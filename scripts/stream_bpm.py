#!/usr/bin/env python3
"""Live BPM of a station, a URL, or a file — the counter without the piano.

    python3 scripts/stream_bpm.py --pls "DI.FM - Progressive Psy.pls"
    python3 scripts/stream_bpm.py --url https://example.org/live.aac --seconds 60
    python3 scripts/stream_bpm.py --wav captures/final_song.wav
    python3 scripts/stream_bpm.py --follow            # macOS: Spotify / Apple Music state + mic

ffmpeg decodes the source to mono PCM; scripts/bpm_tracker.py counts. One
line refreshes twice a second:

    DI.FM - Progressive Psy · ♩ 140 BPM · conf 0.61 · collapse 0.38 · 0:42

The .pls listen key is a credential: the URL is printed masked, only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from bpm_tracker import BpmState, BpmTracker, bpm_text, synth_beat  # noqa: E402
from now_playing import (  # noqa: E402
    PcmReader,
    StreamEntry,
    file_ffmpeg_cmd,
    follow_status,
    is_stream_url,
    load_playlist,
    stream_ffmpeg_cmd,
)

SR = 48000
PRINT_EVERY_S = 0.5


def fmt_clock(seconds: float) -> str:
    t = max(0.0, seconds)
    m = int(t // 60)
    return f"{m}:{int(t - m * 60):02d}"


def status_line(title: str, state: BpmState, elapsed: float, follow_label: str = "") -> str:
    parts = [title]
    if follow_label:
        parts.append(follow_label)
    parts.append(bpm_text(state).replace("♩ ", "♩ ") + (" BPM" if state.ready else ""))
    if state.ready:
        parts.append(f"conf {state.confidence:.2f}")
        parts.append(f"collapse {state.collapse:.2f}")
    parts.append(fmt_clock(elapsed))
    return " · ".join(parts)


def status_json(title: str, state: BpmState, elapsed: float, follow_label: str = "") -> str:
    return json.dumps(
        {
            "source": title,
            "now_playing": follow_label or None,
            "bpm": round(state.bpm, 1) if state.ready and state.bpm else None,
            "ready": state.ready,
            "confidence": round(state.confidence, 3),
            "collapse": round(state.collapse, 3),
            "analysed_s": round(state.seconds, 1),
            "elapsed_s": round(elapsed, 1),
        },
        ensure_ascii=False,
    )


def pick_entry(args: argparse.Namespace) -> tuple[list[str], str] | None:
    """(ffmpeg command, title) for --pls / --url / --wav; None for --follow-only or nothing."""
    if args.pls is not None:
        entries = load_playlist(args.pls)
        if not entries:
            raise SystemExit(f"{args.pls}: no stream URL found")
        idx = max(1, min(len(entries), args.entry)) - 1
        e = entries[idx]
        return stream_ffmpeg_cmd(e.url, SR), e.title
    if args.url:
        if not is_stream_url(args.url):
            raise SystemExit("--url must start with http://, https://, rtmp:// or rtsp://")
        return stream_ffmpeg_cmd(args.url, SR), StreamEntry(args.url, "stream").masked
    if args.wav is not None:
        if not args.wav.is_file():
            raise SystemExit(f"{args.wav}: not a file")
        return file_ffmpeg_cmd(args.wav, SR), args.wav.name
    return None


def run(args: argparse.Namespace) -> int:
    picked = pick_entry(args)
    if picked is None and not args.follow:
        raise SystemExit("give --pls FILE, --url URL, --wav FILE, or --follow")
    tracker = BpmTracker(SR)
    reader: PcmReader | None = None
    title = ""
    if picked is not None:
        cmd, title = picked
        reader = PcmReader(cmd, SR, sink=tracker.push, name=title)
        err = reader.start()
        if err:
            print(err, file=sys.stderr)
            return 2
    elif args.follow:
        # Follow-only: the mic (or loopback) is the audio route; player state is the label.
        from crayon_piano import MicStream  # noqa: E402  (lazy: needs textual)

        mic = MicStream(SR)
        mic.sink = tracker.push
        err = mic.start()
        if err:
            print(err, file=sys.stderr)
            return 2
        reader = mic  # type: ignore[assignment]
        title = "micro"
    t0 = time.monotonic()
    ended_early = False
    last_print = 0.0
    last_follow = 0.0
    follow_label = ""
    out = sys.stdout
    try:
        while True:
            now = time.monotonic()
            elapsed = now - t0
            if reader is not None and not reader.alive:
                # EOF (a file, or a station that hung up) — say so, then print the final count.
                err = getattr(reader, "error", "")
                if not args.json:
                    out.write("\n")
                print(err or f"{title}: fin du flux / end of stream", file=sys.stderr)
                ended_early = bool(err)
                break
            if args.follow and now - last_follow >= 1.5:
                last_follow = now
                fs = follow_status()
                follow_label = fs.label if fs.available else fs.note
            if now - last_print >= PRINT_EVERY_S:
                last_print = now
                state = tracker.snapshot()
                if args.json:
                    out.write(status_json(title, state, elapsed, follow_label) + "\n")
                else:
                    out.write("\r\x1b[2K" + status_line(title, state, elapsed, follow_label))
                out.flush()
            if args.seconds and elapsed >= args.seconds:
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        if reader is not None:
            reader.stop()
    state = tracker.snapshot()
    if args.json:
        out.write(status_json(title, state, time.monotonic() - t0, follow_label) + "\n")
    else:
        out.write("\r\x1b[2K" + status_line(title, state, time.monotonic() - t0, follow_label) + "\n")
    out.flush()
    if ended_early:
        return 1
    return 0 if state.ready else 3


def self_test() -> int:
    tracker = BpmTracker(SR)
    audio = synth_beat(SR, 9.0, 140.0)
    # Feed through PcmReader._deliver as s16le, the way ffmpeg bytes arrive.
    import numpy as np

    reader = PcmReader(["true"], SR, sink=tracker.push, name="synth")
    pcm = np.clip(audio * 32767.0, -32767, 32767).astype("<i2").tobytes()
    for i in range(0, len(pcm), 4096):
        reader._deliver(pcm[i : i + 4096])
    state = tracker.snapshot()
    if not state.ready or state.bpm is None or abs(state.bpm - 140.0) > 1.5:
        raise SystemExit(f"s16le path should read 140 BPM, got {state}")
    line = status_line("DI.FM - Progressive Psy", state, 42.0)
    if "♩ 140 BPM" not in line or "0:42" not in line or "conf" not in line:
        raise SystemExit(f"status line: {line}")
    js = json.loads(status_json("x", state, 3.0, "Spotify · A — B"))
    if js["bpm"] != 140.0 and abs(js["bpm"] - 140.0) > 1.5:
        raise SystemExit(f"status json: {js}")
    if js["now_playing"] != "Spotify · A — B":
        raise SystemExit("status json must carry the now-playing label")
    quiet = status_line("x", BpmTracker(SR).snapshot(), 1.0)
    if "♩ …" not in quiet or "conf" in quiet:
        raise SystemExit(f"settling status line: {quiet}")
    ns = argparse.Namespace(pls=None, url="http://example.org/a.mp3", wav=None, entry=1, follow=False)
    cmd, title = pick_entry(ns)
    if title != "http://example.org/a.mp3" or cmd[-1] != "-":
        raise SystemExit(f"pick_entry url: {cmd} {title}")
    ns_key = argparse.Namespace(pls=None, url="http://h/p?secretkey", wav=None, entry=1, follow=False)
    _cmd, title = pick_entry(ns_key)
    if "secretkey" in title or title != "http://h/p?<key>":
        raise SystemExit(f"--url title must mask the key: {title}")
    print(f"stream_bpm self-test: OK ({state.bpm:.1f} BPM through the s16le path, key masked)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Live BPM of a stream, station playlist, or file")
    parser.add_argument("--pls", type=Path, default=None, help=".pls / .m3u / .m3u8 (DI.FM export)")
    parser.add_argument("--entry", type=int, default=1, help="which playlist entry (1-based)")
    parser.add_argument("--url", default="", help="stream URL ffmpeg can open")
    parser.add_argument("--wav", type=Path, default=None, help="local audio file (any ffmpeg format)")
    parser.add_argument("--follow", action="store_true", help="macOS: label with Spotify / Apple Music state")
    parser.add_argument("--seconds", type=float, default=0.0, help="stop after N seconds (0 = until Ctrl-C)")
    parser.add_argument("--json", action="store_true", help="one JSON object per line instead of a status line")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
