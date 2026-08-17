#!/usr/bin/env python3
"""macOS input volume + default-device helpers for Écouter / ffmpeg.

Shannon (and similar interfaces) can stay the system default while capturing
digital silence. Browser getUserMedia follows that default; the TUI must not.
"""
from __future__ import annotations

import array
import argparse
import subprocess
import sys
import tempfile
import wave
from ctypes import (
    CDLL,
    POINTER,
    Structure,
    byref,
    c_int32,
    c_uint32,
    c_void_p,
    create_string_buffer,
    sizeof,
)
from pathlib import Path

from list_mics import (
    ffmpeg_capture_timeout_s,
    is_unreliable_audio_device,
    list_audio_devices,
    ranked_audio_devices,
)

MIN_INPUT_VOLUME = 50
TARGET_INPUT_VOLUME = 80
SILENT_PEAK = 1e-6

_COREAUDIO = None
_COREFOUNDATION = None
_ENSURED: str | None = None


def fourcc(code: str) -> int:
    if len(code) != 4:
        raise ValueError(f"fourcc must be 4 chars, got {code!r}")
    return int.from_bytes(code.encode("latin-1"), "big")


class AudioObjectPropertyAddress(Structure):
    _fields_ = [
        ("mSelector", c_uint32),
        ("mScope", c_uint32),
        ("mElement", c_uint32),
    ]


def pcm_s16le_is_silent(raw: bytes) -> bool:
    if len(raw) < 2:
        return True
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if not samples:
        return True
    return max(abs(s) for s in samples) == 0


