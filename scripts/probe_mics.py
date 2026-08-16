#!/usr/bin/env python3
"""Probe each mic for a few seconds and rank by signal / noise."""
from __future__ import annotations

import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from list_mics import (
    ffmpeg_capture_timeout_s,
    is_unreliable_audio_device,
    ranked_audio_devices,
    require_audio_devices,
)

EMPTY_STATS = {"rms": 0.0, "peak": 0.0, "snr_like": 0.0, "noise": 0.0, "signal": 0.0}


def record_probe(device: int, seconds: float, out: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        f":{device}",
        "-t",
        str(seconds),
        "-ac",
        "1",
        "-ar",
        "48000",
        str(out),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=ffmpeg_capture_timeout_s(seconds),
        )
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0 and out.is_file() and out.stat().st_size > 64


def wav_stats(path: Path) -> dict[str, float]:
    if not path.is_file() or path.stat().st_size < 64:
        return dict(EMPTY_STATS)
    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            raw = w.readframes(w.getnframes())
    except wave.Error:
        return dict(EMPTY_STATS)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    x /= 32768.0
    if x.size == 0:
        return dict(EMPTY_STATS)
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))
    # crude noise floor = 10th percentile of short-frame RMS
    hop = max(1, int(0.05 * sr))
    frames = [np.sqrt(np.mean(x[i : i + hop] ** 2)) for i in range(0, len(x) - hop, hop)]
    noise = float(np.percentile(frames, 10)) if frames else 1e-12
    signal = float(np.percentile(frames, 90)) if frames else 0.0
    snr_like = signal / max(noise, 1e-12)
    return {"rms": rms, "peak": peak, "snr_like": snr_like, "noise": noise, "signal": signal}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=2.5)
    args = ap.parse_args()

    devices = ranked_audio_devices(require_audio_devices())
    print(f"Probing {len(devices)} device(s) for {args.seconds:.1f}s each...")
    ranked: list[tuple[float, int, str, dict[str, float]]] = []
    with tempfile.TemporaryDirectory() as td:
        for idx, name in devices:
            out = Path(td) / f"dev{idx}.wav"
            ok = record_probe(idx, args.seconds, out)
            st = wav_stats(out) if ok else dict(EMPTY_STATS)
            score = st["rms"] * np.log1p(st["snr_like"])
            ranked.append((float(score), idx, name, st))
            tag = ""
            if is_unreliable_audio_device(name):
                tag = " [Continuity]"
            if not ok:
                tag += " timed out"
            print(
                f"  [{idx}] {name}: rms={st['rms']:.5f} peak={st['peak']:.5f} "
                f"snr~={st['snr_like']:.2f} score={score:.6f}{tag}"
            )

    usable = [row for row in ranked if not is_unreliable_audio_device(row[2])]
    pick_from = usable or ranked
    pick_from.sort(reverse=True)
    best_score, best_idx, best_name, best_st = pick_from[0]
    if best_st["peak"] <= 0 or best_st["rms"] < 1e-6:
        print("\nWARNING: all probes look silent. Check mic permissions for Terminal/ffmpeg.")
    print(f"\nBEST: [{best_idx}] {best_name} (score={best_score:.6f})")
    print(best_idx)


if __name__ == "__main__":
    main()
