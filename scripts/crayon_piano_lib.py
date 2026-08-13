#!/usr/bin/env python3
"""DSP + shared state for the Piano-crayon terminal UI.

Mirrors the HTML peak-picker, musician bands, 8s synth demo, and track-selection
rules in piano/ui_contract.json. Colors come from chord_pitch_colors.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt

os.environ.setdefault("MPLBACKEND", "Agg")

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chord_pitch_colors import NOTE_NAMES, PC_FR, PC_PENCIL, crayon_rgb

Mode = Literal["idle", "live", "replay"]

MIDI_LO = 21  # A0 / La-1, first key of an 88-key piano
MIDI_HI = 108  # C8 / Do8, last key of an 88-key piano
A4_REF = 440.0
A4_MIN = 415.0
A4_MAX = 466.0
TUNE_LO_HZ = 80.0
TUNE_HI_HZ = 1400.0
TUNE_WINDOW_S = 2.2
MIXED_LO_HZ = 27.5
MIXED_HI_HZ = 2500.0
FFT_SIZE = 8192
PEAKS_PER_SEC = 80.0
WAVE_PLAYHEAD_REPLAY = 0.34
WAVE_PLAYHEAD_LIVE = 0.92
COLS_PER_SEC = 14.0
BLACK_PC = frozenset({1, 3, 6, 8, 10})
THEME_BG = (18, 18, 20)
THEME_INK = (154, 154, 162)
THEME_MUTED = (110, 110, 118)
THEME_PAPER = (24, 24, 28)
TOUS_RGB = (42, 42, 46)
SENS_DEFAULT = 58
DEMO_SR = 44100
DEMO_DUR = 8.0

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Musician:
    id: str
    fr: str
    en: str
    lo: float
    hi: float
    rgb: RGB


MUSICIANS: tuple[Musician, ...] = (
    Musician("bass", "Contrebasse", "Bass", 40, 180, (128, 0, 2)),
    Musician("cello", "Violoncelle", "Cello", 130, 400, (253, 128, 8)),
    Musician("guitarA", "Guitare A", "Guitar A", 200, 520, (33, 255, 6)),
    Musician("guitarB", "Guitare B", "Guitar B", 480, 900, (102, 204, 255)),
    Musician("nylon", "Nylon", "High", 600, 2500, (128, 0, 255)),
)
MUSICIAN_BY_ID = {m.id: m for m in MUSICIANS}

WHITE_MIDIS = tuple(m for m in range(MIDI_LO, MIDI_HI + 1) if (m % 12) not in BLACK_PC)
BLACK_MIDIS = tuple(m for m in range(MIDI_LO, MIDI_HI + 1) if (m % 12) in BLACK_PC)
N_KEYS = MIDI_HI - MIDI_LO + 1


def pc_of(midi: int) -> str:
    return NOTE_NAMES[((midi % 12) + 12) % 12]


def octave_of(midi: int) -> int:
    return midi // 12 - 1


def crayon_of(midi: int) -> RGB:
    return crayon_rgb[pc_of(midi)]


def luminance_255(rgb: RGB) -> float:
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


def lab_color(rgb: RGB) -> str:
    return "#f4efe6" if luminance_255(rgb) < 0.48 else "#3a342e"


def lab_rgb(rgb: RGB) -> RGB:
    return (244, 239, 230) if luminance_255(rgb) < 0.48 else (58, 52, 46)


def mix_rgb(rgb: RGB, onto: RGB, amount: float) -> RGB:
    return (
        int(onto[0] + (rgb[0] - onto[0]) * amount),
        int(onto[1] + (rgb[1] - onto[1]) * amount),
        int(onto[2] + (rgb[2] - onto[2]) * amount),
    )


def dim_rgb(rgb: RGB, factor: float = 0.42) -> RGB:
    return (int(rgb[0] * factor), int(rgb[1] * factor), int(rgb[2] * factor))


def midi_to_hz(midi: float, a4: float = A4_REF) -> float:
    return a4 * (2.0 ** ((midi - 69.0) / 12.0))


def hz_to_midi(freq: float, a4: float = A4_REF) -> float:
    if freq <= 0:
        return float("nan")
    return 69.0 + 12.0 * np.log2(freq / a4)


def fmt_time(seconds: float) -> str:
    t = max(0.0, float(seconds))
    minutes = int(t // 60)
    sec = t - minutes * 60
    whole = int(sec)
    tenth = int((sec - whole) * 10)
    return f"{minutes}:{whole:02d}.{tenth}"


def playhead_frac(mode: Mode) -> float:
    if mode == "replay":
        return WAVE_PLAYHEAD_REPLAY
    if mode == "live":
        return WAVE_PLAYHEAD_LIVE
    if mode == "idle":
        return WAVE_PLAYHEAD_REPLAY
    raise RuntimeError(f"unhandled mode: {mode}")


def clock_text(mode: Mode, t: float, duration: float, live_t: float) -> str:
    if mode == "replay":
        return f"{fmt_time(t)} / {fmt_time(duration)}"
    if mode == "live":
        return f"Live · {fmt_time(live_t)}"
    if mode == "idle":
        return f"{fmt_time(t)} / {fmt_time(duration)}"
    raise RuntimeError(f"unhandled mode: {mode}")


def _add_tone(
    data: np.ndarray,
    sr: int,
    freq: float,
    start: float,
    length: float,
    amp: float,
) -> None:
    i0 = int(start * sr)
    i1 = min(data.size, int((start + length) * sr))
    if i1 <= i0:
        return
    t = np.arange(i1 - i0, dtype=np.float64) / sr
    env = np.minimum(1.0, t / 0.05) * np.exp(-t / (length * 0.8))
    sig = (
        np.sin(2 * np.pi * freq * t)
        + 0.5 * np.sin(2 * np.pi * freq * 2 * t)
        + 0.25 * np.sin(2 * np.pi * freq * 3 * t)
    )
    data[i0:i1] += amp * env * sig


def synthesize_demo(sr: int = DEMO_SR, dur: float = DEMO_DUR) -> tuple[np.ndarray, int]:
    """8s bass + mids + a few chords — same idea as the HTML built-in demo."""
    n = int(sr * dur)
    data = np.zeros(n, dtype=np.float64)
    _add_tone(data, sr, 65.41, 0.0, dur, 0.35)
    _add_tone(data, sr, 196.00, 0.5, 3.0, 0.25)
    _add_tone(data, sr, 261.63, 3.5, 3.0, 0.25)
    chords = (
        (0.5, (329.63, 415.30, 493.88)),
        (2.5, (349.23, 440.00, 523.25)),
        (4.5, (392.00, 493.88, 587.33)),
        (6.5, (329.63, 415.30, 493.88)),
    )
    for start, freqs in chords:
        for freq in freqs:
            _add_tone(data, sr, freq, start, 1.8, 0.18)
    _add_tone(data, sr, 1046.50, 1.0, 0.3, 0.08)
    _add_tone(data, sr, 1318.51, 5.0, 0.3, 0.08)
    peak = float(np.max(np.abs(data))) or 1.0
    data *= 0.9 / peak
    return data, sr


def _bandpass_sos(sr: int, lo: float, hi: float) -> np.ndarray:
    nyq = 0.5 * sr
    low = min(max(lo / nyq, 1e-5), 0.98)
    high = min(max(hi / nyq, low + 1e-4), 0.999)
    return butter(2, [low, high], btype="bandpass", output="sos")


def _filter_band(audio: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    sos = _bandpass_sos(sr, lo, hi)
    try:
        return sosfiltfilt(sos, audio)
    except ValueError:
        return sosfilt(sos, audio)


def compute_band_envelopes(
    audio: np.ndarray,
    sr: int,
    *,
    peaks_per_sec: float = PEAKS_PER_SEC,
) -> dict[str, np.ndarray]:
    """Band-limited RMS envelopes (biquad SOS) for each musician, 0..1."""
    hop = max(1, int(round(sr / peaks_per_sec)))
    n_hops = max(1, int(np.ceil(audio.size / hop)))
    pad = n_hops * hop - audio.size
    out: dict[str, np.ndarray] = {}
    for mus in MUSICIANS:
        y = _filter_band(audio, sr, mus.lo, mus.hi)
        if pad > 0:
            y = np.pad(y, (0, pad))
        env = np.sqrt(np.mean(y[: n_hops * hop].reshape(n_hops, hop) ** 2, axis=1))
        peak = float(np.max(env)) or 1.0
        out[mus.id] = (env / peak).astype(np.float32)
    return out


def envelope_at(env: np.ndarray, t: float, peaks_per_sec: float = PEAKS_PER_SEC) -> float:
    if env.size == 0:
        return 0.0
    idx = int(t * peaks_per_sec)
    if idx < 0 or idx >= env.size:
        return 0.0
    return float(env[idx])


def column_blocks(amp: float, rows: int) -> list[str]:
    """Mirrored GarageBand envelope for one column (half-block cells)."""
    if rows <= 0:
        return []
    q = round(max(0.0, min(1.0, float(amp))) * 24.0) / 24.0
    return list(_column_blocks_cached(q, rows))


@lru_cache(maxsize=512)
def _column_blocks_cached(amp: float, rows: int) -> tuple[str, ...]:
    mid = rows / 2.0
    lo = mid - amp * mid
    hi = mid + amp * mid
    chars: list[str] = []
    for r in range(rows):
        top = max(0.0, min(0.5, hi - r) - max(0.0, lo - r))
        bot = max(0.0, min(1.0, hi - r) - max(0.5, lo - r))
        top_on = top >= 0.22
        bot_on = bot >= 0.22
        if top_on and bot_on:
            chars.append("█")
        elif top_on:
            chars.append("▀")
        elif bot_on:
            chars.append("▄")
        else:
            chars.append(" ")
    if amp > 0.04 and all(c == " " for c in chars):
        mid_i = min(rows - 1, rows // 2)
        chars[mid_i] = "▄"
        if mid_i > 0:
            chars[mid_i - 1] = "▀"
    return tuple(chars)


def rfft_db(window: np.ndarray, sr: int, n: int = FFT_SIZE) -> tuple[np.ndarray, float]:
    buf = np.zeros(n, dtype=np.float64)
    if window.size >= n:
        buf[:] = window[-n:]
    elif window.size:
        buf[-window.size :] = window
    spec = np.fft.rfft(buf * np.blackman(n))
    mag = np.abs(spec) / (n / 2.0)
    db = 20.0 * np.log10(mag + 1e-12)
    db = np.clip(db, -95.0, 0.0)
    return db, sr / n


def window_at(audio: np.ndarray, sr: int, t: float, n: int = FFT_SIZE) -> np.ndarray:
    i1 = int(t * sr)
    i0 = i1 - n
    out = np.zeros(n, dtype=np.float64)
    if i1 <= 0:
        return out
    s0 = max(0, i0)
    d0 = s0 - i0
    s1 = min(audio.size, i1)
    take = s1 - s0
    if take > 0:
        out[d0 : d0 + take] = audio[s0:s1]
    return out


def band_energy_db(db: np.ndarray, bin_hz: float, lo: float, hi: float) -> float:
    i0 = max(1, int(lo / bin_hz))
    i1 = min(db.size - 1, int(np.ceil(hi / bin_hz)))
    if i1 < i0:
        return 0.0
    lin = 10.0 ** (db[i0 : i1 + 1] / 20.0)
    return float(np.sqrt(np.mean(lin * lin)))


@dataclass
class LitNote:
    midi: int
    score: float
    freq: float


@dataclass
class FrameResult:
    lit: list[LitNote]
    chroma: dict[str, float]
    gate: float
    abs_gate: float
    peaks: list[tuple[float, float]]
    band_energy: dict[str, float]
    a_est: float
    tune_ready: bool


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def _band_noise_floor(spec: np.ndarray, i0: int, i1: int) -> float:
    step = max(1, (i1 - i0) // 72)
    samples = spec[i0 : i1 + 1 : step]
    if samples.size == 0:
        return -90.0
    return float(np.median(samples))


def _scan_tune_peaks(spec: np.ndarray, bin_hz: float) -> list[tuple[float, float]]:
    i0 = max(2, int(TUNE_LO_HZ / bin_hz))
    i1 = min(spec.size - 2, int(np.ceil(TUNE_HI_HZ / bin_hz)))
    floor = _band_noise_floor(spec, i0, i1)
    min_db = max(-72.0, floor + 8.0)
    peaks: list[tuple[float, float]] = []
    for i in range(i0, i1 + 1):
        db = float(spec[i])
        if db < min_db:
            continue
        if db > spec[i - 1] and db >= spec[i + 1] and db > spec[i - 2] and db >= spec[i + 2]:
            denom = float(spec[i - 1] - 2 * spec[i] + spec[i + 1])
            delta = (0.5 * float(spec[i - 1] - spec[i + 1]) / denom) if denom else 0.0
            freq = (i + delta) * bin_hz
            if TUNE_LO_HZ <= freq <= TUNE_HI_HZ:
                peaks.append((freq, db))
    peaks.sort(key=lambda p: p[1], reverse=True)
    return peaks[:16]


def _group_harmonics(peaks: list[tuple[float, float]]) -> list[tuple[float, float]]:
    by_freq = sorted(peaks, key=lambda p: p[0])
    funds: list[tuple[float, float]] = []
    for freq, db in by_freq:
        harmonic = False
        for f0, _ in funds:
            n = round(freq / f0) if f0 else 0
            if n < 2 or n > 8:
                continue
            cents = 1200.0 * np.log2(freq / (n * f0))
            if abs(cents) < 35:
                harmonic = True
                break
        if not harmonic:
            funds.append((freq, db))
    return funds


class TrackSet:
    """Tous / solo-from-Tous / union, snapping empty back to all five."""

    def __init__(self) -> None:
        self.selected: set[str] = {m.id for m in MUSICIANS}

    def is_tous(self) -> bool:
        return len(self.selected) == len(MUSICIANS)

    def active(self) -> list[Musician]:
        return [m for m in MUSICIANS if m.id in self.selected]

    def select_all(self) -> None:
        self.selected = {m.id for m in MUSICIANS}

    def click_musician(self, ident: str) -> None:
        if ident not in MUSICIAN_BY_ID:
            return
        if self.is_tous():
            self.selected = {ident}
        elif ident in self.selected:
            self.selected.discard(ident)
            if not self.selected:
                self.select_all()
        else:
            self.selected.add(ident)

    def freq_in_active_bands(self, freq: float) -> bool:
        if self.is_tous():
            return MIXED_LO_HZ <= freq <= MIXED_HI_HZ
        return any(m.lo <= freq <= m.hi for m in self.active())


class PeakPicker:
    def __init__(self) -> None:
        self.smooth = np.full(N_KEYS, -120.0, dtype=np.float64)
        self.a_est = A4_REF
        self.tune_ready = False
        self._cents_window: list[tuple[float, float]] = []

    def reset(self) -> None:
        self.smooth.fill(-120.0)
        self.a_est = A4_REF
        self.tune_ready = False
        self._cents_window.clear()

    def concert_a(self, autotune: bool) -> float:
        return self.a_est if autotune else A4_REF

    def _midi_from_hz(self, freq: float, a4: float, fold: bool) -> int:
        m = hz_to_midi(freq, a4)
        if not np.isfinite(m):
            return -1
        if fold:
            while m < MIDI_LO:
                m += 12
            while m > MIDI_HI:
                m -= 12
        return int(round(m))

    def _update_tune(self, spec: np.ndarray, bin_hz: float, now: float) -> None:
        peaks = _scan_tune_peaks(spec, bin_hz)
        funds = _group_harmonics(peaks)
        votes: list[float] = []
        for freq, _db in funds:
            midi = int(round(hz_to_midi(freq, A4_REF)))
            expected = midi_to_hz(midi, A4_REF)
            if expected <= 0:
                continue
            cents = 1200.0 * np.log2(freq / expected)
            if not np.isfinite(cents) or abs(cents) > 90:
                continue
            votes.append(float(cents))
        if len(votes) >= 2:
            self._cents_window.append((now, _median(votes)))
            cut = now - TUNE_WINDOW_S
            self._cents_window = [row for row in self._cents_window if row[0] >= cut]
        if len(self._cents_window) >= 8:
            med = _median([c for _, c in self._cents_window])
            clamped = max(-100.0, min(100.0, med))
            target = A4_REF * (2.0 ** (clamped / 1200.0))
            alpha = 0.12 if len(self._cents_window) >= 24 else 0.05
            self.a_est = self.a_est + alpha * (target - self.a_est)
            self.a_est = max(A4_MIN, min(A4_MAX, self.a_est))
            self.tune_ready = True

    def process(
        self,
        spec: np.ndarray,
        bin_hz: float,
        tracks: TrackSet,
        *,
        chords: bool,
        sensitivity: int,
        autotune: bool,
        now: float,
    ) -> FrameResult:
        self._update_tune(spec, bin_hz, now)
        a4 = self.concert_a(autotune)
        mixed = tracks.is_tous()
        bands = [{"lo": MIXED_LO_HZ, "hi": MIXED_HI_HZ}] if mixed else [
            {"lo": m.lo, "hi": m.hi} for m in tracks.active()
        ]
        scan_lo = min(b["lo"] for b in bands)
        scan_hi = max(b["hi"] for b in bands)
        i0 = max(2, int(scan_lo / bin_hz))
        i1 = min(spec.size - 2, int(np.ceil(scan_hi / bin_hz)))
        score = np.full(N_KEYS, -120.0, dtype=np.float64)
        fold = not mixed
        peaks: list[tuple[float, float]] = []
        for i in range(i0, i1 + 1):
            freq = i * bin_hz
            if not tracks.freq_in_active_bands(freq):
                continue
            db = float(spec[i])
            if (
                db > spec[i - 1]
                and db >= spec[i + 1]
                and db > spec[i - 2]
                and db >= spec[i + 2]
            ):
                denom = float(spec[i - 1] - 2 * spec[i] + spec[i + 1])
                delta = (0.5 * float(spec[i - 1] - spec[i + 1]) / denom) if denom else 0.0
                pf = (i + delta) * bin_hz
                if tracks.freq_in_active_bands(pf):
                    peaks.append((pf, db))
            midi = self._midi_from_hz(freq, a4, fold)
            if MIDI_LO <= midi <= MIDI_HI:
                idx = midi - MIDI_LO
                if db > score[idx]:
                    score[idx] = db
        peaks.sort(key=lambda p: p[1], reverse=True)
        for freq, db in peaks:
            midi = self._midi_from_hz(freq, a4, fold)
            if midi < MIDI_LO or midi > MIDI_HI:
                continue
            idx = midi - MIDI_LO
            if db + 2 > score[idx]:
                score[idx] = db + 2
        self.smooth = 0.62 * self.smooth + 0.38 * score
        loudest = float(np.max(self.smooth))
        sens = max(0, min(100, int(sensitivity))) / 100.0
        abs_gate = -48.0 - sens * 36.0
        rel_db = 10.0 + sens * 18.0
        gate = max(abs_gate, loudest - rel_db)
        max_n = 8 if chords else 1
        candidates: list[LitNote] = []
        for i in range(N_KEYS):
            s = float(self.smooth[i])
            if s < gate:
                continue
            left = float(self.smooth[i - 1]) if i > 0 else -999.0
            right = float(self.smooth[i + 1]) if i < N_KEYS - 1 else -999.0
            if s >= left and s >= right:
                midi = i + MIDI_LO
                candidates.append(LitNote(midi=midi, score=s, freq=midi_to_hz(midi, a4)))
        candidates.sort(key=lambda c: c.score, reverse=True)
        lit = candidates[:max_n]
        chroma = {name: -120.0 for name in NOTE_NAMES}
        for i in range(N_KEYS):
            name = pc_of(i + MIDI_LO)
            v = float(self.smooth[i])
            if v > chroma[name]:
                chroma[name] = v
        energy = {
            m.id: band_energy_db(spec, bin_hz, m.lo, m.hi) for m in MUSICIANS
        }
        return FrameResult(
            lit=lit,
            chroma=chroma,
            gate=gate,
            abs_gate=abs_gate,
            peaks=peaks,
            band_energy=energy,
            a_est=self.a_est,
            tune_ready=self.tune_ready,
        )


def chroma_fill_pct(value: float, abs_gate: float, lit_pcs: set[str], name: str) -> float:
    pct = max(0.0, min(100.0, (value - abs_gate) * 1.8))
    on = value >= abs_gate and name in lit_pcs
    if on:
        return max(28.0, pct)
    return max(0.0, pct * 0.25)


def tune_line(autotune: bool, a_est: float, tune_ready: bool, mode: Mode) -> str:
    if not autotune:
        return "La/A = 440 Hz"
    if mode == "idle":
        return "La/A ≈ 440 Hz"
    if not tune_ready:
        return "La/A ≈ 440 Hz · …"
    return f"La/A ≈ {int(round(a_est))} Hz"


def signed_cents(a_est: float) -> str:
    cents = 1200.0 * np.log2(a_est / A4_REF)
    n = int(round(cents))
    return f"{n:+d} ¢" if n else "0 ¢"
