"""VTRealtimeClient unit tests — exercise the cache logic without a network.

The socket.io transport is the optional 'track' extra; these tests drive the
status cache via the handler directly so they need no connection.
"""
import time

from superdarn_sounder.core.vt_realtime import VTRealtimeClient


def test_handler_caches_latest_status():
    c = VTRealtimeClient(["bks", "fhe"])
    c._make_handler("bks")({"freq": 11651, "beam": 12})
    st = c.current("bks")
    assert st is not None
    assert st.freq_khz == 11651
    assert st.beam == 12


def test_handler_ignores_malformed():
    c = VTRealtimeClient(["bks"])
    c._make_handler("bks")("not a dict")
    c._make_handler("bks")({"beam": 3})        # no freq
    c._make_handler("bks")({"freq": "junk"})   # unparseable
    assert c.current("bks") is None


def test_current_respects_max_age():
    c = VTRealtimeClient(["bks"])
    c._make_handler("bks")({"freq": 11000, "beam": 1})
    assert c.current("bks", max_age_s=10) is not None
    # force staleness
    c._latest["bks"].received_monotonic = time.monotonic() - 1000
    assert c.current("bks", max_age_s=180) is None


def test_unknown_site_is_none():
    c = VTRealtimeClient(["bks"])
    assert c.current("zzz") is None
