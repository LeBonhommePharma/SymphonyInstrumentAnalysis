#!/usr/bin/env python3
"""Piano-crayon — compact Textual TUI matching the HTML piano contract."""
from __future__ import annotations

import argparse
import math
import select
import subprocess
import sys
import threading
import time
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import cast

import numpy as np
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import HorizontalGroup
from textual.content import Content
from textual.style import Style
from textual.widget import Widget
from textual.widgets import Static

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_instruments import hz_to_note, load_wav
from density_cluster import cluster_peaks, heuristic_label
from chord_pitch_colors import NOTE_NAMES, PC_FR, PC_PENCIL, crayon_rgb
from list_mics import ranked_audio_devices
from keyboard_layout import (
    ScoreKeeper,
    ScoreStore,
    detect_layout,
    highlight_state,
    midi_for_char,
)
from crayon_piano_lib import (
    BLACK_MIDIS,
    SCENES,
    COLS_PER_SEC,
    ClusterTrackSet,
    current_scene,
    FFT_SIZE,
    MIDI_LO,
    MUSICIANS,
    SENS_DEFAULT,
    SPEC_F_LO,
    THEME_BG,
    THEME_INK,
    THEME_MUTED,
    THEME_PAPER,
    TOUS_RGB,
    WHITE_MIDIS,
    Mode,
    Musician,
    PeakPicker,
    RGB,
    TrackSet,
    apply_scene,
    chroma_fill_pct,
    clock_text,
    column_blocks,
    compute_band_envelopes,
    crayon_of,
    dim_rgb,
    envelope_at,
    fmt_time,
    freq_matches_cluster,
    hz_to_midi,
    lab_rgb,
    mix_rgb,
    midi_to_hz,
    octave_of,
    pc_of,
    playhead_frac,
    rfft_db,
    spec_x_of,
    synthesize_demo,
    tune_line,
    window_at,
)

FOOTER = "^L Écouter  ^R Rejouer  ^0 Tous  ^1–5  ^K Accords  ^U Entendre  ^A Auto  ^T Scène  PgUp/Dn Sens  ← →  Esc  ·  Z=Do3 D=Do4 Q=La4"
MIC_ERR = "Pas de micro / No mic — replay still works"


@lru_cache(maxsize=2048)
def rgb_style(
    fg: RGB | None = None,
    bg: RGB | None = None,
    *,
    bold: bool = False,
    dim: bool = False,
) -> Style:
    return Style(
        foreground=Color(*fg) if fg else None,
        background=Color(*bg) if bg else None,
        bold=bold,
        dim=dim,
    )


def cells_to_content(cells: list[tuple[str, Style]]) -> Content:
    if not cells:
        return Content("")
    parts: list[tuple[str, Style]] = []
    buf = [cells[0][0]]
    cur = cells[0][1]
    for ch, sty in cells[1:]:
        if sty == cur:
            buf.append(ch)
        else:
            parts.append(("".join(buf), cur))
            buf = [ch]
            cur = sty
    parts.append(("".join(buf), cur))
    return Content.assemble(*parts)


class RingBuffer:
    def __init__(self, n: int) -> None:
        self.n = n
        self.buf = np.zeros(n, dtype=np.float64)
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


def mic_ffmpeg_cmds(sr: int) -> list[list[str]]:
    """ffmpeg capture pipelines. macOS uses AVFoundation; Linux tries Pulse/ALSA/OpenAL."""
    rate = str(sr)
    pcm = ["-ac", "1", "-ar", rate, "-f", "s16le", "-"]
    head = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error"]
    cmds: list[list[str]] = []
    if sys.platform == "darwin":
        # Built-in Mac mic first. Continuity/iPhone inputs hang ffmpeg open().
        devices = ranked_audio_devices(include_unreliable=False) or ranked_audio_devices()
        indices = [idx for idx, _name in devices] or [0]
        for idx in indices[:4]:
            cmds.append([*head, "-f", "avfoundation", "-i", f":{idx}", *pcm])
    cmds.extend(
        [
            [*head, "-f", "pulse", "-i", "default", *pcm],
            [*head, "-f", "alsa", "-i", "default", *pcm],
            [*head, "-f", "openal", "-i", "", *pcm],
        ]
    )
    return cmds


FIRST_AUDIO_WAIT_S = 1.25


