#!/usr/bin/env python3
"""Computer-keyboard → piano map + score store.

Physical keys use KeyboardEvent.code / scan-code names so Canadian French CSA
and US ANSI light the same piano keys. Notes follow the sequential crayon map
(KeyZ=Do3, KeyD=Do4, KeyQ=La4). Shared with web / iOS / TUI via
piano/ui_contract.json.
"""
from __future__ import annotations

import json
import locale
import os
import subprocess
from pathlib import Path
from typing import Literal

from dual_keyboard import CSA, NOTE_KIDS, US, midi_for_kid

LayoutId = Literal["us", "csa"]
Highlight = Literal["idle", "held", "need", "hit"]

# Sequential crayon map (same as dual_keyboard / DualNoteMap).
# KeyZ = Do3, home-row D = Do4, KeyQ = La4.
CODE_TO_MIDI: dict[str, int] = {
    kid: midi for kid in (*NOTE_KIDS, "IntlBackslash") if (midi := midi_for_kid(kid)) is not None
}

# Unshifted keycap glyphs. Letter keys match on US and CSA.
LABELS: dict[LayoutId, dict[str, str]] = {
    "us": {
        "KeyZ": "Z",
        "KeyS": "S",
        "KeyX": "X",
        "KeyD": "D",
        "KeyC": "C",
        "KeyV": "V",
        "KeyG": "G",
        "KeyB": "B",
        "KeyH": "H",
        "KeyN": "N",
        "KeyJ": "J",
        "KeyM": "M",
        "KeyQ": "Q",
        "Digit2": "2",
        "KeyW": "W",
        "Digit3": "3",
        "KeyE": "E",
        "KeyR": "R",
        "Digit5": "5",
        "KeyT": "T",
        "KeyY": "Y",
        "Digit6": "6",
        "Digit7": "7",
        "KeyU": "U",
        "KeyI": "I",
        "Digit9": "9",
        "KeyO": "O",
        "Digit0": "0",
        "KeyP": "P",
        "Slash": "/",
        "Backquote": "`",
        "BracketLeft": "[",
        "Quote": "'",
        "IntlBackslash": "\\",
    },
    "csa": {
        "KeyZ": "Z",
        "KeyS": "S",
        "KeyX": "X",
        "KeyD": "D",
        "KeyC": "C",
        "KeyV": "V",
        "KeyG": "G",
        "KeyB": "B",
        "KeyH": "H",
        "KeyN": "N",
        "KeyJ": "J",
        "KeyM": "M",
        "KeyQ": "Q",
        "Digit2": "2",
        "KeyW": "W",
        "Digit3": "3",
        "KeyE": "E",
        "KeyR": "R",
        "Digit5": "5",
        "KeyT": "T",
        "KeyY": "Y",
        "Digit6": "6",
        "Digit7": "7",
        "KeyU": "U",
        "KeyI": "I",
        "Digit9": "9",
        "KeyO": "O",
        "Digit0": "0",
        "KeyP": "P",
        "Slash": "é",
        "Backquote": "/",
        "BracketLeft": "^",
        "Quote": "`",
        "IntlBackslash": "ù",
    },
}

def _char_to_code(layout) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in layout.keys:
        if key.kind != "char" or not key.base:
            continue
        token = key.base.lower() if len(key.base) == 1 and key.base.isascii() else key.base
        out[token] = key.kid
    return out


CHAR_TO_CODE_US: dict[str, str] = _char_to_code(US)
CHAR_TO_CODE_CSA: dict[str, str] = _char_to_code(CSA)

POINTS_HIT = 10
STREAK_BONUS = 1
DEFAULT_SCORE_PATH = Path.home() / ".crayon_piano_scores.json"


def label_for(code: str, layout: LayoutId) -> str:
    return LABELS[layout].get(code, LABELS["us"].get(code, code))


def midi_for_code(code: str) -> int | None:
    return midi_for_kid(code)


def midi_for_char(char: str, layout: LayoutId) -> int | None:
    table = CHAR_TO_CODE_CSA if layout == "csa" else CHAR_TO_CODE_US
    code = table.get(char.lower() if len(char) == 1 and char.isascii() else char)
    if code is None and layout == "csa":
        code = CHAR_TO_CODE_US.get(char.lower())
    if code is None:
        return None
    return midi_for_code(code)


def infer_layout(code: str, key: str) -> LayoutId | None:
    """Guess CSA vs US from one physical key and the character it produced."""
    if not code or not key:
        return None
    if code == "Slash":
        if key == "é":
            return "csa"
        if key == "/":
            return "us"
    if code == "Backquote":
        if key in {"/", "#"}:
            return "csa"
        if key in {"`", "~"}:
            return "us"
    if code == "BracketLeft":
        if key == "^":
            return "csa"
        if key == "[":
            return "us"
    if code == "Quote":
        if key == "`":
            return "csa"
        if key in {"'", '"'}:
            return "us"
    if code == "IntlBackslash" and key == "ù":
        return "csa"
    return None


