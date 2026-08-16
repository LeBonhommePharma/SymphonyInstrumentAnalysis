#!/usr/bin/env python3
"""Density clustering of spectral peaks into independent tracks.

Harmonic series collapse first (one sung/played note is one source), then
DBSCAN in (log-f0, harmonicity, centroid) with adaptive eps. A solo voice
with overtones spanning 80–2000 Hz is ONE track, not five Hz-band guesses.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

def group_harmonic_funds(peaks: list[dict]) -> list[dict]:
    funds: list[dict] = []
    for p in sorted(peaks, key=lambda x: -x["db"]):
        best: dict | None = None
        best_cents = 35.0
        for g in funds:
            n = round(p["f"] / g["f0"])
            if n < 2 or n > 16:
                continue
            cents = abs(1200 * math.log2(p["f"] / (n * g["f0"])))
            if cents < best_cents:
                best = g
                best_cents = cents
        if best is not None:
            best["members"].append(p)
            best["db"] = max(best["db"], p["db"])
        else:
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


DBSCAN_MIN_PTS = 2
EPS_FLOOR = 0.28
EPS_CAP = 0.85
# eps is scaled *below* the median nearest-neighbor gap so two genuinely
# distinct fundamentals (already harmonic-folded) stay separate. The old
# 1.35× inflation made eps larger than the typical inter-source gap, which let
# the single-linkage expansion chain A~B~C into one cluster even when A and C
# were far apart in feature space.
EPS_NEIGHBOR_SCALE = 0.9


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
    median = gaps[len(gaps) // 2] if gaps else EPS_FLOOR
    eps = max(EPS_FLOOR, min(EPS_CAP, median * EPS_NEIGHBOR_SCALE))
    n = len(pts)
    labels = [-1] * n

    def neighbors(i: int) -> list[int]:
        return [j for j in range(n) if dist(pts[i]["x"], pts[j]["x"]) <= eps]

    # Proper DBSCAN: only core points (>= minPts points incl. self within eps)
    # seed a cluster. The previous flood fill treated every point as a core
    # point, i.e. single-linkage chaining.
    core = [len(neighbors(i)) + 1 >= DBSCAN_MIN_PTS for i in range(n)]
    cid = 0
    for i in range(n):
        if labels[i] != -1 or not core[i]:
            continue
        labels[i] = cid
        seed = list(neighbors(i))
        s = 0
        while s < len(seed):
            j = seed[s]
            s += 1
            if labels[j] == -1:
                labels[j] = cid
                if core[j]:
                    for k in neighbors(j):
                        if k not in seed:
                            seed.append(k)
        cid += 1

    # Isolated funds (no core neighbor) still become their own track.
    for i in range(n):
        if labels[i] == -1:
            labels[i] = cid
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
    return [c for c in clusters if c["db"] > -90]


def funds_as_clusters(funds: list[dict]) -> list[dict]:
    clusters = [
        {
            "f0": g["f0"],
            "db": g["db"],
            "harm": g["harm"],
            "n": len(g["members"]),
        }
        for g in funds
        if g["db"] > -90
    ]
    clusters.sort(key=lambda c: -c["db"])
    return clusters


def cluster_peaks(peaks: list[dict], *, merge_nearby: bool = True) -> list[dict]:
    funds = group_harmonic_funds(peaks)
    if not merge_nearby:
        return funds_as_clusters(funds)
    return density_cluster_funds(funds)


def heuristic_label(f0: float, harm: float) -> str:
    """Same nouns as iOS/web ClusterLabeler — voix is first-class."""
    if harm < 0.18 and f0 > 180:
        return "bruit"
    if f0 < 90:
        return "grave"
    if f0 < 280 and harm >= 0.35:
        return "voix"
    if f0 < 450:
        return "corps"
    if harm >= 0.55:
        return "nylon"
    if f0 > 1400:
        return "air"
    return ""


def tone_stack(f0: float, db0: float = -20.0, n_harm: int = 6) -> list[dict]:
    return [{"f": f0 * n, "db": db0 - 4.0 * (n - 1)} for n in range(1, n_harm + 1)]


def fixture_cases() -> list[dict]:
    return [
        {
            "name": "solo220",
            "peaks": tone_stack(220.0, -16.0, 8),
            "merge_nearby": True,
            "expect_n": 1,
            "expect_f0": [220.0],
        },
        {
            "name": "two_sources",
            "peaks": tone_stack(110.0, -18.0, 5) + tone_stack(523.25, -22.0, 4),
            "merge_nearby": True,
            "expect_n": 2,
            "expect_f0": [110.0, 523.25],
        },
        {
            "name": "ceg_offline",
            "peaks": tone_stack(130.81, -18.0, 4)
            + tone_stack(164.81, -20.0, 4)
            + tone_stack(196.0, -21.0, 3),
            "merge_nearby": False,
            "expect_n": 3,
            "expect_f0": [130.81, 164.81, 196.0],
        },
    ]


def write_fixtures(path: Path) -> None:
    cases = []
    for raw in fixture_cases():
        got = cluster_peaks(raw["peaks"], merge_nearby=raw["merge_nearby"])
        if len(got) != raw["expect_n"]:
            raise SystemExit(f"fixture {raw['name']} expected {raw['expect_n']} got {len(got)}")
        cases.append(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")


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

    # Two distinct sources where one has an exact octave harmonic: 200 Hz must
    # fold into 100 Hz, leaving 141 Hz (inharmonic, ~600 cents up) as its own
    # track. Single-linkage used to chain these into one cluster.
    distinct = cluster_peaks(
        [{"f": 100.0, "db": -20.0}, {"f": 200.0, "db": -24.0}, {"f": 141.0, "db": -22.0}]
    )
    if len(distinct) != 2:
        raise SystemExit(
            f"octave-folded source + inharmonic neighbor must be 2 tracks, "
            f"got {len(distinct)} {[round(c['f0'], 1) for c in distinct]}"
        )

    chordish = cluster_peaks(
        tone_stack(130.81, -18.0, 4) + tone_stack(164.81, -20.0, 4) + tone_stack(196.0, -21.0, 3)
    )
    if not 1 <= len(chordish) <= 3:
        raise SystemExit(f"one-source chord should stay small, got {len(chordish)}")
    chord_off = cluster_peaks(
        tone_stack(130.81, -18.0, 4) + tone_stack(164.81, -20.0, 4) + tone_stack(196.0, -21.0, 3),
        merge_nearby=False,
    )
    if len(chord_off) != 3:
        raise SystemExit(
            f"offline analysis must keep C–E–G as 3 funds, got {len(chord_off)} "
            f"{[round(c['f0'], 1) for c in chord_off]}"
        )
    if len(chordish) >= 5:
        raise SystemExit("must not invent five instrument tracks for one chord")

    # Psytrance-like: kick series + inharmonic highs (n>8 so they are not harmonics).
    psy = cluster_peaks(
        tone_stack(55.0, -12.0, 3)
        + [
            {"f": 2100.0, "db": -18.0},
            {"f": 2450.0, "db": -20.0},
            {"f": 3120.0, "db": -22.0},
            {"f": 3800.0, "db": -24.0},
        ]
    )
    if len(psy) < 2:
        raise SystemExit(f"kick + high synth must stay ≥2 sources, got {len(psy)}")
    if not any(c["f0"] < 80 for c in psy) or not any(c["f0"] > 1800 for c in psy):
        raise SystemExit(f"psytrance must keep a low and a high source: {[round(c['f0']) for c in psy]}")

    print(
        f"solo={len(solo)} voice_span={len(voice_span)} two={len(two)} "
        f"chord={len(chordish)} psy={len(psy)} distinct={len(distinct)}"
    )
    fixtures = Path(__file__).resolve().parents[1] / "piano" / "cluster_fixtures.json"
    write_fixtures(fixtures)
    print(f"density_cluster: OK wrote {fixtures}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e, file=sys.stderr)
        raise
