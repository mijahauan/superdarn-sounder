"""Stream-source tests.

Guards the ka9q callback contract that the synthetic path can't exercise:
``RadiodStream`` invokes ``on_samples(samples, quality)`` — a one-arg callback
silently breaks the live path (caught during the sigma RX888 integration test).
"""
import numpy as np

from superdarn_sounder.core.stream import RadiodIQSource, SyntheticIQSource


def _src():
    return RadiodIQSource(
        radiod_status_dns="x-status.local",
        center_freq_hz=12_000_000, sample_rate_hz=100_000, frame_seconds=0.5,
        lifetime_frames=100,
    )


def test_on_samples_accepts_quality_arg():
    src = _src()
    block = np.ones(8, dtype=np.complex64)
    # RadiodStream delivers (samples, quality); both forms must enqueue.
    src._on_samples(block, quality="ignored")
    src._on_samples(block)                       # quality optional
    assert src._q.qsize() == 2


def test_on_samples_sanitizes_nans():
    src = _src()
    bad = np.array([1 + 1j, np.nan + 0j, 2 + 0j], dtype=np.complex64)
    src._on_samples(bad, quality=None)
    got = src._q.get_nowait()
    assert np.isfinite(got).all()


def test_synthetic_source_yields_frames():
    src = SyntheticIQSource(100_000.0, 0.2, ptab=[0, 14, 22, 24, 27, 31, 42, 43],
                            tau_us=2400.0, n_frames=2)
    frames = [f for f, _utc in src]
    assert len(frames) == 2
    assert frames[0].dtype == np.complex64
