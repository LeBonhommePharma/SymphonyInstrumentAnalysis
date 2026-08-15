#!/usr/bin/env python3
"""US ANSI + Canadian French CSA keyboards, and the 10-finger cluster gate.

Two standard layouts sit side by side. A person has 10 fingers, so an 11th
independent key-down is rejected — unless that key is well clustered with keys
already held (adjacent on the same board). Lane / track count follows those
spatial density clusters, not a fixed instrument parameter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_FINGERS = 10
# Adjacent same-row/column centers are 1.0u. Diagonals are ~1.41u.
# Keep neighbors in one cluster; leave a one-key gap as two fingers.
CLUSTER_EPS = 1.20
BOARD_GAP = 18.0


@dataclass(frozen=True)
class KeySpec:
    kid: str
    row: float
    col: float
    w: float = 1.0
    h: float = 1.0
    kind: str = "char"  # char | shift | caps | alt | altgr | ctrl | tab | enter | backspace | space
    base: str = ""
    shift: str = ""
    altgr: str = ""
    dead: str = ""  # dead-key id when unshifted (and shift_dead when shifted)
    shift_dead: str = ""
    code: str = ""  # KeyboardEvent.code


@dataclass
class Layout:
    id: str
    name: str
    name_fr: str
    geometry: str
    keys: tuple[KeySpec, ...]
    x0: float = 0.0

    def by_id(self) -> dict[str, KeySpec]:
        return {k.kid: k for k in self.keys}

    def by_code(self) -> dict[str, KeySpec]:
        return {k.code: k for k in self.keys if k.code}

    def center(self, key: KeySpec) -> tuple[float, float]:
        return (self.x0 + key.col + key.w / 2.0, key.row + key.h / 2.0)


def _k(
    kid: str,
    row: float,
    col: float,
    w: float = 1.0,
    *,
    kind: str = "char",
    base: str = "",
    shift: str = "",
    altgr: str = "",
    dead: str = "",
    shift_dead: str = "",
    code: str = "",
    h: float = 1.0,
) -> KeySpec:
    return KeySpec(
        kid=kid,
        row=row,
        col=col,
        w=w,
        h=h,
        kind=kind,
        base=base,
        shift=shift,
        altgr=altgr,
        dead=dead,
        shift_dead=shift_dead,
        code=code or kid,
    )


def _us_ansi() -> Layout:
    row0 = [
        _k("Backquote", 0, 0, base="`", shift="~"),
        _k("Digit1", 0, 1, base="1", shift="!"),
        _k("Digit2", 0, 2, base="2", shift="@"),
        _k("Digit3", 0, 3, base="3", shift="#"),
        _k("Digit4", 0, 4, base="4", shift="$"),
        _k("Digit5", 0, 5, base="5", shift="%"),
        _k("Digit6", 0, 6, base="6", shift="^"),
        _k("Digit7", 0, 7, base="7", shift="&"),
        _k("Digit8", 0, 8, base="8", shift="*"),
        _k("Digit9", 0, 9, base="9", shift="("),
        _k("Digit0", 0, 10, base="0", shift=")"),
        _k("Minus", 0, 11, base="-", shift="_"),
        _k("Equal", 0, 12, base="=", shift="+"),
        _k("Backspace", 0, 13, 2.0, kind="backspace", base="⌫"),
    ]
    row1 = [
        _k("Tab", 1, 0, 1.5, kind="tab", base="⇥"),
        _k("KeyQ", 1, 1.5, base="q", shift="Q"),
        _k("KeyW", 1, 2.5, base="w", shift="W"),
        _k("KeyE", 1, 3.5, base="e", shift="E"),
        _k("KeyR", 1, 4.5, base="r", shift="R"),
        _k("KeyT", 1, 5.5, base="t", shift="T"),
        _k("KeyY", 1, 6.5, base="y", shift="Y"),
        _k("KeyU", 1, 7.5, base="u", shift="U"),
        _k("KeyI", 1, 8.5, base="i", shift="I"),
        _k("KeyO", 1, 9.5, base="o", shift="O"),
        _k("KeyP", 1, 10.5, base="p", shift="P"),
        _k("BracketLeft", 1, 11.5, base="[", shift="{"),
        _k("BracketRight", 1, 12.5, base="]", shift="}"),
        _k("Backslash", 1, 13.5, 1.5, base="\\", shift="|"),
    ]
    row2 = [
        _k("CapsLock", 2, 0, 1.75, kind="caps", base="⇪"),
        _k("KeyA", 2, 1.75, base="a", shift="A"),
        _k("KeyS", 2, 2.75, base="s", shift="S"),
        _k("KeyD", 2, 3.75, base="d", shift="D"),
        _k("KeyF", 2, 4.75, base="f", shift="F"),
        _k("KeyG", 2, 5.75, base="g", shift="G"),
        _k("KeyH", 2, 6.75, base="h", shift="H"),
        _k("KeyJ", 2, 7.75, base="j", shift="J"),
        _k("KeyK", 2, 8.75, base="k", shift="K"),
        _k("KeyL", 2, 9.75, base="l", shift="L"),
        _k("Semicolon", 2, 10.75, base=";", shift=":"),
        _k("Quote", 2, 11.75, base="'", shift='"'),
        _k("Enter", 2, 12.75, 2.25, kind="enter", base="⏎"),
    ]
    row3 = [
        _k("ShiftLeft", 3, 0, 2.25, kind="shift", base="⇧"),
        _k("KeyZ", 3, 2.25, base="z", shift="Z"),
        _k("KeyX", 3, 3.25, base="x", shift="X"),
        _k("KeyC", 3, 4.25, base="c", shift="C"),
        _k("KeyV", 3, 5.25, base="v", shift="V"),
        _k("KeyB", 3, 6.25, base="b", shift="B"),
        _k("KeyN", 3, 7.25, base="n", shift="N"),
        _k("KeyM", 3, 8.25, base="m", shift="M"),
        _k("Comma", 3, 9.25, base=",", shift="<"),
        _k("Period", 3, 10.25, base=".", shift=">"),
        _k("Slash", 3, 11.25, base="/", shift="?"),
        _k("ShiftRight", 3, 12.25, 2.75, kind="shift", base="⇧"),
    ]
    row4 = [
        _k("ControlLeft", 4, 0, 1.5, kind="ctrl", base="ctrl"),
        _k("AltLeft", 4, 1.5, 1.5, kind="alt", base="alt"),
        _k("Space", 4, 3.0, 9.0, kind="space", base=" "),
        _k("AltRight", 4, 12.0, 1.5, kind="alt", base="alt"),
        _k("ControlRight", 4, 13.5, 1.5, kind="ctrl", base="ctrl"),
    ]
    return Layout(
        id="us",
        name="US",
        name_fr="É.-U.",
        geometry="ansi",
        keys=tuple(row0 + row1 + row2 + row3 + row4),
        x0=0.0,
    )


def _csa_iso() -> Layout:
    """Canadian Multilingual Standard / CSA on ISO 105 — usable French + English."""
    row0 = [
        _k("Backquote", 0, 0, base="/", shift="\\", altgr="|"),
        _k("Digit1", 0, 1, base="1", shift="!", altgr="¹"),
        _k("Digit2", 0, 2, base="2", shift="@", altgr="²"),
        _k("Digit3", 0, 3, base="3", shift="#", altgr="³"),
        _k("Digit4", 0, 4, base="4", shift="$", altgr="¼"),
        _k("Digit5", 0, 5, base="5", shift="%", altgr="½"),
        _k("Digit6", 0, 6, base="6", shift="?", altgr="¾"),
        _k("Digit7", 0, 7, base="7", shift="&", altgr="{"),
        _k("Digit8", 0, 8, base="8", shift="*", altgr="}"),
        _k("Digit9", 0, 9, base="9", shift="(", altgr="["),
        _k("Digit0", 0, 10, base="0", shift=")", altgr="]"),
        _k("Minus", 0, 11, base="-", shift="_", altgr="¬"),
        _k("Equal", 0, 12, base="=", shift="+", altgr="±"),
        _k("Backspace", 0, 13, 2.0, kind="backspace", base="⌫"),
    ]
    row1 = [
        _k("Tab", 1, 0, 1.5, kind="tab", base="⇥"),
        _k("KeyQ", 1, 1.5, base="q", shift="Q"),
        _k("KeyW", 1, 2.5, base="w", shift="W"),
        _k("KeyE", 1, 3.5, base="e", shift="E", altgr="€"),
        _k("KeyR", 1, 4.5, base="r", shift="R"),
        _k("KeyT", 1, 5.5, base="t", shift="T"),
        _k("KeyY", 1, 6.5, base="y", shift="Y"),
        _k("KeyU", 1, 7.5, base="u", shift="U"),
        _k("KeyI", 1, 8.5, base="i", shift="I"),
        _k("KeyO", 1, 9.5, base="o", shift="O", altgr="œ"),
        _k("KeyP", 1, 10.5, base="p", shift="P"),
        _k("BracketLeft", 1, 11.5, base="^", shift="¨", dead="circ", shift_dead="uml"),
        _k("BracketRight", 1, 12.5, base="¸", shift="ˇ", dead="cedilla", shift_dead="caron"),
        _k("Enter", 1, 13.5, 1.5, h=2.0, kind="enter", base="⏎"),
    ]
    # ISO enter sits on rows 1–2; the extra ISO key is left of Z (IntlBackslash).
    row2 = [
        _k("CapsLock", 2, 0, 1.75, kind="caps", base="⇪"),
        _k("KeyA", 2, 1.75, base="a", shift="A", altgr="æ"),
        _k("KeyS", 2, 2.75, base="s", shift="S"),
        _k("KeyD", 2, 3.75, base="d", shift="D"),
        _k("KeyF", 2, 4.75, base="f", shift="F"),
        _k("KeyG", 2, 5.75, base="g", shift="G"),
        _k("KeyH", 2, 6.75, base="h", shift="H"),
        _k("KeyJ", 2, 7.75, base="j", shift="J"),
        _k("KeyK", 2, 8.75, base="k", shift="K"),
        _k("KeyL", 2, 9.75, base="l", shift="L"),
        _k("Semicolon", 2, 10.75, base=";", shift=":", altgr="~"),
        _k("Quote", 2, 11.75, base="è", shift="È", altgr="`"),
        _k("Backslash", 2, 12.75, 0.75, base="à", shift="À"),
    ]
    row3 = [
        _k("ShiftLeft", 3, 0, 1.25, kind="shift", base="⇧"),
        _k("IntlBackslash", 3, 1.25, base="ù", shift="Ù", altgr="\\"),
        _k("KeyZ", 3, 2.25, base="z", shift="Z"),
        _k("KeyX", 3, 3.25, base="x", shift="X"),
        _k("KeyC", 3, 4.25, base="c", shift="C", altgr="©"),
        _k("KeyV", 3, 5.25, base="v", shift="V"),
        _k("KeyB", 3, 6.25, base="b", shift="B"),
        _k("KeyN", 3, 7.25, base="n", shift="N"),
        _k("KeyM", 3, 8.25, base="m", shift="M"),
        _k("Comma", 3, 9.25, base=",", shift="'", altgr="«"),
        _k("Period", 3, 10.25, base=".", shift=".", altgr="»"),
        _k("Slash", 3, 11.25, base="é", shift="É", altgr="´"),
        _k("ShiftRight", 3, 12.25, 2.75, kind="shift", base="⇧"),
    ]
    row4 = [
        _k("ControlLeft", 4, 0, 1.5, kind="ctrl", base="ctrl"),
        _k("AltLeft", 4, 1.5, 1.5, kind="alt", base="alt"),
        _k("Space", 4, 3.0, 7.5, kind="space", base=" "),
        _k("AltRight", 4, 10.5, 2.25, kind="altgr", base="alt gr"),
        _k("ControlRight", 4, 12.75, 2.25, kind="ctrl", base="ctrl"),
    ]
    return Layout(
        id="csa",
        name="Canadian French",
        name_fr="Canadien français",
        geometry="iso",
        keys=tuple(row0 + row1 + row2 + row3 + row4),
        x0=BOARD_GAP,
    )


US = _us_ansi()
CSA = _csa_iso()
LAYOUTS = (US, CSA)

DEAD_MAP = {
    "circ": {
        "a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û", "w": "ŵ", "y": "ŷ",
        "A": "Â", "E": "Ê", "I": "Î", "O": "Ô", "U": "Û", "W": "Ŵ", "Y": "Ŷ",
    },
    "uml": {
        "a": "ä", "e": "ë", "i": "ï", "o": "ö", "u": "ü", "y": "ÿ",
        "A": "Ä", "E": "Ë", "I": "Ï", "O": "Ö", "U": "Ü", "Y": "Ÿ",
    },
    "grave": {
        "a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
        "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù",
    },
    "cedilla": {"c": "ç", "C": "Ç", "g": "ģ", "G": "Ģ"},
    "caron": {"c": "č", "C": "Č", "s": "š", "S": "Š", "z": "ž", "Z": "Ž"},
}


def layout_by_id(ident: str) -> Layout:
    for layout in LAYOUTS:
        if layout.id == ident:
            return layout
    raise KeyError(ident)


def point_of(layout: Layout, kid: str) -> tuple[float, float]:
    return layout.center(layout.by_id()[kid])


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cluster_points(points: list[tuple[float, float]], *, eps: float = CLUSTER_EPS) -> list[int]:
    """Parameter-less density labels. Adjacent keys share a label; a gap splits."""
    n = len(points)
    if n == 0:
        return []
    labels = [-1] * n

    def neighbors(i: int) -> list[int]:
        return [j for j in range(n) if dist(points[i], points[j]) <= eps]

    cid = 0
    for i in range(n):
        if labels[i] != -1:
            continue
        labels[i] = cid
        seed = list(neighbors(i))
        s = 0
        while s < len(seed):
            j = seed[s]
            s += 1
            if labels[j] == -1:
                labels[j] = cid
                for k in neighbors(j):
                    if k not in seed:
                        seed.append(k)
        cid += 1
    return labels


@dataclass(frozen=True)
class HeldKey:
    board: str
    kid: str

    @property
    def point(self) -> tuple[float, float]:
        return point_of(layout_by_id(self.board), self.kid)


def cluster_held(held: list[HeldKey]) -> list[list[HeldKey]]:
    if not held:
        return []
    labels = cluster_points([h.point for h in held])
    buckets: dict[int, list[HeldKey]] = {}
    for key, lab in zip(held, labels):
        buckets.setdefault(lab, []).append(key)
    return [buckets[i] for i in sorted(buckets)]


def can_accept(held: list[HeldKey], incoming: HeldKey, *, max_fingers: int = MAX_FINGERS) -> bool:
    """11th independent touch is rejected unless it is well clustered."""
    if incoming in held:
        return True
    if len(held) < max_fingers:
        return True
    before = len(cluster_held(held))
    after = len(cluster_held(held + [incoming]))
    return after <= before


@dataclass
class TypeState:
    shift: bool = False
    caps: bool = False
    altgr: bool = False
    dead: str = ""
    text: str = ""

    def glyph(self, key: KeySpec) -> str:
        if key.kind == "space":
            return " "
        if key.kind != "char":
            return ""
        if self.altgr and key.altgr:
            return key.altgr
        upper = self.shift ^ (self.caps and key.base.isalpha())
        if upper:
            return key.shift or key.base.upper()
        return key.base

    def apply(self, key: KeySpec) -> str:
        """Apply a key. Returns any committed characters (may be empty)."""
        if key.kind == "shift":
            self.shift = True
            return ""
        if key.kind == "caps":
            self.caps = not self.caps
            return ""
        if key.kind == "altgr":
            self.altgr = True
            return ""
        if key.kind == "backspace":
            if self.dead:
                self.dead = ""
                return ""
            self.text = self.text[:-1]
            return ""
        if key.kind == "enter":
            self.text += "\n"
            return "\n"
        if key.kind == "tab":
            self.text += "\t"
            return "\t"
        if key.kind == "space":
            if self.dead:
                mark = {"circ": "^", "uml": "¨", "grave": "`", "cedilla": "¸", "caron": "ˇ"}.get(
                    self.dead, ""
                )
                self.dead = ""
                self.text += mark + " "
                return mark + " "
            self.text += " "
            return " "
        if key.kind != "char":
            return ""

        dead_id = ""
        if self.shift and key.shift_dead:
            dead_id = key.shift_dead
        elif not self.shift and key.dead:
            dead_id = key.dead
        if dead_id and not self.altgr:
            self.dead = dead_id
            return ""

        ch = self.glyph(key)
        if self.dead:
            combo = DEAD_MAP.get(self.dead, {}).get(ch)
            self.dead = ""
            if combo:
                ch = combo
        if not ch:
            return ""
        self.text += ch
        return ch

    def release(self, key: KeySpec) -> None:
        if key.kind == "shift":
            self.shift = False
        if key.kind == "altgr":
            self.altgr = False


@dataclass
class FingerGate:
    """Touch pointers (max 10) plus well-clustered extra keys."""

    max_fingers: int = MAX_FINGERS
    pointers: dict[int, HeldKey] = field(default_factory=dict)
    extras: list[HeldKey] = field(default_factory=list)

    def held(self) -> list[HeldKey]:
        out = list(self.pointers.values())
        out.extend(self.extras)
        return out

    def clusters(self) -> list[list[HeldKey]]:
        return cluster_held(self.held())

    def down(self, pointer: int, key: HeldKey) -> bool:
        if pointer in self.pointers:
            prev = self.pointers[pointer]
            if prev == key:
                return True
            del self.pointers[pointer]
            if can_accept(self.held(), key, max_fingers=self.max_fingers):
                self.pointers[pointer] = key
                return True
            self.pointers[pointer] = prev
            return False
        if key in self.held():
            return True
        if not can_accept(self.held(), key, max_fingers=self.max_fingers):
            return False
        if len(self.pointers) < self.max_fingers:
            self.pointers[pointer] = key
        else:
            self.extras.append(key)
        return True

    def up(self, pointer: int) -> None:
        self.pointers.pop(pointer, None)
        self._prune_extras()

    def _prune_extras(self) -> None:
        """Extras stay only while they remain well clustered with a live finger."""
        base = list(self.pointers.values())
        kept: list[HeldKey] = []
        for extra in self.extras:
            if extra in base or extra in kept:
                continue
            before = len(cluster_held(base + kept))
            after = len(cluster_held(base + kept + [extra]))
            if after <= before:
                kept.append(extra)
        self.extras = kept

    def clear(self) -> None:
        self.pointers.clear()
        self.extras.clear()


def main() -> None:
    if US.geometry != "ansi" or CSA.geometry != "iso":
        raise SystemExit("US must be ANSI and Canadian French CSA must be ISO")
    if any(k.kid == "IntlBackslash" for k in US.keys):
        raise SystemExit("US ANSI must not grow the ISO extra key")
    if not any(k.kid == "IntlBackslash" and k.base == "ù" for k in CSA.keys):
        raise SystemExit("CSA must expose ù left of Z")
    if not any(k.base == "é" for k in CSA.keys):
        raise SystemExit("CSA must expose é")
    if not any(k.base == "è" for k in CSA.keys):
        raise SystemExit("CSA must expose è")

    asdf = [HeldKey("us", kid) for kid in ("KeyA", "KeyS", "KeyD", "KeyF")]
    if len(cluster_held(asdf)) != 1:
        raise SystemExit("home-row left hand must be one well-clustered group")

    hands = asdf + [HeldKey("us", kid) for kid in ("KeyJ", "KeyK", "KeyL")]
    if len(cluster_held(hands)) != 2:
        raise SystemExit("left and right home row must be two clusters (gap at G/H)")
    ten_home = [
        HeldKey("us", kid)
        for kid in (
            "KeyA", "KeyS", "KeyD", "KeyF", "KeyG",
            "KeyJ", "KeyK", "KeyL", "Semicolon", "Quote",
        )
    ]
    if len(cluster_held(ten_home)) != 2:
        raise SystemExit("two-hand home row must stay two clusters")
    if can_accept(ten_home, HeldKey("us", "Digit1")):
        raise SystemExit("an 11th isolated key must be rejected even when only two clusters are down")
    if not can_accept(ten_home, HeldKey("us", "KeyQ")):
        raise SystemExit("an 11th key next to A must be accepted as clustered")

    ten = [
        HeldKey("us", kid)
        for kid in (
            "Digit1", "Digit3", "Digit5", "Digit7", "Digit9",
            "KeyZ", "KeyC", "KeyB", "KeyM", "Slash",
        )
    ]
    if len(cluster_held(ten)) != 10:
        raise SystemExit(f"ten isolated keys must be ten fingers, got {len(cluster_held(ten))}")
    eleventh = HeldKey("csa", "KeyA")
    if can_accept(ten, eleventh):
        raise SystemExit("an 11th isolated key must be rejected")
    neighbor = HeldKey("us", "Backquote")
    if not can_accept(ten, neighbor):
        raise SystemExit("an 11th key that is well clustered must be accepted")

    both_boards = [HeldKey("us", "KeyA"), HeldKey("csa", "KeyA")]
    if len(cluster_held(both_boards)) != 2:
        raise SystemExit("the same letter on US and CSA is two clusters (two boards)")

    gate = FingerGate()
    for i, key in enumerate(ten):
        if not gate.down(i, key):
            raise SystemExit("first ten fingers must all land")
    if gate.down(99, eleventh):
        raise SystemExit("gate must refuse an 11th isolated pointer")
    if not gate.down(99, neighbor):
        raise SystemExit("gate must allow a well-clustered extra key")
    if len(gate.clusters()) != 10:
        raise SystemExit("stacked track count must stay at 10 fingers when extras cluster")

    st = TypeState()
    st.apply(CSA.by_id()["Slash"])
    if st.text != "é":
        raise SystemExit(f"CSA Slash should type é, got {st.text!r}")
    st.apply(CSA.by_id()["BracketLeft"])
    st.apply(CSA.by_id()["KeyA"])
    if not st.text.endswith("â"):
        raise SystemExit(f"dead ^ then a should type â, got {st.text!r}")
    st2 = TypeState()
    st2.apply(US.by_id()["KeyA"])
    if st2.text != "a":
        raise SystemExit("US KeyA should type a")
    st2.apply(US.by_id()["CapsLock"])
    st2.apply(US.by_id()["KeyA"])
    if st2.text != "aA":
        raise SystemExit(f"caps should invert case, got {st2.text!r}")
    st2.apply(US.by_id()["ShiftLeft"])
    st2.apply(US.by_id()["KeyB"])
    if st2.text != "aAb":
        raise SystemExit(f"caps+shift should cancel, got {st2.text!r}")

    gate.up(0)
    if any(k.kid == "Backquote" for k in gate.held()):
        raise SystemExit("a clustered extra must lift when its neighbor finger lifts")
    if not gate.down(0, eleventh):
        raise SystemExit("a freed finger must be able to press a new isolated key")
    if gate.down(98, HeldKey("csa", "Digit1")):
        raise SystemExit("an 11th isolated key must stay rejected after the extra is gone")

    print(
        f"dual_keyboard: US={len(US.keys)} CSA={len(CSA.keys)} "
        f"hands={len(cluster_held(hands))} gate=10+cluster OK"
    )


if __name__ == "__main__":
    main()
