#!/usr/bin/env python3
"""Shared chord-tone → musician-layer assignment.

Six synthesis layers are canonical (bass, cello, two steels, nylon, viola).
The five-lane visual folds nylon + viola sheen into nylon_high.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chord_pitch_colors import NOTE_NAMES, PC_HZ  # noqa: E402

PC_INDEX = {pc: i for i, pc in enumerate(NOTE_NAMES)}

SIX_KEYS = (
    "upright_bass",
    "cello",
    "guitar_a",
    "guitar_b",
    "nylon_guitar",
    "viola_sheen",
)
FIVE_KEYS = (
    "upright_bass",
    "cello",
    "guitar_a",
    "guitar_b",
    "nylon_high",
)
FIVE_FROM_SIX = {
    "upright_bass": "upright_bass",
    "cello": "cello",
    "guitar_a": "guitar_a",
    "guitar_b": "guitar_b",
    "nylon_guitar": "nylon_high",
    "viola_sheen": "nylon_high",
}
LAYER_HZ: dict[str, tuple[float, float]] = {
    "upright_bass": (55.0, 130.0),
    "cello": (130.0, 320.0),
    "guitar_a": (196.0, 440.0),
    "guitar_b": (220.0, 494.0),
    "nylon_guitar": (247.0, 587.0),
    "viola_sheen": (392.0, 880.0),
    "nylon_high": (247.0, 880.0),
}


def parse_chord_root(chord: str | None) -> str | None:
    if not chord:
        return None
    m = re.match(r"^([A-G]#?)", chord)
    return m.group(1) if m else None


def hz_in_range(pc: str, lo: float, hi: float) -> float:
    """Place pitch-class into [lo, hi] nearest the geometric mid."""
    base = PC_HZ[pc]
    target = (lo * hi) ** 0.5
    best = base
    best_dist = abs(np.log2(base / target))
    for oct_shift in range(-3, 4):
        f = base * (2.0**oct_shift)
        if f < lo * 0.85 or f > hi * 1.15:
            continue
        d = abs(np.log2(f / target))
        if d < best_dist:
            best = f
            best_dist = d
    return float(np.clip(best, lo * 0.9, hi * 1.1))


def _sorted_pcs(pcs: list[str], chord: str | None) -> list[str]:
    clean = [p for p in pcs if p in PC_HZ][:5]
    if not clean:
        return []
    root = parse_chord_root(chord)
    if root not in PC_HZ:
        root = clean[0]
    uniq = list(dict.fromkeys(clean))
    sorted_pcs = sorted(uniq, key=lambda p: PC_INDEX[p])
    if root in sorted_pcs:
        sorted_pcs = [root] + [p for p in sorted_pcs if p != root]
    return sorted_pcs


def assign_six_layers(
    pcs: list[str],
    chord: str | None,
    *,
    seg_index: int = 0,
) -> dict[str, list[tuple[str, float]]]:
    """Distribute chord tones across the six wooden musicians."""
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in SIX_KEYS}
    sorted_pcs = _sorted_pcs(pcs, chord)
    if not sorted_pcs:
        return out

    def put(key: str, pc: str) -> None:
        lo, hi = LAYER_HZ[key]
        out[key].append((pc, hz_in_range(pc, lo, hi)))

    n = len(sorted_pcs)
    put("upright_bass", sorted_pcs[0])
    if n == 1:
        put("cello", sorted_pcs[0])
        return out
    if n == 2:
        put("cello", sorted_pcs[1])
        put("guitar_a" if seg_index % 2 == 0 else "guitar_b", sorted_pcs[1])
        return out

    put("cello", sorted_pcs[1])
    mid = list(sorted_pcs[2:])
    if n >= 5 and mid:
        put("viola_sheen", mid.pop())
    elif n == 4 and mid:
        put("viola_sheen", mid[-1])
    elif n == 3 and mid:
        put("nylon_guitar", mid[-1])

    guitars = ["guitar_a", "guitar_b", "nylon_guitar"]
    phase = seg_index % 3
    for i, pc in enumerate(mid):
        put(guitars[(i + phase) % 3], pc)
    return out


def assign_five_layers(
    pcs: list[str],
    chord: str | None,
    *,
    seg_index: int = 0,
) -> dict[str, list[tuple[str, float]]]:
    """Five visual lanes: nylon_high = nylon_guitar + viola_sheen."""
    six = assign_six_layers(pcs, chord, seg_index=seg_index)
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in FIVE_KEYS}
    for src, notes in six.items():
        out[FIVE_FROM_SIX[src]].extend(notes)
    return out


def hz_only(assigned: dict[str, list[tuple[str, float]]]) -> dict[str, list[float]]:
    return {k: [hz for _, hz in notes] for k, notes in assigned.items()}


def main() -> None:
    six = assign_six_layers(["C", "E", "G"], "C", seg_index=0)
    if not six["upright_bass"] or not six["cello"]:
        raise SystemExit("triad must light bass and cello")
    five = assign_five_layers(["C", "E", "G", "B"], "Cmaj7", seg_index=1)
    if set(five) != set(FIVE_KEYS):
        raise SystemExit(f"five-lane keys wrong: {sorted(five)}")
    folded = assign_five_layers(["C", "E", "G", "B", "D"], "Cmaj9", seg_index=0)
    six5 = assign_six_layers(["C", "E", "G", "B", "D"], "Cmaj9", seg_index=0)
    n_high = len(folded["nylon_high"])
    n_src = len(six5["nylon_guitar"]) + len(six5["viola_sheen"])
    if n_high != n_src or n_high < 1:
        raise SystemExit(f"nylon_high must fold nylon+viola, got {n_high} vs {n_src}")
    if hz_only(six)["upright_bass"][0] <= 0:
        raise SystemExit("bass hz must be positive")
    print("voicing: OK")


if __name__ == "__main__":
    main()