def input_volume() -> int | None:
    try:
        proc = subprocess.run(
            ["osascript", "-e", "input volume of (get volume settings)"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return int(float(proc.stdout.strip()))
    except ValueError:
        return None


def set_input_volume(level: int) -> bool:
    level = max(0, min(100, int(level)))
    try:
        proc = subprocess.run(
            ["osascript", "-e", f"set volume input volume {level}"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _libs() -> tuple[CDLL, CDLL] | None:
    global _COREAUDIO, _COREFOUNDATION
    if sys.platform != "darwin":
        return None
    if _COREAUDIO is not None and _COREFOUNDATION is not None:
        return _COREAUDIO, _COREFOUNDATION
    try:
        ca = CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        cf = CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    except OSError:
        return None
    ca.AudioObjectGetPropertyDataSize.argtypes = [
        c_uint32,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        POINTER(c_uint32),
    ]
    ca.AudioObjectGetPropertyDataSize.restype = c_int32
    ca.AudioObjectGetPropertyData.argtypes = [
        c_uint32,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        POINTER(c_uint32),
        c_void_p,
    ]
    ca.AudioObjectGetPropertyData.restype = c_int32
    ca.AudioObjectSetPropertyData.argtypes = [
        c_uint32,
        POINTER(AudioObjectPropertyAddress),
        c_uint32,
        c_void_p,
        c_uint32,
        c_void_p,
    ]
    ca.AudioObjectSetPropertyData.restype = c_int32
    cf.CFStringGetCString.argtypes = [c_void_p, c_void_p, c_int32, c_uint32]
    cf.CFStringGetCString.restype = c_uint32
    cf.CFRelease.argtypes = [c_void_p]
    _COREAUDIO, _COREFOUNDATION = ca, cf
    return ca, cf


def _addr(selector: str, scope: str = "glob") -> AudioObjectPropertyAddress:
    return AudioObjectPropertyAddress(fourcc(selector), fourcc(scope), 0)


def _cf_string(cf: CDLL, ref: c_void_p) -> str:
    if not ref.value:
        return ""
    buf = create_string_buffer(1024)
    ok = cf.CFStringGetCString(ref, buf, 1024, 0x08000100)
    cf.CFRelease(ref)
    if not ok:
        return ""
    return buf.value.decode("utf-8", errors="replace")


def _device_name(ca: CDLL, cf: CDLL, dev: int) -> str:
    addr = _addr("lnam")
    ref = c_void_p()
    size = c_uint32(sizeof(c_void_p))
    err = ca.AudioObjectGetPropertyData(dev, byref(addr), 0, None, byref(size), byref(ref))
    if err != 0:
        return ""
    return _cf_string(cf, ref)


def _input_channel_count(ca: CDLL, dev: int) -> int:
    addr = _addr("stm#", "inpt")
    size = c_uint32(0)
    err = ca.AudioObjectGetPropertyDataSize(dev, byref(addr), 0, None, byref(size))
    if err != 0 or size.value == 0:
        return 0
    return max(1, size.value // sizeof(c_uint32))


def list_coreaudio_inputs() -> list[tuple[int, str]]:
    libs = _libs()
    if libs is None:
        return []
    ca, cf = libs
    addr = _addr("dev#")
    size = c_uint32(0)
    err = ca.AudioObjectGetPropertyDataSize(1, byref(addr), 0, None, byref(size))
    if err != 0 or size.value == 0:
        return []
    count = size.value // sizeof(c_uint32)
    devices = (c_uint32 * count)()
    err = ca.AudioObjectGetPropertyData(1, byref(addr), 0, None, byref(size), devices)
    if err != 0:
        return []
    found: list[tuple[int, str]] = []
    for dev in devices:
        if _input_channel_count(ca, int(dev)) <= 0:
            continue
        name = _device_name(ca, cf, int(dev))
        if name:
            found.append((int(dev), name))
    return found


def default_input_name() -> str:
    libs = _libs()
    if libs is None:
        return ""
    ca, cf = libs
    addr = _addr("dIn ")
    dev = c_uint32(0)
    size = c_uint32(sizeof(c_uint32))
    err = ca.AudioObjectGetPropertyData(1, byref(addr), 0, None, byref(size), byref(dev))
    if err != 0 or dev.value == 0:
        return ""
    return _device_name(ca, cf, int(dev.value))


def set_default_input(name: str) -> bool:
    if not name:
        return False
    libs = _libs()
    if libs is None:
        return False
    ca, _cf = libs
    for dev, found in list_coreaudio_inputs():
        if found != name:
            continue
        addr = _addr("dIn ")
        value = c_uint32(dev)
        err = ca.AudioObjectSetPropertyData(
            1, byref(addr), 0, None, sizeof(c_uint32), byref(value)
        )
        return err == 0
    return False


def probe_ffmpeg_peak(device: int, seconds: float = 0.3) -> float:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "probe.wav"
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
        except (OSError, subprocess.TimeoutExpired):
            return 0.0
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size < 64:
            return 0.0
        try:
            with wave.open(str(out), "rb") as w:
                raw = w.readframes(w.getnframes())
        except wave.Error:
            return 0.0
        samples = array.array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if not samples:
            return 0.0
        return max(abs(s) for s in samples) / 32768.0


def _ensure_input_volume(notes: list[str]) -> None:
    """Input gain is per-device; call this after the default input is correct."""
    vol = input_volume()
    if vol is not None and vol < MIN_INPUT_VOLUME:
        if set_input_volume(TARGET_INPUT_VOLUME):
            notes.append(f"input volume {vol}→{TARGET_INPUT_VOLUME}")
        else:
            notes.append(f"input volume {vol} (could not raise)")
    elif vol is not None:
        notes.append(f"input volume {vol}")


def _ffmpeg_index_for_name(name: str, devices: list[tuple[int, str]]) -> int | None:
    for idx, found in devices:
        if found == name:
            return idx
    return None


def ensure_macos_input() -> str:
    """Raise a too-low input gain and move the OS default off a silent/Continuity mic."""
    global _ENSURED
    if sys.platform != "darwin":
        return "skip"
    if _ENSURED is not None:
        return _ENSURED
    notes: list[str] = []
    current = default_input_name()
    av_devices = list_audio_devices()
    preferred = ranked_audio_devices(av_devices, include_unreliable=False)
    if not preferred:
        notes.append(current or "no default input")
        _ensure_input_volume(notes)
        _ENSURED = "; ".join(notes)
        return _ENSURED

    want_idx, want_name = preferred[0]
    silent_default = False
    if current and not is_unreliable_audio_device(current):
        cur_idx = _ffmpeg_index_for_name(current, av_devices)
        if cur_idx is not None:
            silent_default = probe_ffmpeg_peak(cur_idx) <= SILENT_PEAK
    should_switch = (
        not current
        or is_unreliable_audio_device(current)
        or silent_default
    )
    if should_switch and current != want_name:
        if set_default_input(want_name):
            notes.append(f"default input {current or '?'}→{want_name}")
        else:
            notes.append(f"default input still {current or '?'} (wanted {want_name})")
    else:
        notes.append(f"default input {current or want_name}")
    _ensure_input_volume(notes)
    notes.append(f"capture prefers [{want_idx}] {want_name}")
    _ENSURED = "; ".join(notes)
    return _ENSURED


def self_test() -> None:
    silent = b"\x00\x00" * 64
    if not pcm_s16le_is_silent(silent):
        raise SystemExit("all-zero PCM must be silent")
    if not pcm_s16le_is_silent(b""):
        raise SystemExit("empty PCM must be silent")
    loud = b"\x00\x00\x00\x10\x00\x00"
    if pcm_s16le_is_silent(loud):
        raise SystemExit("non-zero PCM must not be silent")
    if fourcc("dIn ") != 0x64496E20:
        raise SystemExit("default-input fourcc is wrong")
    print("macos_audio self-test: OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--ensure",
        action="store_true",
        help="raise low input volume and switch a silent/Continuity default mic",
    )
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if sys.platform != "darwin":
        print("macos_audio: not macOS")
        return
    print("CoreAudio inputs:")
    for dev, name in list_coreaudio_inputs():
        print(f"  id={dev} {name}")
    print(f"default input: {default_input_name() or '?'}")
    vol = input_volume()
    print(f"input volume: {vol if vol is not None else '?'}")
    if args.ensure:
        print("ensure:", ensure_macos_input())
        print(f"default input now: {default_input_name() or '?'}")
        print(f"input volume now: {input_volume()}")


if __name__ == "__main__":
    main()