class MicStream:
    """Live capture via ffmpeg. On macOS this is AVFoundation (Ghostty / Terminal)."""

    def __init__(self, sr: int) -> None:
        self.sr = sr
        self.ring = RingBuffer(max(sr * 2, FFT_SIZE * 2))
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self.alive = False
        self.error = ""

    def start(self) -> str:
        self.stop()
        last_err = MIC_ERR
        for cmd in mic_ffmpeg_cmds(self.sr):
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                continue
            stdout = proc.stdout
            if stdout is None:
                proc.kill()
                continue
            ready, _, _ = select.select([stdout], [], [], FIRST_AUDIO_WAIT_S)
            if not ready or proc.poll() is not None:
                proc.kill()
                last_err = MIC_ERR
                continue
            raw = stdout.read1(4096) if hasattr(stdout, "read1") else stdout.read(4096)
            if not raw:
                proc.kill()
                last_err = MIC_ERR
                continue
            self.ring.push(np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0)
            self._proc = proc
            self.alive = True
            self.error = ""
            self._thread = threading.Thread(target=self._read, daemon=True)
            self._thread.start()
            return ""
        self.alive = False
        self.error = last_err
        return last_err

    def _read(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while self.alive and proc.poll() is None:
                raw = proc.stdout.read(4096)
                if not raw:
                    break
                samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
                self.ring.push(samples)
        except Exception:
            pass
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


class QuietPlayer:
    """Replay audio if the machine can play it; otherwise fail silently."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass

    def play(self, audio: np.ndarray, sr: int, offset: float, gain: float) -> None:
        self.stop()
        if gain <= 0:
            return
        i0 = int(max(0.0, offset) * sr)
        chunk = audio[i0:]
        if chunk.size == 0:
            return
        pcm = np.clip(chunk * gain * 32767.0, -32767, 32767).astype("<i2")
        try:
            proc = subprocess.Popen(
                [
                    "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                    "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return
        self._proc = proc

        def _feed() -> None:
            try:
                if proc.stdin is not None:
                    proc.stdin.write(pcm.tobytes())
                    proc.stdin.close()
                proc.wait(timeout=chunk.size / sr + 3.0)
            except Exception:
                pass

        threading.Thread(target=_feed, daemon=True).start()

    def play_tone(self, freq: float, sr: int, dur: float = 0.18) -> None:
        t = np.arange(int(sr * dur), dtype=np.float64) / sr
        env = np.minimum(1.0, t / 0.02) * np.exp(-t / 0.12)
        sig = 0.14 * env * (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t))
        self.play(sig, sr, 0.0, 1.0)


class Chip(Static):
    """One-line or two-line clickable control. No slider chrome."""

    DEFAULT_CSS = """
    Chip {
        width: auto;
        height: auto;
        padding: 0 1;
        content-align: center middle;
    }
    """

    def __init__(self, label: str, **kwargs: object) -> None:
        super().__init__(label, markup=False, **kwargs)  # type: ignore[arg-type]


class WaveStack(Widget):
    """Stacked filled envelopes — one lane per density cluster. No time slider."""

    DEFAULT_CSS = """
    WaveStack {
        width: 1fr;
        height: 1fr;
        min-height: 5;
        background: #18181c;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._dragging = False
        self._grab_x = 0
        self._grab_t = 0.0

    def render(self) -> Content:
        app = cast(CrayonPianoApp, self.app)
        width = max(8, self.size.width)
        height = max(1, self.size.height)
        lanes = app.active_cluster_lanes()
        n = max(1, len(lanes))
        lane_h = max(1, height // n)
        extra = height - lane_h * n
        t = app.view_time()
        mode = app.mode
        ph = int(round(playhead_frac(mode) * (width - 1)))
        lines: list[Content] = []
        if not lanes:
            lines.extend(self._empty_bed(width, height))
        for i, lane in enumerate(lanes):
            rows = lane_h + (1 if i < extra else 0)
            lines.extend(self._lane_lines(app, lane, width, rows, t, ph, mode))
        while len(lines) < height:
            lines.append(Content.blank(width, rgb_style(bg=THEME_PAPER)))
        joined = lines[0]
        for line in lines[1:]:
            joined = Content.assemble(joined, "\n", line)
        return joined

    def _empty_bed(self, width: int, height: int) -> list[Content]:
        paper = THEME_PAPER
        return [Content.blank(width, rgb_style(bg=paper)) for _ in range(height)]

    def _lane_lines(
        self,
        app: CrayonPianoApp,
        lane: dict,
        width: int,
        rows: int,
        t: float,
        ph: int,
        mode: Mode,
    ) -> list[Content]:
        midi = int(round(hz_to_midi(float(lane["f0"])))) if lane.get("f0") else MIDI_LO
        rgb = crayon_of(midi)
        rgb_future = dim_rgb(rgb, 0.38)
        paper = THEME_PAPER
        cols: list[list[str]] = [column_blocks(0.0, rows) for _ in range(width)]
        amps = [0.0] * width
        hist = app.live_hist.get(int(lane["id"]), deque())
        if mode in ("live", "replay", "idle"):
            for x in range(width):
                dt_cols = ph - x
                idx = len(hist) - 1 - dt_cols
                if 0 <= idx < len(hist):
                    amps[x] = hist[idx]
        else:
            raise RuntimeError(f"unhandled mode: {mode}")
        for x in range(width):
            cols[x] = column_blocks(amps[x], rows)
        out: list[Content] = []
        for r in range(rows):
            parts: list[tuple[str, Style]] = []
            for x in range(width):
                ch = cols[x][r]
                if mode == "live" or mode == "idle":
                    played = True
                elif mode == "replay":
                    played = (t + (x - ph) / COLS_PER_SEC) <= t
                else:
                    raise RuntimeError(f"unhandled mode: {mode}")
                color = rgb if played else rgb_future
                if x == ph:
                    if ch == " ":
                        ch = "│"
                        color = THEME_INK
                    else:
                        color = mix_rgb(rgb, (255, 255, 255), 0.22)
                parts.append((ch if ch != " " else " ", rgb_style(fg=color, bg=paper)))
            line = cells_to_content(parts)
            if r == 0:
                name = str(lane.get("label") or hz_to_note(float(lane.get("f0") or 0)) or "?")
                if len(name) > width - 2:
                    name = name[: max(1, width - 2)]
                overlay = Content.styled(name, rgb_style(fg=rgb, bg=paper, dim=True))
                line = overlay + line[len(name) :]
            out.append(line)
        return out

    def on_mouse_down(self, event: events.MouseDown) -> None:
        app = cast(CrayonPianoApp, self.app)
        if app.mode == "live":
            return
        event.stop()
        width = max(1, self.size.width)
        ph = playhead_frac(app.mode) * (width - 1)
        jumped = app.view_time() + (event.x - ph) / COLS_PER_SEC
        self._dragging = True
        self._grab_x = event.x
        self._grab_t = jumped
        app.seek_to(jumped, restart=True)
        self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        app = cast(CrayonPianoApp, self.app)
        if app.mode == "live":
            return
        dt = (event.x - self._grab_x) / COLS_PER_SEC
        app.seek_to(self._grab_t - dt, restart=True)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._end_drag()

    def on_mouse_release(self, event: events.MouseRelease) -> None:
        self._end_drag()

    def _end_drag(self) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.capture_mouse(False)
        app = cast(CrayonPianoApp, self.app)
        if app.mode == "replay":
            app._restart_playback()


class ChromaBars(Widget):
    DEFAULT_CSS = """
    ChromaBars {
        height: 4;
        background: #18181c;
    }
    """

    def render(self) -> Content:
        app = cast(CrayonPianoApp, self.app)
        width = max(12, self.size.width)
        height = max(2, self.size.height)
        bar_w = max(1, width // 12)
        used = bar_w * 12
        pad = width - used
        label_row = height - 1
        fill_rows = max(1, height - 1)
        lit_pcs = {pc_of(n.midi) for n in app.lit}
        grid = [[" " for _ in range(width)] for _ in range(height)]
        colors: list[list[RGB]] = [[THEME_PAPER for _ in range(width)] for _ in range(height)]
        for i, name in enumerate(NOTE_NAMES):
            rgb = crayon_rgb[name]
            pct = chroma_fill_pct(app.chroma.get(name, -120.0), app.abs_gate, lit_pcs, name)
            fill_h = pct / 100.0 * fill_rows
            x0 = i * bar_w
            lab = PC_FR[name]
            if len(lab) > bar_w:
                lab = lab[:bar_w]
            lab_x = x0 + max(0, (bar_w - len(lab)) // 2)
            for k, ch in enumerate(lab):
                if lab_x + k < width:
                    grid[label_row][lab_x + k] = ch
                    colors[label_row][lab_x + k] = rgb if name in lit_pcs else THEME_MUTED
            for r in range(fill_rows):
                from_bottom = fill_rows - r
                if from_bottom <= fill_h:
                    ch = "█"
                    if from_bottom - 1 < fill_h < from_bottom:
                        ch = "▄"
                    for x in range(x0, min(width, x0 + bar_w - (0 if bar_w == 1 else 1))):
                        grid[r][x] = ch
                        colors[r][x] = rgb
        lines: list[Content] = []
        for r in range(height):
            parts = []
            for x in range(width):
                bg = THEME_PAPER
                parts.append((grid[r][x], rgb_style(fg=colors[r][x], bg=bg)))
            extra = " " * pad if r == 0 else ""
            line = cells_to_content(parts)
            if extra:
                line = line + Content.styled(extra, rgb_style(bg=THEME_PAPER))
            lines.append(line)
        joined = lines[0]
        for line in lines[1:]:
            joined = Content.assemble(joined, "\n", line)
        return joined


class PianoBoard(Widget):
    DEFAULT_CSS = """
    PianoBoard {
        height: 3;
        background: #18181c;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._held: int | None = None

    def render(self) -> Content:
        app = cast(CrayonPianoApp, self.app)
        width = max(len(WHITE_MIDIS), self.size.width)
        height = max(2, self.size.height)
        ww = max(1, width // len(WHITE_MIDIS))
        idle_white = (42, 42, 46)
        idle_black = (26, 26, 28)
        needed = {n.midi for n in app.lit}
        pressed = set(app.held)
        rows: list[list[tuple[str, Style]]] = [
            [(" ", rgb_style(bg=THEME_PAPER)) for _ in range(width)] for _ in range(height)
        ]

        def paint_span(x0: int, w: int, y0: int, y1: int, ch: str, rgb: RGB, bg: RGB) -> None:
            fill = rgb_style(fg=rgb, bg=bg)
            for y in range(y0, min(height, y1)):
                for x in range(x0, min(width, x0 + w)):
                    rows[y][x] = (ch, fill)

        def key_look(midi: int, idle: RGB) -> tuple[str, RGB, RGB]:
            state = highlight_state(midi, needed, pressed)
            crayon = crayon_of(midi)
            if state == "hit":
                return ("◆", crayon, crayon)
            if state == "need":
                return ("█", crayon, crayon)
            if state == "held":
                return ("○", THEME_INK, mix_rgb(THEME_INK, idle, 0.35))
            return ("█", idle, idle)

        for wi, midi in enumerate(WHITE_MIDIS):
            x0 = wi * ww
            ch, rgb, bg = key_look(midi, idle_white)
            paint_span(x0, ww, 1 if height >= 3 else 0, height, ch, rgb, bg)
            if midi % 12 == 0 and ww >= 2 and height >= 2:
                octv = octave_of(midi)
                lab = f"Do{octv}" if ww >= 3 else str(octv)
                sty = rgb_style(fg=lab_rgb(rgb) if ch != "█" or rgb != idle_white else THEME_MUTED, bg=bg)
                y = height - 1
                for k, glyph in enumerate(lab[:ww]):
                    if x0 + k < width:
                        rows[y][x0 + k] = (glyph, sty)

        if height >= 2:
            bw = max(1, int(ww * 0.6) or 1)
            white_index = {m: i for i, m in enumerate(WHITE_MIDIS)}
            for midi in BLACK_MIDIS:
                prev = midi - 1
                while prev >= MIDI_LO and prev not in white_index:
                    prev -= 1
                if prev not in white_index:
                    continue
                wi = white_index[prev]
                x0 = (wi + 1) * ww - bw // 2
                ch, rgb, bg = key_look(midi, idle_black)
                paint_span(x0, bw, 0, max(1, height - 1), ch, rgb, bg)

        lines: list[Content] = []
        for y in range(height):
            lines.append(cells_to_content(rows[y]))
        joined = lines[0]
        for line in lines[1:]:
            joined = Content.assemble(joined, "\n", line)
        return joined

    def _midi_at(self, x: int, y: int) -> int | None:
        width = max(len(WHITE_MIDIS), self.size.width)
        height = max(2, self.size.height)
        ww = max(1, width // len(WHITE_MIDIS))
        if height >= 2 and y == 0:
            bw = max(1, int(ww * 0.6) or 1)
            white_index = {m: i for i, m in enumerate(WHITE_MIDIS)}
            for midi in BLACK_MIDIS:
                prev = midi - 1
                while prev >= MIDI_LO and prev not in white_index:
                    prev -= 1
                if prev not in white_index:
                    continue
                wi = white_index[prev]
                x0 = (wi + 1) * ww - bw // 2
                if x0 <= x < x0 + bw:
                    return midi
        wi = x // ww
        if 0 <= wi < len(WHITE_MIDIS):
            return WHITE_MIDIS[wi]
        return None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        midi = self._midi_at(event.x, event.y)
        if midi is None:
            return
        app = cast(CrayonPianoApp, self.app)
        app.hold_key(midi)
        self._held = midi
        self.capture_mouse()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._release()

    def on_mouse_release(self, event: events.MouseRelease) -> None:
        self._release()

    def _release(self) -> None:
        app = cast(CrayonPianoApp, self.app)
        if self._held is not None:
            app.release_key(self._held)
            self._held = None
        self.capture_mouse(False)


class CrayonPianoApp(App[None]):
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen {
        background: #121214;
        color: #9a9aa2;
        layout: vertical;
        overflow: hidden;
    }
    #title {
        height: 1;
        color: #c8c8d0;
        text-style: bold;
        padding: 0 1;
    }
    #actions, #toggles, #tracks {
        height: auto;
        padding: 0 1;
        background: #121214;
    }
    #actions { height: 1; }
    #toggles { height: 1; }
    #tracks { height: 2; }
    Chip {
        background: #1c1c20;
        color: #9a9aa2;
        height: 1;
    }
    Chip.-on {
        color: #c8c8d0;
        background: #2a2a32;
        text-style: bold;
    }
    Chip.-live {
        background: #1e2a18;
        color: #c8c8d0;
    }
    Chip.-playing {
        background: #1a2830;
        color: #c8c8d0;
    }
    #clock {
        width: 18;
        color: #9a9aa2;
        text-style: bold;
        padding: 0 1;
    }
    #tune {
        width: 1fr;
        color: #7a8a94;
        padding: 0 1;
    }
    .track {
        height: 2;
        min-width: 11;
        width: auto;
        margin: 0 1 0 0;
        padding: 0 1;
    }
    #lit {
        height: 1;
        padding: 0 1;
        background: #121214;
    }
    #err {
        height: 1;
        color: #8a4a4c;
        padding: 0 1;
        display: none;
    }
    #foot {
        height: 1;
        color: #6e6e76;
        padding: 0 1;
        background: #121214;
    }
    """
    BINDINGS = [
        Binding("ctrl+l", "listen", "Écouter", show=False, priority=True),
        Binding("ctrl+r", "replay", "Rejouer", show=False, priority=True),
        Binding("ctrl+0", "tous", "Tous", show=False, priority=True),
        Binding("ctrl+1", "cluster_n(1)", "1", show=False, priority=True),
        Binding("ctrl+2", "cluster_n(2)", "2", show=False, priority=True),
        Binding("ctrl+3", "cluster_n(3)", "3", show=False, priority=True),
        Binding("ctrl+4", "cluster_n(4)", "4", show=False, priority=True),
        Binding("ctrl+5", "cluster_n(5)", "5", show=False, priority=True),
        Binding("ctrl+k", "chords", "Accords", show=False, priority=True),
        Binding("ctrl+u", "unmute", "Entendre", show=False, priority=True),
        Binding("ctrl+a", "autotune", "Auto", show=False, priority=True),
        Binding("ctrl+t", "theme", "Scène", show=False, priority=True),
        Binding("pageup", "sens_down", "Sens−", show=False, priority=True),
        Binding("pagedown", "sens_up", "Sens+", show=False, priority=True),
        Binding("left", "seek_left", "←", show=False, priority=True),
        Binding("right", "seek_right", "→", show=False, priority=True),
        Binding("escape", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(
        self,
        audio: np.ndarray,
        sr: int,
        envelopes: dict[str, np.ndarray] | None = None,
        source_name: str = "demo",
    ) -> None:
        super().__init__()
        self.audio = np.asarray(audio, dtype=np.float64)
        self.sr = int(sr)
        self.duration = self.audio.size / self.sr if self.sr else 0.0
        self.envelopes = envelopes if envelopes is not None else compute_band_envelopes(
            self.audio, self.sr
        )
        self.tracks = ClusterTrackSet()
        self.live_clusters: list[dict] = []
        self.next_track_id = 1
        self.picker = PeakPicker()
        self.mode: Mode = "idle"
        self.sensitivity = SENS_DEFAULT
        self.chords_on = True
        self.unmute_on = False
        self.autotune_on = True
        self.sample_offset = 0.0
        self._replay_mono = 0.0
        self._live_mono = 0.0
        self.lit: list = []
        self.chroma = {n: -120.0 for n in NOTE_NAMES}
        self.abs_gate = -48.0
        self.held: set[int] = set()
        self.mic_error = ""
        self.live_hist: dict[int, deque[float]] = {}
        self.mic = MicStream(self.sr)
        self.player = QuietPlayer()
        self._last_seek_play = 0.0
        self.source_name = source_name
        self.layout = detect_layout()
        self.score = ScoreKeeper()
        self.score_store = ScoreStore()
        self._key_held: dict[int, float] = {}

    def compose(self) -> ComposeResult:
        yield Static("Piano-crayon", id="title")
        with HorizontalGroup(id="actions"):
            yield Chip("Rejouer", id="btn-replay")
            yield Chip("Écouter", id="btn-listen")
            yield Static(clock_text("idle", 0.0, self.duration, 0.0), id="clock")
            yield Static("La/A ≈ 440 Hz", id="tune")
            yield Static("", id="score")
        with HorizontalGroup(id="toggles"):
            yield Chip(self._sens_label(), id="tog-sens")
            yield Chip("c Accords", id="tog-chords", classes="-on")
            yield Chip("u Entendre", id="tog-unmute")
            yield Chip("a Auto-accord", id="tog-auto", classes="-on")
        with HorizontalGroup(id="tracks"):
            yield Chip("Tous\n27.5–5000 Hz", id="track-all", classes="track -on")
            yield HorizontalGroup(id="track-live")
        yield WaveStack(id="waves")
        yield ChromaBars(id="chroma")
        yield Static("", id="lit")
        yield PianoBoard(id="board")
        yield Static("", id="err")
        yield Static(FOOTER, id="foot")

    def on_mount(self) -> None:
        self._paint_tracks()
        self.set_interval(1 / 25, self._tick)
        self._refresh_chrome()

    def on_unmount(self) -> None:
        self.mic.stop()
        self.player.stop()

    def on_click(self, event: events.Click) -> None:
        wid = event.widget.id if event.widget is not None else None
        if not wid:
            return
        if wid == "btn-replay":
            event.stop()
            self.action_replay()
        elif wid == "btn-listen":
            event.stop()
            self.action_listen()
        elif wid == "tog-chords":
            event.stop()
            self.action_chords()
        elif wid == "tog-unmute":
            event.stop()
            self.action_unmute()
        elif wid == "tog-auto":
            event.stop()
            self.action_autotune()
        elif wid == "track-all":
            event.stop()
            self.action_tous()
        elif wid.startswith("track-"):
            event.stop()
            tail = wid.split("-", 1)[1]
            if tail.isdigit():
                self.action_cluster(int(tail))

    def _sens_label(self) -> str:
        return f"[ ] Sens {self.sensitivity}"

    def view_time(self) -> float:
        if self.mode == "replay":
            t = self.sample_offset + (time.monotonic() - self._replay_mono)
            return min(self.duration, max(0.0, t))
        if self.mode == "live":
            return time.monotonic() - self._live_mono
        if self.mode == "idle":
            return self.sample_offset
        raise RuntimeError(f"unhandled mode: {self.mode}")

    def sample_now(self) -> float:
        if self.mode == "replay":
            return self.view_time()
        if self.mode in ("idle", "live"):
            return self.sample_offset
        raise RuntimeError(f"unhandled mode: {self.mode}")

    def live_elapsed(self) -> float:
        if self.mode == "live":
            return time.monotonic() - self._live_mono
        return 0.0

    def seek_to(self, t: float, *, restart: bool) -> None:
        if self.mode == "live":
            return
        self.sample_offset = max(0.0, min(self.duration, t))
        if self.mode == "replay":
            self._replay_mono = time.monotonic()
            if restart:
                now = time.monotonic()
                if now - self._last_seek_play > 0.12:
                    self._last_seek_play = now
                    self._restart_playback()
        self._refresh_chrome()
        self.query_one("#waves", WaveStack).refresh()

    def action_listen(self) -> None:
        if self.mode == "live":
            self._stop_live()
            return
        if self.mode == "replay":
            self._stop_replay(keep=True)
        err = self.mic.start()
        if err:
            self.mic_error = err
            self.mode = "idle"
            self._show_err(err)
            self._refresh_chrome()
            return
        self.mic_error = ""
        self._show_err("")
        self.picker.reset()
        self.live_hist.clear()
        self.live_clusters = []
        self.mode = "live"
        self._live_mono = time.monotonic()
        self._refresh_chrome()

    def action_replay(self) -> None:
        if self.mode == "replay":
            self._stop_replay(keep=True)
            return
        if self.mode == "live":
            self._stop_live()
        self.picker.reset()
        if self.sample_offset >= self.duration - 0.05:
            self.sample_offset = 0.0
        self.mode = "replay"
        self._replay_mono = time.monotonic()
        self._restart_playback()
        self._refresh_chrome()

    def action_tous(self) -> None:
        self.tracks.select_all()
        self.picker.reset()
        self._paint_tracks()
        self.query_one("#waves", WaveStack).refresh()

    def action_cluster(self, ident: int) -> None:
        self.tracks.click(ident)
        self.picker.reset()
        self._paint_tracks()
        self.query_one("#waves", WaveStack).refresh()

    def action_cluster_n(self, n: int) -> None:
        if 1 <= n <= len(self.live_clusters):
            self.action_cluster(int(self.live_clusters[n - 1]["id"]))

    def action_chords(self) -> None:
        self.chords_on = not self.chords_on
        self._refresh_chrome()

    def action_unmute(self) -> None:
        self.unmute_on = not self.unmute_on
        if self.mode == "replay":
            if self.unmute_on:
                self._restart_playback()
            else:
                self.player.stop()
        self._refresh_chrome()

    def action_autotune(self) -> None:
        self.autotune_on = not self.autotune_on
        self.picker.reset()
        self._refresh_chrome()

    def action_theme(self) -> None:
        i = SCENES.index(current_scene()) if current_scene() in SCENES else 0
        name = apply_scene(SCENES[(i + 1) % len(SCENES)])
        colors = {
            "day": "#f6ead4",
            "light": "#eef1f5",
            "dark": "#1c1e24",
            "night": "#0d1220",
            "stealth": "#121214",
        }
        self.screen.styles.background = colors.get(name, "#121214")
        self._refresh_chrome()

    def action_sens_down(self) -> None:
        self.sensitivity = max(0, self.sensitivity - 5)
        self._refresh_chrome()

    def action_sens_up(self) -> None:
        self.sensitivity = min(100, self.sensitivity + 5)
        self._refresh_chrome()

    def action_seek_left(self) -> None:
        if self.mode == "live":
            return
        t = self.sample_now() if self.mode == "replay" else self.sample_offset
        if self.mode == "replay":
            self.sample_offset = t
        self.seek_to(t - 1.0, restart=True)

    def action_seek_right(self) -> None:
        if self.mode == "live":
            return
        t = self.sample_now() if self.mode == "replay" else self.sample_offset
        if self.mode == "replay":
            self.sample_offset = t
        self.seek_to(t + 1.0, restart=True)

    def hold_key(self, midi: int) -> None:
        self.held.add(midi)
        self.score.press(midi)
        try:
            self.player.play_tone(midi_to_hz(midi, self.picker.concert_a(self.autotune_on)), self.sr)
        except Exception:
            pass
        self.query_one("#board", PianoBoard).refresh()
        self._paint_lit()
        self._paint_score()

    def release_key(self, midi: int) -> None:
        self.held.discard(midi)
        self.query_one("#board", PianoBoard).refresh()
        self._paint_lit()

    def _stop_live(self) -> None:
        self._persist_score()
        self.score.reset_session()
        self.mic.stop()
        self.mode = "idle"
        self.lit = []
        self.chroma = {n: -120.0 for n in NOTE_NAMES}
        self._refresh_chrome()
        self.query_one("#waves", WaveStack).refresh()
        self.query_one("#chroma", ChromaBars).refresh()
        self.query_one("#board", PianoBoard).refresh()

    def _stop_replay(self, *, keep: bool) -> None:
        self._persist_score()
        self.score.reset_session()
        if self.mode == "replay":
            self.sample_offset = self.view_time() if keep else 0.0
        self.player.stop()
        if self.mode == "replay":
            self.mode = "idle"
        self.lit = []
        self.chroma = {n: -120.0 for n in NOTE_NAMES}
        self._refresh_chrome()
        self.query_one("#waves", WaveStack).refresh()
        self.query_one("#chroma", ChromaBars).refresh()
        self.query_one("#board", PianoBoard).refresh()

    def _restart_playback(self) -> None:
        if self.mode != "replay" or not self.unmute_on:
            self.player.stop()
            return
        try:
            self.player.play(self.audio, self.sr, self.sample_offset, 0.28)
        except Exception:
            pass

    def _show_err(self, msg: str) -> None:
        err = self.query_one("#err", Static)
        err.update(msg)
        err.display = bool(msg)

    def active_cluster_lanes(self) -> list[dict]:
        if not self.live_clusters:
            return []
        if self.tracks.is_tous():
            return list(self.live_clusters)
        return [t for t in self.live_clusters if self.tracks.is_on(int(t["id"]))]

    def _paint_tracks(self) -> None:
        tous = self.tracks.is_tous()
        all_chip = self.query_one("#track-all", Chip)
        all_chip.set_class(tous, "-on")
        all_chip.styles.background = Color(*(TOUS_RGB if tous else mix_rgb(TOUS_RGB, THEME_BG, 0.25)))
        all_chip.styles.color = Color(*THEME_INK)
        all_chip.update(f"Tous\n{len(self.live_clusters)} pistes")
        try:
            row = self.query_one("#track-live", HorizontalGroup)
        except Exception:
            return
        existing = {child.id: child for child in row.children if child.id}
        want = {f"track-{t['id']}" for t in self.live_clusters}
        for cid, widget in existing.items():
            if cid not in want:
                widget.remove()
        for t in self.live_clusters:
            cid = f"track-{t['id']}"
            midi = int(round(hz_to_midi(float(t["f0"])))) if t.get("f0") else MIDI_LO
            rgb = crayon_of(midi)
            label = f"{t.get('label') or hz_to_note(float(t['f0'])) or '?'}\n{int(round(t['f0']))} Hz"
            chip = existing.get(cid)
            if chip is None:
                chip = Chip(label, id=cid, classes="track")
                row.mount(chip)
            else:
                chip.update(label)
            on = tous or self.tracks.is_on(int(t["id"]))
            chip.set_class(on, "-on")
            if on:
                chip.styles.background = Color(*rgb)
                chip.styles.color = Color(*lab_rgb(rgb))
            else:
                chip.styles.background = Color(*mix_rgb(rgb, THEME_BG, 0.16))
                chip.styles.color = Color(*THEME_MUTED)

    def _refresh_chrome(self) -> None:
        try:
            replay = self.query_one("#btn-replay", Chip)
            listen = self.query_one("#btn-listen", Chip)
        except Exception:
            return
        replay.update("Stop" if self.mode == "replay" else "Rejouer")
        replay.set_class(self.mode == "replay", "-playing")
        listen.update("Stop" if self.mode == "live" else "Écouter")
        listen.set_class(self.mode == "live", "-live")
        t = self.view_time() if self.mode != "live" else self.sample_offset
        if self.mode == "replay":
            t = self.view_time()
        elif self.mode == "idle":
            t = self.sample_offset
        elif self.mode == "live":
            t = self.sample_offset
        else:
            raise RuntimeError(f"unhandled mode: {self.mode}")
        self.query_one("#clock", Static).update(
            clock_text(self.mode, t if self.mode != "live" else self.view_time(), self.duration, self.live_elapsed())
        )
        self.query_one("#tune", Static).update(
            tune_line(self.autotune_on, self.picker.a_est, self.picker.tune_ready, self.mode)
        )
        self.query_one("#tog-sens", Chip).update(self._sens_label())
        self.query_one("#tog-chords", Chip).set_class(self.chords_on, "-on")
        self.query_one("#tog-unmute", Chip).set_class(self.unmute_on, "-on")
        self.query_one("#tog-auto", Chip).set_class(self.autotune_on, "-on")
        self._paint_lit()
        self._paint_score()

    def _paint_lit(self) -> None:
        try:
            widget = self.query_one("#lit", Static)
        except Exception:
            return
        notes = sorted({n.midi for n in self.lit} | self.held)
        if not notes:
            widget.update("")
            return
        parts: list[tuple[str, Style] | str] = []
        for midi in notes:
            pc = pc_of(midi)
            rgb = crayon_rgb[pc]
            label = f" {PC_FR[pc]}{octave_of(midi)} "
            parts.append((label, rgb_style(fg=lab_rgb(rgb), bg=rgb, bold=True)))
            parts.append(" ")
        if self.lit:
            top = self.lit[0]
            parts.append(
                (
                    f"{PC_PENCIL[pc_of(top.midi)]} · {int(round(top.freq))} Hz",
                    rgb_style(fg=THEME_MUTED),
                )
            )
        widget.update(Content.assemble(*parts))

    def _paint_score(self) -> None:
        try:
            widget = self.query_one("#score", Static)
        except Exception:
            return
        src = "live" if self.mode == "live" else self.source_name
        best = self.score_store.best_for(src)
        widget.update(f"{self.score.score} · best {best} · {self.layout.upper()}")

    def _persist_score(self) -> None:
        src = "live" if self.mode == "live" else self.source_name
        if self.score.score > 0:
            self.score_store.record(src, self.score.score)

    def on_key(self, event: events.Key) -> None:
        if event.key.startswith(("ctrl+", "alt+", "meta+")):
            return
        ch = event.character or ""
        midi = midi_for_char(ch, self.layout) if ch else None
        if midi is None:
            return
        if midi not in self.held:
            self.hold_key(midi)
        self._key_held[midi] = time.monotonic()

    def _tick(self) -> None:
        if self.mode == "replay" and self.view_time() >= self.duration - 0.02:
            self.sample_offset = self.duration
            self._stop_replay(keep=True)
            return
        if self.mode == "live" and not self.mic.alive:
            self.mic_error = self.mic.error or MIC_ERR
            self._stop_live()
            self._show_err(self.mic_error)
            return
        now = time.monotonic()
        for midi, seen in list(self._key_held.items()):
            if now - seen > 0.18:
                self.release_key(midi)
                del self._key_held[midi]
        if self.mode in ("live", "replay"):
            self._analyze()
        self._refresh_chrome()
        self.query_one("#waves", WaveStack).refresh()
        self.query_one("#chroma", ChromaBars).refresh()
        self.query_one("#board", PianoBoard).refresh()

    def _analyze(self) -> None:
        if self.mode == "live":
            window = self.mic.latest(FFT_SIZE)
        elif self.mode == "replay":
            window = window_at(self.audio, self.sr, self.view_time())
        elif self.mode == "idle":
            return
        else:
            raise RuntimeError(f"unhandled mode: {self.mode}")
        spec, bin_hz = rfft_db(window, self.sr)
        now = time.monotonic()
        frame = self.picker.process(
            spec,
            bin_hz,
            self.tracks,
            chords=self.chords_on,
            sensitivity=self.sensitivity,
            autotune=self.autotune_on,
            now=now,
            live_clusters=self.live_clusters,
        )
        self.lit = frame.lit
        self.chroma = frame.chroma
        self.abs_gate = frame.abs_gate
        self.score.set_needed({n.midi for n in frame.lit})
        for midi in list(self.held):
            self.score.press(midi)
        clustered = cluster_peaks(frame.mix_peaks)
        self._sync_clusters(clustered, now)
        if frame.peaks and self.lit:
            self.lit[0].freq = frame.peaks[0][0]

    def _sync_clusters(self, clusters: list[dict], now: float) -> None:
        used: set[int] = set()
        for c in clusters:
            f0 = float(c["f0"])
            if f0 <= 0:
                continue
            best: dict | None = None
            best_cost = 0.45
            for t in self.live_clusters:
                if t["id"] in used or t["f0"] <= 0:
                    continue
                cost = abs(math.log2(f0 / float(t["f0"])))
                if cost < best_cost:
                    best_cost = cost
                    best = t
            energy = min(1.0, max(0.0, (float(c["db"]) + 80.0) / 50.0))
            if best is not None:
                used.add(int(best["id"]))
                best["f0"] = float(best["f0"]) * 0.55 + f0 * 0.45
                best["db"] = float(c["db"])
                best["harm"] = float(c["harm"])
                best["centroid"] = float(c.get("centroid") or f0)
                best["energy"] = energy
                best["last"] = now
                name = heuristic_label(best["f0"], best["harm"], best.get("centroid"))
                if name:
                    best["label"] = name
                self.live_hist.setdefault(int(best["id"]), deque(maxlen=400)).append(energy)
            else:
                tid = self.next_track_id
                self.next_track_id += 1
                centroid = float(c.get("centroid") or f0)
                label = heuristic_label(f0, float(c["harm"]), centroid) or hz_to_note(f0) or str(int(round(f0)))
                self.live_clusters.append(
                    {
                        "id": tid,
                        "f0": f0,
                        "db": float(c["db"]),
                        "harm": float(c["harm"]),
                        "centroid": centroid,
                        "energy": energy,
                        "last": now,
                        "label": label,
                    }
                )
                used.add(tid)
                self.live_hist.setdefault(tid, deque(maxlen=400)).append(energy)
        for t in self.live_clusters:
            if int(t["id"]) not in used:
                t["energy"] = float(t["energy"]) * 0.72
        self.live_clusters = [
            t
            for t in self.live_clusters
            if now - float(t["last"]) <= 1.4 and float(t["energy"]) >= 0.04
        ]
        live_ids = {int(t["id"]) for t in self.live_clusters}
        self.tracks.prune(live_ids)
        self.live_hist = {i: h for i, h in self.live_hist.items() if i in live_ids}
        self._paint_tracks()


def self_test() -> int:
    audio, sr = synthesize_demo()
    if audio.size < sr * 7:
        raise SystemExit("demo buffer too short")
    envelopes = compute_band_envelopes(audio, sr)
    if set(envelopes) != {m.id for m in MUSICIANS}:
        raise SystemExit(f"expected 5 envelopes, got {sorted(envelopes)}")
    bass = envelopes["bass"]
    if not np.any(bass > 0):
        raise SystemExit("bass envelope is zero on the 65 Hz demo")
    if column_blocks(1.0, 4).count("█") < 2:
        raise SystemExit("envelope columns should fill when amp=1")
    if fmt_time(8) != "0:08.0":
        raise SystemExit(f"bad clock {fmt_time(8)!r}")
    tracks = TrackSet()
    if not tracks.is_tous():
        raise SystemExit("default tracks should be Tous")
    tracks.click_musician("bass")
    if tracks.selected != {"bass"}:
        raise SystemExit("Tous + musician should solo")
    tracks.click_musician("cello")
    if tracks.selected != {"bass", "cello"}:
        raise SystemExit("second musician should union")
    tracks.click_musician("bass")
    tracks.click_musician("cello")
    if not tracks.is_tous():
        raise SystemExit("empty selection should snap to Tous")
    clusters = ClusterTrackSet()
    if not clusters.is_tous():
        raise SystemExit("density tracks default to Tous")
    clusters.click(1)
    if clusters.selected != {1}:
        raise SystemExit("Tous + cluster should solo")
    clusters.click(2)
    if clusters.selected != {1, 2}:
        raise SystemExit("second cluster should union")
    clusters.click(1)
    clusters.click(2)
    if not clusters.is_tous():
        raise SystemExit("empty cluster selection should snap to Tous")
    clusters.click(3)
    clusters.prune({1, 2})
    if not clusters.is_tous():
        raise SystemExit("dropping the last selected cluster should return to Tous")
    live = [{"id": 1, "f0": 110.0}, {"id": 2, "f0": 523.25}]
    clusters.click(1)
    if not freq_matches_cluster(220.0, 110.0):
        raise SystemExit("octave harmonic should match its cluster")
    if clusters.freq_in_active(523.25, live):
        raise SystemExit("solo bass cluster must not light the treble cluster")
    if not clusters.freq_in_active(110.0, live):
        raise SystemExit("solo bass cluster must keep its fundamental")
    if len(clusters.active_ids([1, 2, 3])) != 1:
        raise SystemExit("stacked lane count while soloing must follow the selection")
    clusters.select_all()
    if len(clusters.active_ids([1, 2, 3])) != 3:
        raise SystemExit("Tous stacked lane count must equal live cluster count")
    app = CrayonPianoApp(audio=audio, sr=sr, envelopes=envelopes)
    if app.mode != "idle" or "bass" not in app.envelopes:
        raise SystemExit("app did not instantiate with demo envelopes")
    if not isinstance(app.tracks, ClusterTrackSet):
        raise SystemExit("TUI tracks must be a ClusterTrackSet")

    x440 = spec_x_of(440.0)
    x_a0 = spec_x_of(SPEC_F_LO)
    if abs(x_a0) > 1e-12:
        raise SystemExit(f"A0 should sit at x=0, got {x_a0}")
    # A4 is exactly 4 octaves above A0, so x = 4 / log2(C8/A0)
    expect = 4.0 / np.log2((440.0 * (2.0 ** (39.0 / 12.0))) / SPEC_F_LO)
    if abs(x440 - expect) > 1e-9:
        raise SystemExit(f"440 Hz log-x {x440} != {expect}")
    if highlight_state(60, {60}, {60}) != "hit":
        raise SystemExit("highlight hit missing")
    if midi_for_char("q", "us") != 69 or midi_for_char("d", "us") != 60:
        raise SystemExit("TUI play-along must use the kid map (Q=La4 D=Do4)")
    if midi_for_char("q", "us") != midi_for_char("q", "csa"):
        raise SystemExit("CSA and US must share letter-key midis")
    bind_keys = {str(b.key) for b in CrayonPianoApp.BINDINGS}
    if "q" in bind_keys or "escape" not in bind_keys:
        raise SystemExit("TUI quit must be Escape so Q can play La4")
    if sys.platform == "darwin":
        cmds = mic_ffmpeg_cmds(48000)
        if not any("avfoundation" in cmd for cmd in cmds):
            raise SystemExit("macOS TUI listen must capture via AVFoundation")
        reliable = ranked_audio_devices(include_unreliable=False)
        if reliable:
            first_av = next(c for c in cmds if "avfoundation" in c)
            want = f":{reliable[0][0]}"
            if want not in first_av:
                raise SystemExit(f"TUI must open {reliable[0][1]} before Continuity mics")
    print("crayon_piano self-test: demo, 5 envelopes, bass>0, App() OK, 440Hz tick OK, layout OK")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Piano-crayon terminal UI")
    parser.add_argument("--wav", type=Path, default=None, help="16-bit PCM WAV")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    if args.wav is not None:
        audio, sr = load_wav(args.wav)
        source_name = args.wav.name
    else:
        audio, sr = synthesize_demo()
        source_name = "demo"
    envelopes = compute_band_envelopes(audio, sr)
    CrayonPianoApp(audio=audio, sr=sr, envelopes=envelopes, source_name=source_name).run()


if __name__ == "__main__":
    main()
