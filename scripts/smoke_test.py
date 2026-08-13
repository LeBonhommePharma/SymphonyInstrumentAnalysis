#!/usr/bin/env python3
"""Generate a known-pitch WAV and verify the analyzer recovers those notes.

Mic capture (list/probe/record) needs macOS AVFoundation. This smoke test
exercises the analysis path on any machine with numpy + ffmpeg-style 16-bit WAV.
"""
from __future__ import annotations

import math
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_instruments import analyze, load_wav  # noqa: E402

SR = 48000
# Analyzer FFT size is 4096, so pick bin-centered tones (bin * sr / 4096).
TONES = [
    ("E2", 7 * SR / 4096),    # 82.03 Hz
    ("A4", 38 * SR / 4096),   # 445.31 Hz
    ("C5", 45 * SR / 4096),   # 527.34 Hz
]


def write_tone_wav(path: Path, duration_sec: float = 3.0) -> None:
    t = np.arange(int(SR * duration_sec), dtype=np.float64) / SR
    x = np.zeros_like(t)
    for _, hz in TONES:
        x += 0.22 * np.sin(2 * math.pi * hz * t)
        # slight amplitude envelope so RMS is stable
        x += 0.04 * np.sin(2 * math.pi * hz * t) * np.sin(math.pi * t / duration_sec)
    peak = np.max(np.abs(x)) or 1.0
    pcm = np.clip(x / peak * 0.8, -1.0, 1.0)
    samples = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.tobytes())


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "smoke_tones.wav"
        write_tone_wav(wav)
        audio, sr = load_wav(wav)
        if sr != SR:
            raise SystemExit(f"unexpected sample rate {sr}")
        if audio.size < SR:
            raise SystemExit("synthetic WAV too short")
        report = analyze(audio, sr, ignore_vocals=False)

    notes = {p["note"] for p in report["top_pitches"]}
    missing = [name for name, _ in TONES if name not in notes]
    print("Smoke test source: synthetic E2 + A4 + C5 @ 48 kHz")
    print(f"duration={report['duration_sec']}s peak={report['peak']} rms={report['rms']}")
    print("top pitches:")
    for p in report["top_pitches"][:8]:
        print(f"  {p['note']}: ~{p['hz_median']} Hz")
    print("instrument families:")
    for inst in report["instruments"]:
        print(f"  {inst['family']} (salience {inst['salience']})")
    if report["peak"] <= 0:
        raise SystemExit("smoke WAV was silent")
    if missing:
        raise SystemExit(f"analyzer missed expected notes: {missing}; found {sorted(notes)}")
    print("SMOKE OK: recovered E2, A4, and C5")


if __name__ == "__main__":
    main()
