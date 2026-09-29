#!/usr/bin/env python3
"""Live BPM counter for Piano-crayon — one estimator, ported to every surface.

Front end (PCM → onset envelope at ONSET_HZ)
    2048-point Hann STFT, hop = sr / 100 → one onset value every 10 ms.
    Bin magnitudes are averaged into log-spaced bands (6 per octave, 30 Hz to
    8 kHz, ≤ 48 bands) so a broadband hat and a sub-bass kick weigh by level,
    not by how many FFT bins they happen to cover (the reason onset strength
    is computed on mel bands everywhere). Per band: L_b = ln(1 + 100·m_b),
    SuperFlux-style flux Σ_b max(0, L_b[t] − max(L_{b−1..b+1}[t−1]) − 0.05)
    (Böck & Widmer 2013: the 3-band max over the previous frame cancels
    energy that merely sloshes between neighbours — vibrato, and the leakage
    ripple a stationary tone makes as its phase sweeps across frames), then a
    1 s running mean is subtracted and the remainder half-wave rectified.

Tempo (onset envelope → BPM)
    The envelope is smoothed by a 3-tap Hann (onset spikes are 1–2 samples
    wide at 100 Hz; a beat period is fractional, and an integer comb misses
    a spike it cannot straddle). Comb-enhanced autocorrelation
    A(L) = r(L)·(1 + ½·max r(2L±1) + ¼·max r(4L±2)) over the last 8 s
    (Percival & Tzanetakis 2014 with a tolerant, multiplicative comb: the
    candidate's own lag carries the score, so neither 1.5·P nor P/2 can win
    on its multiples alone), a mild log-Gaussian prior centred on 128 BPM
    (σ = 0.75 octave), argmax over 60–200 BPM, parabolic refinement. Then a
    halving test: a kick on every beat correlates as well at P as at 2P, so
    when max r(L*/2 ± 1) ≥ 0.9·r(L*) the faster reading wins (a true-tempo
    train reads ≈ −0.06 there; the margin is wide).

Confidence (Shannon energy collapse)
    Fold the onset energy on the chosen period into 16 beat-phase bins and
    take the normalised Shannon entropy H of that histogram. On the true
    period the energy collapses into a few phase bins (H → 0); on a wrong
    period it spreads flat (H → 1). `collapse = 1 − H` is reported next to
    the autocorrelation peak `confidence = r(L*)`. Same structure as
    conditional-entropy period finding (Graham et al. 2013): the beat is the
    period on which the onset ensemble's phase entropy collapses, exactly the
    way a binding mode is the pose on which configurational entropy collapses.

Display: median of the last five estimates (1.25 s), integer BPM.
Contract: piano/dsp_contract.json → "bpm".
Ports:    web/bpm_tracker.js, ios/CrayonPiano.swiftpm/BpmTracker.swift.
"""
from __future__ import annotations

import argparse
import math
import sys
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ONSET_HZ = 100.0
FRAME = 2048
WINDOW_S = 8.0
MIN_S = 3.0
UPDATE_S = 0.25
BPM_MIN = 60.0
BPM_MAX = 200.0
PRIOR_BPM = 128.0
PRIOR_SIGMA_OCT = 0.75
FOLD_BINS = 16
COMB_W2 = 0.5
COMB_W4 = 0.25
HALF_RATIO = 0.9
FLUX_MU = 100.0
FLUX_LO_HZ = 30.0
FLUX_HI_HZ = 8000.0
BANDS_PER_OCTAVE = 6
MEAN_TAU_S = 1.0
FLUX_DEADBAND = 0.05
READY_CONFIDENCE = 0.12
READY_COLLAPSE = 0.12
MEDIAN_N = 5


@dataclass(frozen=True)
class TempoEstimate:
    bpm: float
    lag: float  # onset samples per beat
    confidence: float  # normalised autocorrelation at the beat lag, 0..1
    collapse: float  # 1 − normalised Shannon entropy of the beat-phase fold
    phase: float  # beat phase 0..1 of the loudest fold bin
    ready: bool


NOT_READY = TempoEstimate(0.0, 0.0, 0.0, 0.0, 0.0, False)


@dataclass(frozen=True)
class BpmState:
    bpm: float | None
    confidence: float
    collapse: float
    ready: bool
    seconds: float  # onset seconds analysed so far


IDLE = BpmState(None, 0.0, 0.0, False, 0.0)


