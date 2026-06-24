"""VT SuperDARN real-time frequency feed client.

Virginia Tech publishes a near-real-time status stream for the radars it tracks
(Fort Hays, Blackstone, and the wider network).  Each radar's current operating
frequency hops roughly every scan (~1 min) as it does its clear-frequency
search, so a passive receiver has to follow it.  This client keeps a live cache
of the latest {frequency, beam} per radar so the tracker can re-tune to the
radar's current frequency.

Endpoint (reverse-engineered from vt.superdarn.org/plot/real-time/echoes):
  socket.io at https://vt.superdarn.org ; event named "<abbr>" delivers
  {"freq": <kHz>, "beam": <n>, ...}.  See docs/OBSERVING.md §2.

``python-socketio[client]`` is an OPTIONAL dependency (the ``track`` extra); the
core client and the daemon do not need it.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://vt.superdarn.org"


@dataclass
class RadarStatus:
    freq_khz: int
    beam: Optional[int]
    received_monotonic: float

    def age_s(self) -> float:
        return time.monotonic() - self.received_monotonic


class VTRealtimeClient:
    """Persistent socket.io client caching the latest status per radar."""

    def __init__(self, sites: list[str], url: str = DEFAULT_URL):
        self.sites = list(sites)
        self.url = url
        self._latest: dict[str, RadarStatus] = {}
        self._lock = threading.Lock()
        self._sio = None

    def start(self, wait_timeout: float = 15.0) -> None:
        try:
            import socketio
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "python-socketio not installed — install the 'track' extra: "
                "uv pip install -e '.[track]'"
            ) from exc
        self._sio = socketio.Client(reconnection=True, logger=False,
                                    engineio_logger=False)
        for site in self.sites:
            self._sio.on(site, self._make_handler(site))
        self._sio.connect(self.url, transports=["websocket", "polling"],
                          wait_timeout=wait_timeout)

    def _make_handler(self, site: str):
        def handler(data) -> None:
            if not isinstance(data, dict):
                return
            freq = data.get("freq")
            if freq is None:
                return
            try:
                freq_khz = int(freq)
            except (TypeError, ValueError):
                return
            beam = data.get("beam")
            with self._lock:
                self._latest[site] = RadarStatus(
                    freq_khz=freq_khz,
                    beam=int(beam) if beam is not None else None,
                    received_monotonic=time.monotonic(),
                )
        return handler

    def current(self, site: str, max_age_s: float = 180.0) -> Optional[RadarStatus]:
        """Latest status for a radar, or None if never seen / too stale."""
        with self._lock:
            st = self._latest.get(site)
        if st is None or st.age_s() > max_age_s:
            return None
        return st

    def wait_for(self, site: str, timeout_s: float = 15.0) -> Optional[RadarStatus]:
        """Block until a fresh status for ``site`` arrives (or timeout)."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            st = self.current(site)
            if st is not None:
                return st
            time.sleep(0.5)
        return None

    def stop(self) -> None:
        if self._sio is not None:
            try:
                self._sio.disconnect()
            except Exception:
                pass
