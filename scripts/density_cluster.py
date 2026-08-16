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

def _cents(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 1e9
    return abs(1200 * math.log2(a / b))


def _fill_fund_stats(g: dict) -> None:
    w = 0.0
    f_sum = 0.0
    for m in g["members"]:
        mag = 10 ** (m["db"] / 20)
        w += mag
        f_sum += m["f"] * mag
    g["centroid"] = f_sum / (w or 1.0)
    g["harm"] = min(1.0, (len(g["members"]) - 1) / 5.0)
    g["logF"] = math.log2(max(g["f0"], 1e-6))
    g["logC"] = math.log2(max(g["centroid"], 1.0))


def _refine_fund_f0(g: dict) -> None:
    """Prefer the lowest candidate that explains the partials (not the loudest).

    A clean even series (220, 440, 660…) must stay at 220. Half-f0 is accepted
    only when a peak sits there or an odd partial (3, 5, …) needs that f0.
    """
    freqs = [m["f"] for m in g["members"] if m["f"] > 0]
    if not freqs:
        return
    candidates = list(freqs)
    for f in freqs:
        candidates.append(f / 2.0)
    best_f0 = g["f0"]
    best_score = -1e18
    for cand in candidates:
        if cand < 20:
            continue
        hits = 0
        odd_hi = 0
        has_self = False
        for f in freqs:
            n = round(f / cand)
            if 1 <= n <= 16 and _cents(f, n * cand) < 35:
                hits += 1
                if n == 1:
                    has_self = True
                if n >= 3 and n % 2 == 1:
                    odd_hi += 1
        if hits < 2:
            continue
        if not has_self and odd_hi < 1:
            continue
        score = hits * 1000.0 + odd_hi * 10.0 - cand
        if score > best_score:
            best_score = score
            best_f0 = cand
    g["f0"] = best_f0


def _merge_octave_funds(funds: list[dict]) -> list[dict]:
    funds = sorted(funds, key=lambda g: g["f0"])
    used: set[int] = set()
    out: list[dict] = []
    for i, a in enumerate(funds):
        if i in used:
            continue
        for j in range(i + 1, len(funds)):
            if j in used:
                continue
            b = funds[j]
            n = round(b["f0"] / a["f0"]) if a["f0"] else 0
            # n=1 merges refined unisons (loud 220 + quiet 110 both become 110).
            if n < 1 or n > 8:
                continue
            if _cents(b["f0"], n * a["f0"]) < 35:
                a["members"].extend(b["members"])
                a["db"] = max(a["db"], b["db"])
                used.add(j)
        out.append(a)
    for g in out:
        _fill_fund_stats(g)
    return out


def group_harmonic_funds(peaks: list[dict]) -> list[dict]:
    funds: list[dict] = []
    for p in sorted(peaks, key=lambda x: -x["db"]):
        best: dict | None = None
        best_cents = 35.0
        for g in funds:
            n = round(p["f"] / g["f0"])
            if n < 2 or n > 16:
                continue
            cents = _cents(p["f"], n * g["f0"])
            if cents < best_cents:
                best = g
                best_cents = cents
        if best is not None:
            best["members"].append(p)
            best["db"] = max(best["db"], p["db"])
        else:
            funds.append({"f0": p["f"], "db": p["db"], "members": [p]})
    for g in funds:
        _refine_fund_f0(g)
        _fill_fund_stats(g)
    return _merge_octave_funds(funds)


def feat(g: dict) -> tuple[float, float, float]:
    return (g["logF"] * 0.42, g["harm"] * 1.8, g["logC"] * 0.35)


def dist(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


DBSCAN_MIN_PTS = 3
EPS_FLOOR = 0.28
EPS_CAP = 0.85
EPS_NEIGHBOR_SCALE = 0.9
# Distinct fundamentals more than this many cents apart never share a cluster.
MIN_F0_CENTS = 70.0


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
        out: list[int] = []
        for j in range(n):
            if i == j:
                continue
            if abs(1200.0 * (pts[i]["g"]["logF"] - pts[j]["g"]["logF"])) > MIN_F0_CENTS:
                continue
            if dist(pts[i]["x"], pts[j]["x"]) <= eps:
                out.append(j)
        return out

    # neighbors exclude self; +1 counts the point. minPts=3 means a pair of
    # notes is not a core (avoids single-linkage A~B~C chains).
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
                "centroid": head["centroid"],
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
            "centroid": g.get("centroid", g["f0"]),
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


def heuristic_label(f0: float, harm: float, centroid: float | None = None) -> str:
    """Same nouns as iOS/web ClusterLabeler. voix needs a formant-ish centroid."""
    if harm < 0.18 and f0 > 180:
        return "bruit"
    if f0 < 90:
        return "grave"
    voice_like = (
        85.0 <= f0 <= 280.0
        and harm >= 0.45
        and centroid is not None
        and 250.0 <= centroid <= 1400.0
        and centroid > f0 * 1.8
    )
    if voice_like:
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
            "name": "louder_overtone",
            "peaks": [
                {"f": 110.0, "db": -28.0},
                {"f": 220.0, "db": -12.0},
                {"f": 330.0, "db": -22.0},
                {"f": 440.0, "db": -18.0},
            ],
            "merge_nearby": True,
            "expect_n": 1,
            "expect_f0": [110.0],
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
        for i, want in enumerate(raw.get("expect_f0") or []):
            if i >= len(got) or abs(got[i]["f0"] - want) > 1.0:
                raise SystemExit(
                    f"fixture {raw['name']} f0[{i}] {got[i]['f0'] if i < len(got) else None} != {want}"
                )
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

    loud = cluster_peaks(
        [
            {"f": 110.0, "db": -28.0},
            {"f": 220.0, "db": -12.0},
            {"f": 330.0, "db": -22.0},
            {"f": 440.0, "db": -18.0},
        ]
    )
    if len(loud) != 1 or abs(loud[0]["f0"] - 110.0) > 2:
        raise SystemExit(f"louder 220 Hz overtone must fold to 110 Hz, got {loud}")
    if heuristic_label(220.0, 0.6, centroid=280.0) == "voix":
        raise SystemExit("cello-like centroid must not be labeled voix")
    if heuristic_label(220.0, 0.6, centroid=700.0) != "voix":
        raise SystemExit("formant-ish stack should still be voix")

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