def detect_layout() -> LayoutId:
    hid = os.environ.get("CRAYON_KEYBOARD_LAYOUT", "").strip().lower()
    if hid in {"us", "csa"}:
        return hid  # type: ignore[return-value]
    try:
        out = subprocess.check_output(
            [
                "defaults",
                "read",
                "com.apple.HIToolbox",
                "AppleCurrentKeyboardLayoutInputSourceID",
            ],
            text=True,
            timeout=1.5,
        ).strip()
        low = out.lower()
        if "csa" in low or "canadian" in low:
            return "csa"
        if "us" in low or "abc" in low or "american" in low:
            return "us"
    except (OSError, subprocess.SubprocessError):
        pass
    loc = locale.getlocale()[0] or ""
    if loc.lower().startswith("fr_ca"):
        return "csa"
    return "us"


def highlight_state(midi: int, needed: set[int], pressed: set[int]) -> Highlight:
    want = midi in needed
    have = midi in pressed
    if want and have:
        return "hit"
    if want:
        return "need"
    if have:
        return "held"
    return "idle"


class ScoreKeeper:
    """One hit per needed-note appearance. Chart = current peak-picker midis."""

    def __init__(self) -> None:
        self.score = 0
        self.streak = 0
        self.needed: set[int] = set()
        self._awarded: set[int] = set()

    def set_needed(self, midis: set[int]) -> None:
        self.needed = set(midis)
        self._awarded &= self.needed
        if not self.needed:
            self.streak = 0

    def press(self, midi: int) -> Highlight:
        if midi in self.needed and midi not in self._awarded:
            self._awarded.add(midi)
            self.score += POINTS_HIT + self.streak * STREAK_BONUS
            self.streak += 1
            return "hit"
        if midi in self.needed:
            return "hit"
        return "held"

    def reset_session(self) -> None:
        self.score = 0
        self.streak = 0
        self.needed = set()
        self._awarded = set()


class ScoreStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_SCORE_PATH
        self.all_time = 0
        self.best_by_source: dict[str, int] = {}
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.all_time = int(data.get("allTime", 0) or 0)
        raw = data.get("bestBySource") or {}
        if isinstance(raw, dict):
            self.best_by_source = {str(k): int(v) for k, v in raw.items() if str(k)}

    def save(self) -> None:
        payload = {"allTime": self.all_time, "bestBySource": self.best_by_source}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record(self, source: str, score: int) -> bool:
        """Return True if this score is a new high (all-time or this source)."""
        improved = False
        if score > self.all_time:
            self.all_time = score
            improved = True
        key = source or "live"
        prev = self.best_by_source.get(key, 0)
        if score > prev:
            self.best_by_source[key] = score
            improved = True
        if improved:
            self.save()
        return improved

    def best_for(self, source: str) -> int:
        return max(self.all_time, self.best_by_source.get(source or "live", 0))


def main() -> None:
    if midi_for_code("KeyZ") != 48 or midi_for_code("KeyD") != 60 or midi_for_code("KeyQ") != 69:
        raise SystemExit("kid map required: Z=Do3 D=Do4 Q=La4")
    if midi_for_code("KeyA") != 58:
        raise SystemExit("KeyA is La♯3 on the sequential crayon map")
    if midi_for_char("q", "us") != 69 or midi_for_char("d", "csa") != 60:
        raise SystemExit("letter keys must follow the kid map on both layouts")
    if label_for("Slash", "csa") != "é" or label_for("Slash", "us") != "/":
        raise SystemExit("Slash glyph must differ CSA vs US")
    if infer_layout("Slash", "é") != "csa" or infer_layout("Slash", "/") != "us":
        raise SystemExit("infer_layout failed for Slash")
    if infer_layout("BracketLeft", "^") != "csa" or infer_layout("BracketLeft", "[") != "us":
        raise SystemExit("infer_layout failed for BracketLeft")
    if midi_for_char("é", "csa") is not None:
        pass
    if midi_for_char("q", "csa") != midi_for_char("q", "us"):
        raise SystemExit("letter keys must map to the same midi on CSA and US")
    if highlight_state(60, {60}, {60}) != "hit":
        raise SystemExit("need+press must be hit")
    if highlight_state(60, {60}, set()) != "need":
        raise SystemExit("need only")
    if highlight_state(60, set(), {60}) != "held":
        raise SystemExit("held only")
    keep = ScoreKeeper()
    keep.set_needed({60, 64})
    if keep.press(60) != "hit" or keep.score != POINTS_HIT:
        raise SystemExit("first hit should score")
    if keep.press(60) != "hit" or keep.score != POINTS_HIT:
        raise SystemExit("same appearance must not double-score")
    if keep.press(64) != "hit" or keep.score != POINTS_HIT + POINTS_HIT + STREAK_BONUS:
        raise SystemExit("streak bonus missing")
    keep.set_needed({67})
    if keep.press(67) != "hit":
        raise SystemExit("new target should score again")
    print(f"layout={detect_layout()} map={len(CODE_TO_MIDI)} keyboard_layout: OK")


if __name__ == "__main__":
    main()
