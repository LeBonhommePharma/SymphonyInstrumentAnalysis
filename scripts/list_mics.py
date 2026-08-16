#!/usr/bin/env python3
"""List AVFoundation audio devices via ffmpeg."""
from __future__ import annotations

import re
import subprocess

NO_DEVICES_MESSAGE = "No AVFoundation audio devices found."

# Continuity / iPhone-mirroring inputs enumerate in AVFoundation but ffmpeg
# often blocks forever on them (no samples, no error). Live listen skips these.
UNRELIABLE_AUDIO_RE = re.compile(
    r"iPhone|LPhone|Continuity|Desk View|\biPad\b|Apple Watch",
    re.I,
)


def list_audio_devices() -> list[tuple[int, str]]:
    proc = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    text = proc.stderr
    devices: list[tuple[int, str]] = []
    in_audio = False
    for line in text.splitlines():
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if in_audio and "AVFoundation video devices" in line:
            break
        if in_audio:
            m = re.search(r"\[(\d+)\]\s+(.+)$", line)
            if m:
                devices.append((int(m.group(1)), m.group(2).strip()))
    return devices


def is_unreliable_audio_device(name: str) -> bool:
    return bool(UNRELIABLE_AUDIO_RE.search(name))


def ffmpeg_capture_timeout_s(capture_seconds: float) -> float:
    """Hard cap so a Continuity mic cannot stall probe/record/smoke."""
    return max(2.5, float(capture_seconds) + 2.0)


def ranked_audio_devices(
    devices: list[tuple[int, str]] | None = None,
    *,
    include_unreliable: bool = True,
) -> list[tuple[int, str]]:
    """Built-in Mac mic first, other local mics next, Continuity last."""
    if devices is None:
        devices = list_audio_devices()

    def bucket(name: str) -> int:
        if is_unreliable_audio_device(name):
            return 2
        lowered = name.lower()
        if "macbook" in lowered or "built-in" in lowered:
            return 0
        return 1

    ordered = sorted(devices, key=lambda item: (bucket(item[1]), item[0]))
    if not include_unreliable:
        ordered = [item for item in ordered if not is_unreliable_audio_device(item[1])]
    return ordered


def require_audio_devices() -> list[tuple[int, str]]:
    devices = list_audio_devices()
    if not devices:
        print(NO_DEVICES_MESSAGE)
        raise SystemExit(1)
    return devices


def main() -> None:
    devices = require_audio_devices()
    print("Audio devices:")
    flaky = False
    for idx, name in devices:
        note = ""
        if is_unreliable_audio_device(name):
            flaky = True
            note = "  (Continuity — ffmpeg often hangs; live listen skips this)"
        print(f"  [{idx}] {name}{note}")
    if flaky:
        print("Prefer MacBook Pro Microphone (or Shannon) for Écouter / record_mic.py.")


if __name__ == "__main__":
    main()