def band_plan(bin_hz: float, n_bins: int) -> list[tuple[int, int]]:
    """[(k_lo, k_hi)] inclusive bin ranges of the log bands that have ≥ 1 bin.

    Shared by the PCM and the AnalyserNode front ends (web/bpm_tracker.js
    computes the same plan from the same bin width).
    """
    k_lo = max(1, int(math.ceil(FLUX_LO_HZ / bin_hz)))
    hi_hz = min(FLUX_HI_HZ, bin_hz * (n_bins - 1))
    k_hi = int(math.floor(hi_hz / bin_hz))
    plan: list[tuple[int, int]] = []
    cur = -1
    start = k_lo
    for k in range(k_lo, k_hi + 1):
        b = int(math.floor(BANDS_PER_OCTAVE * math.log2(k * bin_hz / FLUX_LO_HZ)))
        if b != cur:
            if cur >= 0:
                plan.append((start, k - 1))
            cur = b
            start = k
    if cur >= 0 and k_hi >= start:
        plan.append((start, k_hi))
    return plan


def band_logmag(mag: np.ndarray, plan: list[tuple[int, int]]) -> np.ndarray:
    """Mean linear magnitude per band, log-compressed: ln(1 + 100·m_b)."""
    out = np.empty(len(plan), dtype=np.float64)
    for i, (a, b) in enumerate(plan):
        out[i] = float(np.mean(mag[a : b + 1]))
    return np.log1p(FLUX_MU * out)


class OnsetFrontEnd:
    """PCM in, onset strength out — one value per 1/ONSET_HZ second."""

    def __init__(self, sr: int, *, frame: int = FRAME, onset_hz: float = ONSET_HZ) -> None:
        self.sr = int(sr)
        self.frame = int(frame)
        self.hop = max(1, int(round(self.sr / onset_hz)))
        self.win = np.hanning(self.frame)
        self.plan = band_plan(self.sr / self.frame, self.frame // 2 + 1)
        self._alpha = 1.0 / (MEAN_TAU_S * onset_hz)
        self.reset()

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float64)
        self._prev: np.ndarray | None = None
        self._mean = 0.0
        self._primed = False

    def push(self, samples: np.ndarray) -> list[float]:
        x = np.asarray(samples, dtype=np.float64).ravel()
        if x.size == 0:
            return []
        self._buf = np.concatenate([self._buf, x]) if self._buf.size else x
        out: list[float] = []
        while self._buf.size >= self.frame:
            out.append(self._onset(self._buf[: self.frame]))
            self._buf = self._buf[self.hop :]
        return out

    def _onset(self, frame: np.ndarray) -> float:
        spec = np.fft.rfft(frame * self.win)
        mag = np.abs(spec) * (4.0 / self.frame)
        logmag = band_logmag(mag, self.plan)
        if self._prev is None:
            self._prev = logmag
            return 0.0
        # Per-bin deadband: a stationary tone's Hann leakage ripples each bin
        # by a few percent per hop; a real onset moves it by whole log units.
        prev = self._prev
        # 3-band max of the previous frame (SuperFlux): a band only counts as
        # an onset if it rises above its whole neighbourhood.
        prev_max = prev.copy()
        prev_max[1:] = np.maximum(prev_max[1:], prev[:-1])
        prev_max[:-1] = np.maximum(prev_max[:-1], prev[1:])
        flux = float(np.sum(np.maximum(0.0, logmag - prev_max - FLUX_DEADBAND)))
        self._prev = logmag
        # Prime the running mean on the first real flux. Starting it at zero
        # leaves a one-second ramp in the envelope, and a ramp correlates at
        # every lag: white noise then "locks" at ~146 BPM with r = 0.49.
        if not self._primed:
            self._mean = flux
            self._primed = True
        else:
            self._mean += (flux - self._mean) * self._alpha
        return max(0.0, flux - self._mean)


def tempo_prior(bpm: float) -> float:
    if bpm <= 0:
        return 0.0
    z = math.log2(bpm / PRIOR_BPM) / PRIOR_SIGMA_OCT
    return math.exp(-0.5 * z * z)


