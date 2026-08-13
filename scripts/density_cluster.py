#!/usr/bin/env python3
"""Density clustering of spectral peaks into independent tracks.

Harmonic series collapse first (one sung/played note is one source), then
DBSCAN in (log-f0, harmonicity, centroid) with adaptive eps. A solo voice
with overtones spanning 80–2000 Hz is ONE track, not five Hz-band guesses.
"""
from __future__ import annotations

import math
import sys

SOFT_MAX = 8


def group_harmonic_funds(peaks: list[dict]) -> list[dict]:
    funds: list[dict] = []
    for p in sorted(peaks, key=lambda x: -x["db"]):
        attached = False
        for g in funds:
            n = round(p["f"] / g["f0"])
            if n < 2 or n > 8:
                continue
            cents = 1200 * math.log2(p["f"] / (n * g["f0"]))
            if abs(cents) < 35:
                g["members"].append(p)
                g["db"] = max(g["db"], p["db"])
                attached = True
                break
        if not attached:
            funds.append({"f0": p["f"], "db": p["db"], "members": [p]})
    for g in funds:
        w = 0.0
        f_sum = 0.0
        for m in g["members"]:
            mag = 10 ** (m["db"] / 20)
            w += mag
            f_sum += m["f"] * mag
        g["centroid"] = f_sum / (w or 1.0)
        g["harm"] = min(1.0, (len(g["members"]) - 1) / 5.0)
        g["logF"] = math.log2(g["f0"])
        g["logC"] = math.log2(max(g["centroid"], 1.0))
    return funds


def feat(g: dict) -> tuple[float, float, float]:
    return (g["logF"] * 0.42, g["harm"] * 1.8, g["logC"] * 0.35)


def dist(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def density_cluster_funds(funds: list[dict]) -> list[dict]:
    if not funds:
        return []
    pts = [{"g": g, "x": feat(g)} for g in funds]
    gaps: list[float] = []
    for i, p in enumerate(pts):
        best = 1e9
        for j, q in enumerate(pts):
            if i == j:
                continue
            d = dist(p["x"], q["x"])
            if d < best:
                best = d
        if best < 1e9:
            gaps.append(best)
    gaps.sort()
    median = gaps[len(gaps) // 2] if gaps else 0.55
    eps = max(0.28, min(0.85, (median * 1.35) if median else 0.55))
    n = len(pts)
    labels = [-1] * n

    def neighbors(i: int) -> list[int]:
        return [j for j in range(n) if dist(pts[i]["x"], pts[j]["x"]) <= eps]

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

    buckets: dict[int, list] = {}
    for i, lab in enumerate(labels):
        buckets.setdefault(lab, []).append(pts[i]["g"])
    clusters = []
    for members in buckets.values():
        members.sort(key=lambda g: -g["db"])
        head = members[0]
        clusters.append(
            {
                "f0": head["f0"],
                "db": max(g["db"] for g in members),
                "harm": sum(g["harm"] for g in members) / len(members),
                "n": sum(len(g["members"]) for g in members),
            }
        )
    clusters.sort(key=lambda c: -c["db"])
    if not clusters:
        return []
    top = clusters[0]["db"]
    return [c for c in clusters if c["db"] > top - 22 and c["db"] > -72][:SOFT_MAX]


def cluster_peaks(peaks: list[dict]) -> list[dict]:
    return density_cluster_funds(group_harmonic_funds(peaks))


def tone_stack(f0: float, db0: float = -20.0, n_harm: int = 6) -> list[dict]:
    return [{"f": f0 * n, "db": db0 - 4.0 * (n - 1)} for n in range(1, n_harm + 1)]


def main() -> None:
    solo = cluster_peaks(tone_stack(220.0, -16.0, 8))
    if len(solo) != 1:
        raise SystemExit(f"solo 220 Hz + harmonics must be 1 track, got {len(solo)}")

    voice_span = cluster_peaks(tone_stack(82.4, -16.0, 12))
    if len(voice_span) != 1:
        raise SystemExit(
            f"one harmonic series 82–990 Hz must be 1 track (not five bands), got {len(voice_span)}"
        )

    two = cluster_peaks(tone_stack(110.0, -18.0, 5) + tone_stack(523.25, -22.0, 4))
    if len(two) != 2:
        raise SystemExit(
            f"two independent sources must be 2 tracks, got {len(two)} {[round(c['f0'], 1) for c in two]}"
        )

    chordish = cluster_peaks(
        tone_stack(130.81, -18.0, 4) + tone_stack(164.81, -20.0, 4) + tone_stack(196.0, -21.0, 3)
    )
    if not 1 <= len(chordish) <= 3:
        raise SystemExit(f"one-source chord should stay small, got {len(chordish)}")
    if len(chordish) >= 5:
        raise SystemExit("must not invent five instrument tracks for one chord")

    print(f"solo={len(solo)} voice_span={len(voice_span)} two={len(two)} chord={len(chordish)}")
    print("density_cluster: OK")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e, file=sys.stderr)
        raise
