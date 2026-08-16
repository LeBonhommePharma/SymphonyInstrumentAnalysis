#!/usr/bin/env python3
"""Record from a chosen (or auto-best) mic with denoising filters."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_mics import ffmpeg_capture_timeout_s, ranked_audio_devices, require_audio_devices  # noqa: E402
from probe_mics import record_probe, wav_stats  # noqa: E402


def pick_best(seconds: float = 2.0) -> tuple[int, str]:
    all_devices = require_audio_devices()
    devices = ranked_audio_devices(all_devices, include_unreliable=False) or all_devices
    best = (-1.0, devices[0][0], devices[0][1])

    with tempfile.TemporaryDirectory() as td:
        for idx, name in devices:
            out = Path(td) / f"d{idx}.wav"
            ok = record_probe(idx, seconds, out)
            st = wav_stats(out) if ok else {"rms": 0.0, "peak": 0.0, "snr_like": 0.0}
            score = st["rms"] * float(np.log1p(st["snr_like"]))
            hung = "" if ok else " timed out"
            print(
                f"probe [{idx}] {name}: rms={st['rms']:.5f} peak={st['peak']:.5f} "
                f"score={score:.6f}{hung}"
            )
            if score > best[0]:
                best = (score, idx, name)
    return best[1], best[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", type=int, default=None, help="AVFoundation audio index")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--denoise",
        action="store_true",
        help="afftdn after capture (off by default so peak-picking keeps bass and partials)",
    )
    ap.add_argument("--no-denoise", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--probe-seconds", type=float, default=2.0)
    args = ap.parse_args()

    devices = {i: n for i, n in require_audio_devices()}
    if args.device is None:
        print("Auto-selecting lowest-noise / strongest mic...")
        device, name = pick_best(args.probe_seconds)
    else:
        device = args.device
        name = devices.get(device, f"device_{device}")

    captures = ROOT / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or captures / f"capture_{stamp}_dev{device}.wav"

    # Rumble-only highpass so A0–C2 stay in the 27.5–5000 Hz analysis range.
    # Keep lowpass under Nyquist for devices that capture at 24 kHz (e.g. Shannon).
    af = "highpass=f=25,lowpass=f=10000"
    if args.denoise:
        af += ",afftdn=nr=12:nf=-30"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        f":{device}",
        "-t",
        str(args.seconds),
        "-ac",
        "1",
        "-ar",
        "48000",
        "-af",
        af,
        str(out),
    ]
    print(f"Recording [{device}] {name} -> {out}")
    print(f"Filters: {af}")
    print("Play the music now.")
    try:
        proc = subprocess.run(cmd, timeout=ffmpeg_capture_timeout_s(args.seconds))
    except subprocess.TimeoutExpired:
        print("ERROR: ffmpeg capture timed out (Continuity/iPhone mics hang; use the MacBook mic).")
        raise SystemExit(2)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    st = wav_stats(out)
    print(f"Done. rms={st['rms']:.5f} peak={st['peak']:.5f}")
    if st["peak"] <= 0:
        print("ERROR: capture is silent. Grant mic access to Terminal/Cursor and retry.")
        raise SystemExit(2)
    print(out)


if __name__ == "__main__":
    main()
