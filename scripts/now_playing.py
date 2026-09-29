#!/usr/bin/env python3
"""Follow what is playing: stream playlists, ffmpeg PCM readers, macOS player state.

Three routes into the listening tools, honest per platform:

  DI.FM (any Icecast / Shoutcast / HLS URL) → decode the stream itself with ffmpeg
      python3 scripts/stream_bpm.py  --pls "DI.FM - Progressive Psy.pls"
      python3 scripts/crayon_piano.py --pls "DI.FM - Progressive Psy.pls"
  Spotify / Apple Music on this Mac → player state via AppleScript (osascript);
      audio through a loopback device (BlackHole, Loopback) when one exists,
      otherwise the built-in mic hears the speakers
      python3 scripts/crayon_piano.py --follow
  Anything on iPhone / iPad → the native app's Suivre toggle
      (AVAudioSession.isOtherAudioPlaying + the mic; iOS offers no other route)

A DI.FM .pls carries the premium listen key in the URL. It is a credential:
nothing here prints it (see mask_url), and *.pls / *.m3u are gitignored.
"""
from __future__ import annotations

import argparse
import re
import select
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np

LOOPBACK_RE = re.compile(
    r"blackhole|loopback|soundflower|vb-?audio|cable|stereo mix|stereo out|aggregate|multi-output|wave link|groundcontrol",
    re.I,
)
STREAM_URL_RE = re.compile(r"^(https?|rtmp|rtsp|hls)://", re.I)
FIRST_DATA_WAIT_S = 8.0
PLAYER_APPS = ("Spotify", "Music")


@dataclass(frozen=True)
class StreamEntry:
    url: str
    title: str

    @property
    def masked(self) -> str:
        return mask_url(self.url)


