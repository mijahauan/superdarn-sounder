# Observing SuperDARN passively — sources, frequencies, geometry

Field notes for finding a SuperDARN signal to detect. Compiled 2026-06-24 from
the live network; reconcile against the sources as they evolve.

## 1. Schedule — what mode is running, when

Monthly schedule files: **https://github.com/SuperDARN/schedules** (`YYYYMM.swg`,
e.g. `2026/202606.swg`). Format: UT time blocks tagged Common / Special /
Discretionary Time. Nearly all common-time modes are 1-minute, UT-locked scans
(`normalscan`, `themisscan`, `rbspscan`, interleave), so the beam-scan cadence
`beam_phase.py` assumes holds during common time.

- Rendered calendar: https://superdarn.ca/radar-schedule (historical/planning).
- Control-program IDs (cpid): https://superdarn.ca/cpid-info
- Scheduling WG: https://superdarn.thayer.dartmouth.edu/WG-sched/issues.html

Example (June 2026): common-time `normalscan` 06:00–15:00 UT, a `normalsound`
frequency-sweep block 03:00–06:00 UT, then discretionary after 15:00 UT on the
24th.

## 2. Live operating frequency — the radars hop

SuperDARN does a clear-frequency search and **re-tunes roughly every scan
(~1 min)**, so the operating frequency moves by tens of kHz to a different band
between captures. You must read the *current* frequency and scan immediately.

**VT real-time feed** (VT operates Fort Hays + Blackstone). The UI at
`http://vt.superdarn.org/plot/real-time/echoes` shows Status / Beam / Op-mode /
Frequency(kHz) per radar. Under the hood (reverse-engineered):

- REST echo counts: `GET https://vt.superdarn.org/echoes?site_name=<abbr>`
  → JSON `{timestamp[], total_echoes[], ionospheric_echoes[], ground_scatter_echoes[]}`
  (a recent `timestamp` = the radar is online).
- Live status via **socket.io** (origin `https://vt.superdarn.org` over 443, or
  `http://vt.superdarn.org:81` over http): event named `"<abbr>"` pushes
  `{freq: <kHz>, beam: <n>, ...}`; event `"<abbr>/echoes"` pushes echo arrays.
  A minimal `python-socketio` client that registers `sio.on("fhe", ...)` etc.
  reads the live frequency. (`superdarn-sounder` could grow an auto-tune mode
  that drives `detect-scan`'s centre from this feed — see §5.)

Observed live values 2026-06-24 ~12:1x UT (illustrative — they hop):
`fhe 10.8–11.1`, `fhw 11.0–11.1`, `bks 11.6–11.7 MHz`; Canadian radars
(kap/sas/pgr/rkn/inv/cly) clustered 10.4–10.9 MHz.

Other frequency sources: 24-h **summary plots** (`tfreq` panel) at
https://superdarn.ca/summary-plots; **rawACF/fitACF** downloads
(https://superdarn.ca/data-download) carry `tfreq`/`cp`/`bmnum` per integration
(the ground truth `scripts/validate_against_rawacf.py` consumes). Network range:
8–20 MHz, most radars 10–14 MHz.

## 3. Which radars to try from central Missouri (EM38ww)

`radars.py` ranks by distance: Fort Hays (FHE/FHW, ~600 km) closest, then
Blackstone/Wallops (~1100 km), Christmas Valley (~2200 km), Adak far.

## 4. The hard part: beam geometry

**US SuperDARN radars beam poleward (north).** Boresights (from `data/radars.toml`):
FHE +45°, FHW −25°, BKS −40°, WAL +36° — all point N/NE toward the auroral zone.
A mid-latitude central-US receiver sits **off the main lobe** of these radars, so
the direct path arrives mainly via antenna side/back-lobes — much weaker than a
main-beam illumination. Combined with HF skip geometry (~600–1100 km can be near
the skip zone depending on band/time) and the ~1-minute frequency hopping, a
*blind* fixed-frequency capture rarely lands a clean burst.

Best odds: read the live frequency (§2), scan that exact centre with a ±75 kHz
window, and dwell across at least one full 1-minute scan so the beam sweeps
through the geometry that best couples to us. Lower bands (10–11 MHz) and
night/terminator hours generally favour the closer paths.

## 5. Tracking mode — `detect-scan --track <radar>`

The fix for the frequency-hop problem is implemented: `detect-scan --track <abbr>`
(needs the `track` extra) reads the radar's live frequency from the VT feed
(`core/vt_realtime.py`) and continuously re-tunes the scan to it, dwelling across
full scans so we are always on-frequency when the beam/geometry favours us.

```bash
superdarn-sounder detect-scan --config <cfg> --track fhe --dwell 90
```

## 6. First light (2026-06-24, ~12:25 UT)

Tracked dwells against sigma's RX-888 Mk2 produced credible detections:

- **Fort Hays East (fhe) @ 11.091 MHz** — a sustained ~5 s burst of *consecutive*
  frames matching `eight_pulse` (the standard normalscan sequence), τ≈1500 µs,
  several frames at score **1.00** (all 8 lags), stable beam≈13, bracketed by
  quiet frames. That contiguous envelope is a SuperDARN beam-dwell sweeping past
  us — a clean detection.
- **Blackstone (bks) @ 11.716 MHz** — 42 pulses, `seven_pulse` score 0.86,
  +10 dB; strong pulsed signal but the score is partly **density-inflated** (see
  below), so treat the bks mode-ID as provisional.

**Matcher refinement (known):** on dense frames (many overlapping sequences in
one 0.5 s window, tens of pulses) `match_sequence`'s score can inflate, because
almost any ptab offset lands near *some* pulse. The clean fhe result came from
sparse single-sequence frames (e.g. 9 pulses → 8/8). To make mode-ID rigorous on
busy frames, window the matcher to a single pulse-repetition interval and/or add
a "purity" term (penalise unexplained pulses). Then cross-check with rawACF
(`scripts/validate_against_rawacf.py`).

## 7. Phase 2 — propagation products (2026-06-24)

`detect-scan --track <radar>` now emits, at the end of a dwell, the
path-condition observables built on the shared `hamsci-dsp` library:
**dTEC + dTEC/dt** (carrier phase across detected pulses), **scintillation**
(S4 / sigma_phi), and a **propagation window** (per-radar observed
supported-frequency = a measured lower bound on path MUF). Oblique
virtual-height/MUF is wired (`core/propagation.oblique_products`) and lights up
once an absolute group delay is bridged from rawACF.

Validated live on sigma: a tracked Blackstone dwell (11.745 MHz) caught a clean
beam-dwell burst (eight_pulse, tau=1500 us, score 1.00) and produced
`dTEC span ~ -0.0013 TECU, |rate|max ~ 0.0024 TECU/s, unwrap_q 1.00`. In track
mode the source is attributed to the tracked radar (we tuned to its live
frequency), not the nearest-audible guess.