def autocorrelation(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Biased, energy-normalised autocorrelation r[0..max_lag], r[0] = 1."""
    n = x.size
    energy = float(np.dot(x, x))
    r = np.zeros(max_lag + 1, dtype=np.float64)
    if energy <= 0.0 or n == 0:
        return r
    for lag in range(0, min(max_lag, n - 1) + 1):
        r[lag] = float(np.dot(x[lag:], x[: n - lag])) / energy
    return r


def fold_collapse(env: np.ndarray, lag: float, bins: int = FOLD_BINS) -> tuple[float, float]:
    """(1 − normalised Shannon entropy, phase of the loudest bin) of the beat fold."""
    n = env.size
    total = float(np.sum(env))
    if total <= 0.0 or lag <= 0.0 or n == 0:
        return 0.0, 0.0
    phase = (np.arange(n, dtype=np.float64) / lag) % 1.0
    idx = np.minimum(bins - 1, (phase * bins).astype(int))
    hist = np.bincount(idx, weights=env, minlength=bins)[:bins]
    p = hist / total
    nz = p[p > 0]
    h = float(-np.sum(nz * np.log(nz)) / math.log(bins))
    return max(0.0, min(1.0, 1.0 - h)), float(np.argmax(hist)) / bins


def smooth3(env: np.ndarray) -> np.ndarray:
    """3-tap Hann (¼, ½, ¼) with edge hold — widens 10 ms spikes to ~30 ms."""
    if env.size < 3:
        return env.copy()
    out = np.empty_like(env)
    out[1:-1] = 0.25 * env[:-2] + 0.5 * env[1:-1] + 0.25 * env[2:]
    out[0] = 0.75 * env[0] + 0.25 * env[1]
    out[-1] = 0.75 * env[-1] + 0.25 * env[-2]
    return out


def estimate_tempo(env: np.ndarray, fps: float = ONSET_HZ) -> TempoEstimate:
    env = np.maximum(0.0, np.asarray(env, dtype=np.float64).ravel())
    n = env.size
    lag_min = int(round(fps * 60.0 / BPM_MAX))
    lag_max = int(round(fps * 60.0 / BPM_MIN))
    if n < lag_max + 2 or float(np.sum(env)) <= 0.0:
        return NOT_READY
    smoothed = smooth3(env)
    x = smoothed - float(smoothed.mean())
    if float(np.dot(x, x)) <= 1e-12:
        return NOT_READY
    top = min(n - 1, 4 * lag_max)
    r = autocorrelation(x, top)

    def near(lag: int, tol: int) -> float:
        lo = max(0, lag - tol)
        hi = min(top, lag + tol)
        return float(np.max(r[lo : hi + 1])) if hi >= lo else 0.0

    def enhanced(lag: int) -> float:
        own = max(0.0, float(r[lag]))
        comb = 1.0
        if 2 * lag <= top:
            comb += COMB_W2 * max(0.0, near(2 * lag, 1))
        if 4 * lag <= top:
            comb += COMB_W4 * max(0.0, near(4 * lag, 2))
        return own * comb

    # One lag beyond each edge is scored too, so the parabola always has neighbours.
    lo = max(1, lag_min - 1)
    hi = min(top, lag_max + 1)
    score = {lag: enhanced(lag) * tempo_prior(60.0 * fps / lag) for lag in range(lo, hi + 1)}
    best = max(range(lag_min, lag_max + 1), key=lambda lag: score[lag])
    half = int(round(best / 2.0))
    if half >= lag_min and r[best] > 0 and near(half, 1) >= HALF_RATIO * float(r[best]):
        best = max(range(max(lag_min, half - 1), min(lag_max, half + 1) + 1), key=lambda lag: float(r[lag]))
    lag = float(best)
    if best - 1 in score and best + 1 in score:
        s0, s1, s2 = score[best - 1], score[best], score[best + 1]
        denom = s0 - 2.0 * s1 + s2
        if denom < 0.0:
            lag = best + max(-0.5, min(0.5, 0.5 * (s0 - s2) / denom))
    confidence = max(0.0, min(1.0, float(r[best])))
    collapse, phase = fold_collapse(env, lag)
    bpm = 60.0 * fps / lag
    # Two gates: the comb peak must be real (confidence) AND the onset energy
    # must collapse onto that period (collapse). A stationary tone passes the
    # first with r ≈ 0.9 and fails the second with a flat fold.
    ready = confidence >= READY_CONFIDENCE and collapse >= READY_COLLAPSE
    return TempoEstimate(bpm, lag, confidence, collapse, phase, ready)


class BpmTracker:
    """Push contiguous PCM (any chunking); read `snapshot()` whenever the UI paints."""

    def __init__(self, sr: int, *, fps: float = ONSET_HZ) -> None:
        self.fps = float(fps)
        self.front = OnsetFrontEnd(sr, onset_hz=self.fps)
        self._ring = np.zeros(int(WINDOW_S * self.fps), dtype=np.float64)
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.front.reset()
            self._ring.fill(0.0)
            self._n = 0
            self._last_update = 0
            self._estimates: deque[TempoEstimate] = deque(maxlen=MEDIAN_N)
            self._state = IDLE

    def push(self, samples: np.ndarray) -> None:
        onsets = self.front.push(samples)
        if onsets:
            self.push_onsets(onsets)

    def push_onsets(self, values: list[float]) -> None:
        size = self._ring.size
        with self._lock:
            for v in values:
                self._ring[self._n % size] = v
                self._n += 1
            if self._n - self._last_update >= UPDATE_S * self.fps and self._n >= MIN_S * self.fps:
                self._last_update = self._n
                self._update()

    def _window(self) -> np.ndarray:
        size = self._ring.size
        m = min(self._n, size)
        if m == 0:
            return np.zeros(0, dtype=np.float64)
        idx = np.arange(self._n - m, self._n) % size
        return self._ring[idx]

    def _update(self) -> None:
        est = estimate_tempo(self._window(), self.fps)
        self._estimates.append(est)
        ready = [e.bpm for e in self._estimates if e.ready]
        bpm = float(np.median(ready)) if ready else None
        self._state = BpmState(
            bpm=bpm,
            confidence=est.confidence,
            collapse=est.collapse,
            ready=est.ready and bool(ready),
            seconds=self._n / self.fps,
        )

    def snapshot(self) -> BpmState:
        with self._lock:
            return self._state


def bpm_text(state: BpmState, active: bool = True) -> str:
    """♩ — (idle) · ♩ … (settling) · ♩ 140 (locked)."""
    if not active:
        return "♩ —"
    if not state.ready or state.bpm is None:
        return "♩ …"
    return f"♩ {int(round(state.bpm))}"


def synth_beat(sr: int, seconds: float, bpm: float, *, hats: bool = True, pad: bool = True) -> np.ndarray:
    """Deterministic test signal: a 909-style kick every beat (pitch sweep 160→50 Hz
    with a click), bright hats on the off-beats, a sustained pad."""
    n = int(sr * seconds)
    out = np.zeros(n, dtype=np.float64)
    beat = 60.0 / bpm

    def burst(t0: float, length: float, decay: float, amp: float, freqs: tuple[tuple[float, float], ...]) -> None:
        i0 = int(round(t0 * sr))
        i1 = min(n, i0 + int(length * sr))
        if i1 <= i0:
            return
        t = np.arange(i1 - i0, dtype=np.float64) / sr
        env = np.exp(-t / decay)
        sig = np.zeros_like(t)
        for f, a in freqs:
            sig += a * np.sin(2.0 * np.pi * f * t)
        out[i0:i1] += amp * env * sig

    def kick(t0: float) -> None:
        i0 = int(round(t0 * sr))
        i1 = min(n, i0 + int(0.25 * sr))
        if i1 <= i0:
            return
        t = np.arange(i1 - i0, dtype=np.float64) / sr
        # instantaneous frequency 160 Hz → 50 Hz with a 40 ms time constant
        freq = 50.0 + 110.0 * np.exp(-t / 0.04)
        phase = 2.0 * np.pi * np.cumsum(freq) / sr
        body = np.sin(phase) * np.exp(-t / 0.09)
        click = np.exp(-t / 0.003) * (np.sin(2.0 * np.pi * 1800.0 * t) + 0.6 * np.sin(2.0 * np.pi * 4100.0 * t))
        out[i0:i1] += 0.8 * body + 0.25 * click

    t0 = 0.0
    while t0 < seconds:
        kick(t0)
        if hats:
            burst(t0 + beat / 2.0, 0.06, 0.02, 0.12, ((6000.0, 1.0), (9300.0, 0.7)))
        t0 += beat
    if pad:
        out += 0.1 * np.sin(2.0 * np.pi * 220.0 * np.arange(n, dtype=np.float64) / sr)
    peak = float(np.max(np.abs(out))) or 1.0
    return out * (0.9 / peak)


def track_array(audio: np.ndarray, sr: int, *, chunk: int = 4800) -> BpmState:
    tracker = BpmTracker(sr)
    for i in range(0, audio.size, chunk):
        tracker.push(audio[i : i + chunk])
    return tracker.snapshot()


def self_test() -> int:
    sr = 48000

    def expect(name: str, state: BpmState, want: float, tol: float, min_conf: float) -> None:
        if not state.ready or state.bpm is None:
            raise SystemExit(f"{name}: tracker never locked ({state})")
        if abs(state.bpm - want) > tol:
            raise SystemExit(f"{name}: {state.bpm:.2f} BPM, wanted {want} ± {tol}")
        if state.confidence < min_conf:
            raise SystemExit(f"{name}: confidence {state.confidence:.2f} < {min_conf}")
        print(f"  {name}: {state.bpm:.1f} BPM · conf {state.confidence:.2f} · collapse {state.collapse:.2f}")

    # Ideal envelope: impulses every 50 onset samples at 100 Hz → 120 BPM, near-total collapse.
    env = np.zeros(800)
    env[::50] = 1.0
    est = estimate_tempo(env, ONSET_HZ)
    if not est.ready or abs(est.bpm - 120.0) > 0.5:
        raise SystemExit(f"impulse envelope should read 120 BPM, got {est}")
    if est.collapse < 0.85:
        raise SystemExit(f"impulse envelope should collapse into one phase bin, got {est.collapse:.2f}")
    if estimate_tempo(np.zeros(800), ONSET_HZ).ready:
        raise SystemExit("a flat envelope must not be ready")
    print(f"  impulse envelope: {est.bpm:.2f} BPM · collapse {est.collapse:.2f}")

    expect("140 BPM kick + hats + pad", track_array(synth_beat(sr, 10.0, 140.0), sr), 140.0, 1.5, 0.25)
    expect("90 BPM kicks only", track_array(synth_beat(sr, 12.0, 90.0, hats=False), sr), 90.0, 1.5, 0.25)
    expect("172 BPM kick + hats", track_array(synth_beat(sr, 10.0, 172.0), sr), 172.0, 2.0, 0.2)
    expect("44.1 kHz 128 BPM", track_array(synth_beat(44100, 10.0, 128.0), 44100), 128.0, 1.5, 0.25)
    # Range edges and a fractional-lag tempo (138 BPM = 43.48 onset samples).
    expect("64 BPM", track_array(synth_beat(sr, 12.0, 64.0), sr), 64.0, 1.5, 0.25)
    expect("138 BPM", track_array(synth_beat(sr, 10.0, 138.0), sr), 138.0, 1.5, 0.25)
    expect("198 BPM", track_array(synth_beat(sr, 10.0, 198.0), sr), 198.0, 2.0, 0.25)

    rng = np.random.default_rng(7)
    quiet = track_array(rng.normal(0.0, 1e-4, sr * 6), sr)
    if quiet.ready:
        raise SystemExit(f"near-silence must not lock a tempo: {quiet}")
    tt = np.arange(sr * 6, dtype=np.float64) / sr
    for name, sig in (
        ("220 Hz tone", 0.3 * np.sin(2 * np.pi * 220.0 * tt)),
        ("55 Hz tone", 0.3 * np.sin(2 * np.pi * 55.0 * tt)),
        ("C-minor chord", 0.2 * (np.sin(2 * np.pi * 130.8 * tt) + np.sin(2 * np.pi * 155.6 * tt) + np.sin(2 * np.pi * 196.0 * tt))),
    ):
        steady = track_array(sig, sr)
        if steady.ready:
            raise SystemExit(f"{name} has no beat and must not lock: {steady}")
    print("  silence, tones and a held chord: not ready")

    tracker = BpmTracker(sr)
    if bpm_text(tracker.snapshot()) != "♩ …" or bpm_text(tracker.snapshot(), active=False) != "♩ —":
        raise SystemExit("bpm_text idle / settling contract")
    tracker.push(synth_beat(sr, 8.0, 140.0))
    if bpm_text(tracker.snapshot()) != "♩ 140":
        raise SystemExit(f"bpm_text locked contract, got {bpm_text(tracker.snapshot())!r}")
    tracker.reset()
    if tracker.snapshot().ready or tracker.snapshot().seconds != 0.0:
        raise SystemExit("reset must forget the previous song")
    print("bpm_tracker self-test: OK (140 / 90 / 172 / 128 BPM, silence stays quiet)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Live BPM counter — reference implementation")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--wav", type=Path, default=None, help="16-bit PCM WAV to estimate")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    if args.wav is None:
        parser.error("--self-test or --wav required")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analyze_instruments import load_wav  # noqa: E402

    audio, sr = load_wav(args.wav)
    state = track_array(np.asarray(audio, dtype=np.float64), sr)
    if not state.ready or state.bpm is None:
        print(f"{args.wav.name}: no steady beat found (confidence {state.confidence:.2f})")
        raise SystemExit(2)
    print(f"{args.wav.name}: {state.bpm:.1f} BPM · confidence {state.confidence:.2f} · collapse {state.collapse:.2f}")


if __name__ == "__main__":
    main()