def mask_url(url: str) -> str:
    """Drop credentials: user:pass@ and the whole query string (DI.FM listen key)."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return "<url>"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    query = "?<key>" if parts.query else ""
    return urlunsplit((parts.scheme, host, parts.path, "", "")) + query


def is_stream_url(text: str) -> bool:
    return bool(STREAM_URL_RE.match(text.strip()))


def parse_playlist(text: str, *, name: str = "") -> list[StreamEntry]:
    """PLS (`[playlist]` + FileN/TitleN), M3U/M3U8 (#EXTINF + URL lines), or a bare URL."""
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    fallback = name or "stream"
    if any(ln.lower() == "[playlist]" for ln in lines):
        files: dict[int, str] = {}
        titles: dict[int, str] = {}
        for ln in lines:
            m = re.match(r"^(File|Title)(\d+)\s*=\s*(.*)$", ln, re.I)
            if not m:
                continue
            idx = int(m.group(2))
            if m.group(1).lower() == "file":
                files[idx] = m.group(3).strip()
            else:
                titles[idx] = m.group(3).strip()
        return [
            StreamEntry(files[i], titles.get(i) or fallback)
            for i in sorted(files)
            if is_stream_url(files[i])
        ]
    out: list[StreamEntry] = []
    pending_title = ""
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("#EXTINF"):
            pending_title = ln.split(",", 1)[1].strip() if "," in ln else ""
            continue
        if ln.startswith("#"):
            continue
        if is_stream_url(ln):
            out.append(StreamEntry(ln, pending_title or fallback))
            pending_title = ""
    return out


def load_playlist(path: Path) -> list[StreamEntry]:
    return parse_playlist(path.read_text(encoding="utf-8", errors="replace"), name=path.stem)


def stream_ffmpeg_cmd(url: str, sr: int) -> list[str]:
    """Decode any URL ffmpeg can open to mono s16le on stdout, reconnecting on drops."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        url,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(int(sr)),
        "-f",
        "s16le",
        "-",
    ]


def file_ffmpeg_cmd(path: Path, sr: int) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(int(sr)),
        "-f",
        "s16le",
        "-",
    ]


class RingBuffer:
    """Thread-safe float ring; `latest(m)` is zero-padded at the front."""

    def __init__(self, n: int) -> None:
        self.n = int(n)
        self.buf = np.zeros(self.n, dtype=np.float64)
        self.i = 0
        self.filled = 0
        self.lock = threading.Lock()

    def push(self, x: np.ndarray) -> None:
        if x.size == 0:
            return
        x = np.asarray(x, dtype=np.float64)
        k = x.size
        n = self.n
        with self.lock:
            if k >= n:
                self.buf[:] = x[-n:]
                self.i = 0
                self.filled = n
                return
            i = self.i
            end = i + k
            if end <= n:
                self.buf[i:end] = x
            else:
                first = n - i
                self.buf[i:] = x[:first]
                self.buf[: k - first] = x[first:]
            self.i = (i + k) % n
            self.filled = min(n, self.filled + k)

    def latest(self, m: int) -> np.ndarray:
        with self.lock:
            if self.filled <= 0:
                return np.zeros(m, dtype=np.float64)
            take = min(m, self.filled)
            out = np.zeros(m, dtype=np.float64)
            i = self.i
            start = (i - take) % self.n
            if start + take <= self.n:
                chunk = self.buf[start : start + take]
            else:
                first = self.n - start
                chunk = np.concatenate([self.buf[start:], self.buf[: take - first]])
            out[-take:] = chunk
            return out


class PcmReader:
    """Run an ffmpeg command that writes mono s16le to stdout; feed a ring and a sink.

    The sink receives every sample exactly once, in order, on the reader
    thread — that is what the BPM tracker needs (contiguous PCM), and what a
    `latest(n)` snapshot cannot promise.
    """

    def __init__(
        self,
        cmd: list[str],
        sr: int,
        *,
        sink=None,
        name: str = "",
        first_wait_s: float = FIRST_DATA_WAIT_S,
    ) -> None:
        self.cmd = list(cmd)
        self.sr = int(sr)
        self.sink = sink
        self.name = name or "flux"
        self.first_wait_s = float(first_wait_s)
        self.ring = RingBuffer(max(self.sr * 2, 16384))
        self.alive = False
        self.error = ""
        self.bytes_read = 0
        self.sink_error = ""
        self._carry = b""
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        self.stop()
        self.error = ""
        self.bytes_read = 0
        self._carry = b""
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            self.error = f"ffmpeg introuvable / not found: {exc}"
            return self.error
        stdout = proc.stdout
        if stdout is None:
            proc.kill()
            self.error = "ffmpeg: no stdout"
            return self.error
        first = self._wait_first(proc, stdout)
        if not first:
            proc.kill()
            tail = ""
            try:
                err = (proc.stderr.read() if proc.stderr else b"") or b""
                lines = [ln for ln in err.decode("utf-8", "replace").splitlines() if ln.strip()]
                tail = lines[-1].strip() if lines else ""
            except Exception:
                tail = ""
            self.error = f"{self.name}: pas de données / no data"
            if tail:
                self.error += f" — {tail}"
            return self.error
        self._proc = proc
        self.alive = True
        self._deliver(first)
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        return ""

    def _wait_first(self, proc: subprocess.Popen[bytes], stdout) -> bytes:
        deadline = time.monotonic() + self.first_wait_s
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([stdout], [], [], min(0.25, remaining))
            if not ready:
                if proc.poll() is not None:
                    return b""
                continue
            chunk = stdout.read1(8192) if hasattr(stdout, "read1") else stdout.read(8192)
            if not chunk:
                return b""
            return chunk
        return b""

    def _deliver(self, raw: bytes) -> None:
        data = self._carry + raw
        cut = len(data) - (len(data) % 2)
        self._carry = data[cut:]
        if cut <= 0:
            return
        samples = np.frombuffer(data[:cut], dtype="<i2").astype(np.float64) / 32768.0
        self.bytes_read += cut
        self.ring.push(samples)
        if self.sink is not None:
            try:
                self.sink(samples)
            except Exception as exc:  # never let a sink bug kill the reader thread
                self.sink_error = repr(exc)

    def _read(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while self.alive and proc.poll() is None:
                raw = proc.stdout.read(4096)
                if not raw:
                    break
                self._deliver(raw)
        except Exception:
            pass
        if self.alive and proc.poll() is not None and proc.returncode not in (0, None):
            self.error = f"{self.name}: ffmpeg exit {proc.returncode}"
        self.alive = False

    def stop(self) -> None:
        self.alive = False
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass

    def latest(self, n: int) -> np.ndarray:
        return self.ring.latest(n)


class StreamSource:
    """A URL (from a .pls / .m3u or typed) decoded live; same surface as the TUI mic."""

    def __init__(self, entry: StreamEntry, sr: int, *, sink=None) -> None:
        self.entry = entry
        self.sr = int(sr)
        self.reader = PcmReader(stream_ffmpeg_cmd(entry.url, sr), sr, sink=sink, name=entry.title)

    @property
    def alive(self) -> bool:
        return self.reader.alive

    @property
    def error(self) -> str:
        return self.reader.error

    @property
    def title(self) -> str:
        return self.entry.title

    def start(self) -> str:
        return self.reader.start()

    def stop(self) -> None:
        self.reader.stop()

    def latest(self, n: int) -> np.ndarray:
        return self.reader.latest(n)


# ── macOS: Spotify / Apple Music player state ───────────────────────────────
PLAYER_SCRIPT = """
set out to ""
if application "Spotify" is running then
\ttell application "Spotify"
\t\tset st to (player state as text)
\t\tset nm to ""
\t\tset ar to ""
\t\ttry
\t\t\tset nm to name of current track
\t\t\tset ar to artist of current track
\t\tend try
\t\tset out to out & "Spotify" & tab & st & tab & nm & tab & ar & linefeed
\tend tell
end if
if application "Music" is running then
\ttell application "Music"
\t\tset st to (player state as text)
\t\tset nm to ""
\t\tset ar to ""
\t\ttry
\t\t\tset nm to name of current track
\t\t\tset ar to artist of current track
\t\tend try
\t\tset out to out & "Music" & tab & st & tab & nm & tab & ar & linefeed
\tend tell
end if
return out
"""


@dataclass(frozen=True)
class PlayerState:
    app: str
    state: str
    title: str
    artist: str

    @property
    def playing(self) -> bool:
        return self.state.lower() == "playing"

    @property
    def label(self) -> str:
        app = "Apple Music" if self.app == "Music" else self.app
        if self.title and self.artist:
            return f"{app} · {self.artist} — {self.title}"
        if self.title:
            return f"{app} · {self.title}"
        return f"{app} · {self.state or 'running'}"


def parse_player_lines(text: str) -> list[PlayerState]:
    out: list[PlayerState] = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        cols = ln.split("\t")
        while len(cols) < 4:
            cols.append("")
        app, state, title, artist = (c.strip() for c in cols[:4])
        if app not in PLAYER_APPS:
            continue
        out.append(PlayerState(app, state.lower(), title, artist))
    return out


def player_states(timeout_s: float = 4.0) -> list[PlayerState]:
    """Ask the running Spotify / Music apps what they are doing (never launches them)."""
    if sys.platform != "darwin":
        return []
    try:
        proc = subprocess.run(
            ["osascript", "-"],
            input=PLAYER_SCRIPT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return parse_player_lines(proc.stdout)


@dataclass(frozen=True)
class FollowStatus:
    available: bool
    playing: bool
    label: str
    note: str = ""


def follow_status(states: list[PlayerState] | None = None) -> FollowStatus:
    if sys.platform != "darwin" and states is None:
        return FollowStatus(False, False, "", "--follow lit Spotify / Apple Music via osascript : macOS seulement.")
    if states is None:
        states = player_states()
    playing = [s for s in states if s.playing]
    if playing:
        return FollowStatus(True, True, playing[0].label)
    if states:
        return FollowStatus(True, False, states[0].label)
    return FollowStatus(True, False, "", "Spotify / Music ne tournent pas.")


# ── capture route for followed players ──────────────────────────────────────
def looks_loopback(name: str) -> bool:
    return bool(LOOPBACK_RE.search(name or ""))


def follow_capture_devices(devices: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Loopback devices first (they carry the other app's output), then the rest in order."""
    loop = [d for d in devices if looks_loopback(d[1])]
    rest = [d for d in devices if not looks_loopback(d[1])]
    return loop + rest


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    key = "0123456789abcdef0123456789abcdef"
    pls = (
        "[playlist]\nNumberOfEntries=2\n"
        f"File1=http://prem1.di.fm:80/progressivepsy_hi?{key}\nTitle1=DI.FM - Progressive Psy\nLength1=0\n"
        f"File2=http://prem4.di.fm:80/progressivepsy_hi?{key}\nTitle2=DI.FM - Progressive Psy\nLength2=0\n"
        "Version=2\n"
    )
    entries = parse_playlist(pls, name="station")
    if len(entries) != 2 or entries[0].title != "DI.FM - Progressive Psy":
        raise SystemExit(f"pls parse: {entries}")
    if key not in entries[0].url:
        raise SystemExit("pls parse must keep the real URL for ffmpeg")
    if key in entries[0].masked or entries[0].masked != "http://prem1.di.fm:80/progressivepsy_hi?<key>":
        raise SystemExit(f"mask_url must hide the listen key, got {entries[0].masked}")
    if mask_url("https://user:pw@host/path") != "https://host/path":
        raise SystemExit("mask_url must drop userinfo")
    m3u = "#EXTM3U\n#EXTINF:-1,Some Radio\nhttps://example.org/live.aac\nnot-a-url\n"
    e2 = parse_playlist(m3u, name="x")
    if len(e2) != 1 or e2[0].title != "Some Radio" or e2[0].url != "https://example.org/live.aac":
        raise SystemExit(f"m3u parse: {e2}")
    bare = parse_playlist("http://example.org/a.mp3\n", name="bare")
    if len(bare) != 1 or bare[0].title != "bare":
        raise SystemExit(f"bare url parse: {bare}")
    if parse_playlist("hello\n", name="x"):
        raise SystemExit("plain text is not a playlist")
    cmd = stream_ffmpeg_cmd(entries[0].url, 48000)
    if cmd[0] != "ffmpeg" or "s16le" not in cmd or entries[0].url not in cmd or "-reconnect" not in cmd:
        raise SystemExit(f"stream cmd: {cmd}")
    if "-vn" not in cmd or cmd[cmd.index("-ar") + 1] != "48000":
        raise SystemExit("stream cmd must drop video and resample to the tool rate")

    states = parse_player_lines(
        "Spotify\tplaying\tSong A\tArtist A\nMusic\tpaused\tSong B\tArtist B\nFinder\tx\t\t\n"
    )
    if len(states) != 2 or not states[0].playing or states[1].playing:
        raise SystemExit(f"player parse: {states}")
    fs = follow_status(states)
    if not fs.available or not fs.playing or fs.label != "Spotify · Artist A — Song A":
        raise SystemExit(f"follow status: {fs}")
    fs2 = follow_status([PlayerState("Music", "paused", "", "")])
    if fs2.playing or fs2.label != "Apple Music · paused":
        raise SystemExit(f"paused follow status: {fs2}")
    if follow_status([]).playing:
        raise SystemExit("no players must not read as playing")

    devs = [(0, "MacBook Pro Microphone"), (1, "BlackHole 2ch"), (2, "Shannon")]
    if follow_capture_devices(devs)[0][1] != "BlackHole 2ch":
        raise SystemExit("follow must prefer a loopback device")
    if looks_loopback("MacBook Pro Microphone") or not looks_loopback("Loopback Audio"):
        raise SystemExit("looks_loopback contract")

    ring = RingBuffer(8)
    ring.push(np.arange(1, 6, dtype=np.float64))
    ring.push(np.arange(6, 11, dtype=np.float64))
    if ring.latest(4).tolist() != [7.0, 8.0, 9.0, 10.0]:
        raise SystemExit(f"ring latest wrap: {ring.latest(4)}")
    if ring.latest(10).tolist()[:2] != [0.0, 0.0]:
        raise SystemExit("ring must zero-pad the front")

    got: list[np.ndarray] = []
    reader = PcmReader(["true"], 48000, sink=got.append, name="t")
    # 3 bytes: one sample (0x4000 = +0.5) and a dangling low byte that must wait.
    reader._deliver(b"\x00\x40\x00")
    if reader.bytes_read != 2 or len(got) != 1 or abs(got[0][0] - 0.5) > 1e-6 or reader._carry != b"\x00":
        raise SystemExit(f"pcm reader must carry an odd trailing byte: {reader.bytes_read} {got} {reader._carry!r}")
    # carry + 3 bytes = two samples: 0xc000 = −0.5, 0x8000 = −1.0, nothing left over.
    reader._deliver(b"\xc0\x00\x80")
    if reader.bytes_read != 6 or len(got) != 2 or got[1].tolist() != [-0.5, -1.0] or reader._carry != b"":
        raise SystemExit(f"pcm reader alignment: {reader.bytes_read} {got} {reader._carry!r}")
    print("now_playing self-test: OK (pls/m3u, key masked, player state, loopback first, pcm reader)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Playlist parsing and now-playing state helpers")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--pls", type=Path, default=None, help="print the entries of a .pls / .m3u (keys masked)")
    parser.add_argument("--players", action="store_true", help="print Spotify / Music player state (macOS)")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    if args.pls is not None:
        for i, e in enumerate(load_playlist(args.pls), 1):
            print(f"{i}. {e.title} — {e.masked}")
        return
    if args.players:
        fs = follow_status()
        if not fs.available:
            print(fs.note)
            raise SystemExit(1)
        print(f"playing={fs.playing} {fs.label or fs.note}")
        return
    parser.print_help()


if __name__ == "__main__":
    main()
