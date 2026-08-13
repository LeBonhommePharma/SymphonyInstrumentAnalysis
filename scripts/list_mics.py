#!/usr/bin/env python3
"""List AVFoundation audio devices via ffmpeg."""
from __future__ import annotations

import re
import subprocess

NO_DEVICES_MESSAGE = "No AVFoundation audio devices found."


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


def require_audio_devices() -> list[tuple[int, str]]:
    devices = list_audio_devices()
    if not devices:
        print(NO_DEVICES_MESSAGE)
        raise SystemExit(1)
    return devices


def main() -> None:
    devices = require_audio_devices()
    print("Audio devices:")
    for idx, name in devices:
        print(f"  [{idx}] {name}")


if __name__ == "__main__":
    main()
