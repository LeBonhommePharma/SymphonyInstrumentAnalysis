#!/usr/bin/env python3
"""Per-musician / per-instrument layered chord visuals (color = pitch).

No audio synthesis. Assigns chord tones by register so each lane shows a
distinct slice of the harmony — not the full stack compressed into one panel.
Kid-genius bilingual crayon legend via chord_pitch_colors.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chord_pitch_colors import (  # noqa: E402
    NOTE_NAMES,
    PC_FR,
    PC_HZ,
    draw_color_legend,
    legend_markdown_rows,
    pc_rgb,
)

ROOT = Path(__file__).resolve().parents[1]
CHORD_JSON = ROOT / "analysis_out" / "final_song_chords.json"
OUT = ROOT / "analysis_out"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def chord_duration(data: dict) -> float:
    timeline = data.get("timeline") or []
    listed = data.get("duration_sec")
    duration = float(listed) if listed not in (None, "") else (
        float(timeline[-1]["end"]) if timeline else 0.0
    )
    if timeline:
        duration = max(duration, float(timeline[-1]["end"]))
    return duration

PC_INDEX = {pc: i for i, pc in enumerate(NOTE_NAMES)}

@dataclass(frozen=True)
class LayerSpec:
    key: str
    display: str
    role: str
    freq_range_hz: tuple[float, float]
    lane_tint: str  # soft panel background


# Five visual musicians (wooden chords only). High lane = nylon + viola sheen.
LAYERS: list[LayerSpec] = [
    LayerSpec(
        "upright_bass",
        "Upright bass",
        "lowest / root-ish floor",
        (55.0, 130.0),
        "#f0e6d8",
    ),
    LayerSpec(
        "cello",
        "Cello",
        "low-mid wooden sustain",
        (130.0, 320.0),
        "#efe8dc",
    ),
    LayerSpec(
        "guitar_a",
        "Guitar A (steel)",
        "mid chord body",
        (196.0, 440.0),
        "#e8efe6",
    ),
    LayerSpec(
        "guitar_b",
        "Guitar B (steel)",
        "mid chord alternate",
        (220.0, 494.0),
        "#e6efe9",
    ),
    LayerSpec(
        "nylon_high",
        "Nylon / high (viola sheen)",
        "mid-high extensions & sparkle",
        (247.0, 880.0),
        "#e4ebf2",
    ),
]


def parse_chord_root(chord: str | None) -> str | None:
    if not chord:
        return None
    m = re.match(r"^([A-G]#?)", chord)
    return m.group(1) if m else None


def hz_in_range(pc: str, lo: float, hi: float) -> float:
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


def assign_pcs_to_layers(
    pcs: list[str],
    chord: str | None,
    *,
    seg_index: int = 0,
) -> dict[str, list[tuple[str, float]]]:
    """Distribute chord tones by register so lanes don't all show the same stack.

    Returns layer_key → list of (pitch_class, hz).
    """
    clean = [p for p in pcs if p in PC_HZ][:5]
    out: dict[str, list[tuple[str, float]]] = {L.key: [] for L in LAYERS}
    if not clean:
        return out

    root = parse_chord_root(chord)
    if root not in PC_HZ:
        root = clean[0]

    uniq = list(dict.fromkeys(clean))
    sorted_pcs = sorted(uniq, key=lambda p: PC_INDEX[p])
    if root in sorted_pcs:
        sorted_pcs = [root] + [p for p in sorted_pcs if p != root]

    n = len(sorted_pcs)
    bass, cello, gA, gB, high = LAYERS

    def put(key: str, pc: str, lo: float, hi: float) -> None:
        hz = hz_in_range(pc, lo, hi)
        out[key].append((pc, hz))

    put("upright_bass", sorted_pcs[0], *bass.freq_range_hz)

    if n == 1:
        put("cello", sorted_pcs[0], *cello.freq_range_hz)
        return out

    if n == 2:
        put("cello", sorted_pcs[1], *cello.freq_range_hz)
        # alternate sparse mid between A / B so neither guitar lane is empty forever
        g = gA if (seg_index % 2 == 0) else gB
        put(g.key, sorted_pcs[1], *g.freq_range_hz)
        return out

    put("cello", sorted_pcs[1], *cello.freq_range_hz)
    mid = list(sorted_pcs[2:])

    # Highest extension → nylon/high; remaining mids split across guitar A / B
    if n >= 4 and mid:
        top = mid.pop()
        put("nylon_high", top, *high.freq_range_hz)
    elif n == 3 and mid:
        # light high sparkle on the lone mid when chords are thin
        put("nylon_high", mid[-1], *high.freq_range_hz)

    guitars = [gA, gB]
    # phase the round-robin so Guitar B isn't chronically starved
    phase = seg_index % 2
    for i, pc in enumerate(mid):
        g = guitars[(i + phase) % 2]
        put(g.key, pc, *g.freq_range_hz)

    return out


def style_fig(fig: plt.Figure) -> None:
    fig.patch.set_facecolor("#f7f5f1")


def build_layer_events(timeline: list[dict]) -> list[dict]:
    """Flatten timeline into per-layer colored events."""
    events = []
    for si, seg in enumerate(timeline):
        assigned = assign_pcs_to_layers(
            list(seg.get("pcs") or []), seg.get("chord"), seg_index=si
        )
        for L in LAYERS:
            notes = assigned[L.key]
            if not notes:
                continue
            events.append(
                {
                    "start": float(seg["start"]),
                    "end": float(seg["end"]),
                    "chord": seg.get("chord"),
                    "layer": L.key,
                    "notes": notes,
                    "pcs": [pc for pc, _ in notes],
                }
            )
    return events


def plot_layered_timeline(timeline: list[dict], duration: float, path: Path) -> None:
    """Stacked horizontal lanes — one musician per row (bass at bottom)."""
    n = len(LAYERS)
    fig = plt.figure(figsize=(16.5, 10.4))
    style_fig(fig)
    gs = fig.add_gridspec(n, 1, left=0.14, right=0.97, top=0.88, bottom=0.22, hspace=0.18)

    events = build_layer_events(timeline)
    by_layer: dict[str, list[dict]] = {L.key: [] for L in LAYERS}
    for ev in events:
        by_layer[ev["layer"]].append(ev)

    # Draw high→low top-to-bottom so upright bass sits at the bottom (DAW-like)
    draw_order = list(reversed(LAYERS))
    for row, L in enumerate(draw_order):
        ax = fig.add_subplot(gs[row, 0])
        ax.set_facecolor(L.lane_tint)
        for ev in by_layer[L.key]:
            pcs = ev["pcs"]
            if not pcs:
                continue
            h = 0.78 / max(1, len(pcs))
            for j, pc in enumerate(pcs):
                ax.add_patch(
                    Rectangle(
                        (ev["start"], 0.12 + j * h),
                        ev["end"] - ev["start"],
                        h * 0.92,
                        facecolor=pc_rgb(pc),
                        edgecolor="white",
                        linewidth=0.25,
                        alpha=0.95,
                    )
                )
        ax.set_xlim(0, duration)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.5])
        ax.set_yticklabels([L.display], fontsize=10, fontweight="bold")
        is_bottom = row == n - 1
        ax.tick_params(axis="x", labelbottom=is_bottom)
        if is_bottom:
            ax.set_xlabel("Temps (s) / Time (s)", fontsize=11)
        else:
            ax.set_xticklabels([])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("0.55")
        ax.text(
            0.995,
            0.92,
            L.role,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color="0.4",
            style="italic",
        )

    fig.suptitle(
        "Qui joue quel crayon / Who plays which crayon\n"
        "Une rangée = un musicien (basse en bas) · couleur = son · chacun a sa tranche",
        fontsize=12.5,
        fontweight="bold",
        y=0.955,
    )
    draw_color_legend(fig, y=0.015, height=0.14)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_layer_sync(
    timeline: list[dict], duration: float, path: Path
) -> tuple[list[float], list[float]]:
    """Show vertical alignment (full ensemble) vs thin / staggered texture."""
    events = build_layer_events(timeline)
    n = len(LAYERS)

    fig = plt.figure(figsize=(16.5, 10.6))
    style_fig(fig)
    ax = fig.add_axes([0.14, 0.38, 0.83, 0.50])
    ax.set_facecolor("#eceae4")

    # bass at bottom (y=0)
    for i, L in enumerate(LAYERS):
        ax.axhspan(i - 0.42, i + 0.42, color=L.lane_tint, zorder=0)
        for ev in (e for e in events if e["layer"] == L.key):
            pc = ev["pcs"][0]
            ax.barh(
                i,
                ev["end"] - ev["start"],
                left=ev["start"],
                height=0.62,
                color=pc_rgb(pc),
                edgecolor="white",
                linewidth=0.2,
                alpha=0.92,
                align="center",
            )
            if ev["end"] - ev["start"] >= 0.55:
                ax.text(
                    0.5 * (ev["start"] + ev["end"]),
                    i,
                    PC_FR.get(pc, pc),
                    ha="center",
                    va="center",
                    fontsize=5.5,
                    color="0.15",
                    alpha=0.55,
                )

    # Per chord segment: how many layers are lit?
    full_times: list[float] = []
    thin_times: list[float] = []
    layer_counts: list[tuple[float, float, int]] = []  # start, end, count

    for si, seg in enumerate(timeline):
        assigned = assign_pcs_to_layers(
            list(seg.get("pcs") or []), seg.get("chord"), seg_index=si
        )
        count = sum(1 for L in LAYERS if assigned[L.key])
        t0, t1 = float(seg["start"]), float(seg["end"])
        mid = 0.5 * (t0 + t1)
        layer_counts.append((t0, t1, count))
        if count >= 4:
            full_times.append(mid)
            ax.axvline(t0, color="#111111", lw=1.15, alpha=0.55, zorder=5)
        elif count <= 2:
            thin_times.append(mid)
            ax.axvline(t0, color="#886622", lw=0.9, alpha=0.45, linestyle="--", zorder=4)

    ax.set_xlim(0, duration)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks(range(n))
    ax.set_yticklabels([L.display for L in LAYERS], fontsize=10, fontweight="bold")
    ax.set_xlabel("Temps (s) / Time (s)", fontsize=11)
    ax.set_title(
        "Quand les crayons changent ensemble / When the crayons change together\n"
        "Ligne noire = tout le monde joue en même temps  ·  "
        "ligne ambre pointillée = quelques crayons seulement",
        fontsize=12,
        fontweight="bold",
        pad=8,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Bottom: how many musicians are sounding
    ax2 = fig.add_axes([0.14, 0.22, 0.83, 0.09])
    ax2.set_facecolor("#e8e4dc")
    for t0, t1, count in layer_counts:
        if count >= 4:
            color = "#1a1a1a"
        elif count == 3:
            color = "#5a7d9a"
        else:
            color = "#c4a35a"
        ax2.bar(
            0.5 * (t0 + t1),
            count,
            width=max(0.12, t1 - t0),
            color=color,
            alpha=0.85,
            align="center",
            edgecolor="none",
        )
    ax2.axhline(4, color="0.35", lw=0.7, linestyle=":", alpha=0.6)
    ax2.set_xlim(0, duration)
    ax2.set_ylim(0, 5.5)
    ax2.set_yticks([1, 2, 3, 4, 5])
    ax2.set_ylabel("#\nmusiciens", fontsize=8)
    ax2.set_xlabel(
        "Combien de musiciens jouent  ·  noir=tous / bleu=3 / ambre=peu",
        fontsize=9,
    )
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    draw_color_legend(fig, y=0.015, height=0.14)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return full_times, thin_times


def plot_facet_pngs(timeline: list[dict], duration: float, out_dir: Path) -> list[Path]:
    """One small PNG per instrument lane."""
    out_dir.mkdir(parents=True, exist_ok=True)
    events = build_layer_events(timeline)
    paths: list[Path] = []
    for L in LAYERS:
        fig = plt.figure(figsize=(12, 3.6))
        style_fig(fig)
        ax = fig.add_axes([0.06, 0.42, 0.90, 0.42])
        ax.set_facecolor(L.lane_tint)
        for ev in (e for e in events if e["layer"] == L.key):
            pcs = ev["pcs"]
            h = 0.78 / max(1, len(pcs))
            for j, pc in enumerate(pcs):
                ax.add_patch(
                    Rectangle(
                        (ev["start"], 0.12 + j * h),
                        ev["end"] - ev["start"],
                        h * 0.92,
                        facecolor=pc_rgb(pc),
                        edgecolor="white",
                        linewidth=0.25,
                    )
                )
        ax.set_xlim(0, duration)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xlabel("Temps (s) / Time (s)", fontsize=9)
        ax.set_title(f"{L.display}  —  {L.role}", fontsize=11, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        draw_color_legend(fig, y=0.03, height=0.28, show_a440_hint=False)
        path = out_dir / f"layer_{L.key}.png"
        fig.savefig(path, dpi=140, facecolor=fig.get_facecolor())
        plt.close(fig)
        paths.append(path)
    return paths


def write_md(
    path: Path,
    duration: float,
    n_segs: int,
    full_times: list[float],
    thin_times: list[float],
    facet_paths: list[Path],
    *,
    chords: str,
) -> None:
    facet_list = "\n".join(f"- `{p.name}`" for p in facet_paths)
    layer_rows = "\n".join(
        f"| {L.display} | {L.role} | {L.freq_range_hz[0]:.0f}–{L.freq_range_hz[1]:.0f} Hz |"
        for L in LAYERS
    )
    legend_rows = legend_markdown_rows()
    md = f"""# Accords par musicien — boîte de crayons
# Chord visuals by musician — crayon box

Pour les petits génies (~7–8 ans).
Chaque **rangée** = un musicien en bois. La couleur = le crayon macOS
(Do=Maraschino … La=Blueberry≈440 Hz … Si=Magenta) — **toujours la même règle**.

Palette = **macOS Color Picker crayons** (`NSColorList` « Crayons » /
`/System/Library/Colors/Crayons.clr`).

## Comment lire / How to read

1. **Haut/bas = qui.** Nylon/aigu en haut ; contrebasse en bas.
2. **Barre colorée** = ce musicien tient ce crayon-son.
3. **Couleurs différentes en même temps** = l’accord est partagé
   (basse prend le sol, violoncelle le suivant, guitares le milieu, aigu les étincelles).
4. **Trou dans une rangée** = ce musicien se tait un moment.
5. Lis d’abord le **français (Do Ré Mi…)**, puis l’anglais, puis le **nom du crayon macOS**, puis la petite partition, puis ~Hz.

## Boîte de crayons / Crayon box

Astuce : **Blueberry = La / A** — la note que les orchestres accordent (~440 Hz).

| Français | English | Crayon macOS | ~Hz | RGB |
|----------|---------|--------------|-----|-----|
{legend_rows}

## Les cinq musiciens (bois seulement — pas de clarinette)

| Rangée | Rôle | Registre |
|--------|------|----------|
{layer_rows}

## Images / Pictures

### 1. Qui joue quel crayon / Who plays which crayon
`chord_layers_timeline.png`

Cinq panneaux empilés. Gauche→droite = temps ; haut/bas = qui.

### 2. Quand les crayons changent ensemble / When the crayons change together
`chord_layers_sync.png`

- **Ligne noire** → **tout le monde joue en même temps** (≥4 rangées)
- **Ligne ambre pointillée** → **quelques crayons seulement** (≤2 rangées)
- Bande du bas → combien de musiciens sonnent (noir=tous, bleu=3, ambre=peu)

Sur ce take (~{duration:.0f}s, {n_segs} segments) :
- tout le monde ensemble : **{len(full_times)}**
- quelques crayons seulement : **{len(thin_times)}**

### 3. Un PNG par musicien / One PNG per musician
`chord_layers_facets/`

{facet_list}

## Ce que ça raconte / Plain story

La basse et le violoncelle peignent surtout le **plancher chaud**.
Les guitares A/B se partagent le **milieu** (pas les mêmes crayons tout le temps).
L’aigu s’allume quand il y a des **notes en plus en haut**.
Lignes noires = tout le monde change ensemble ; lignes ambre = texture mince.

## Source

- Accords: `{chords}`
- Ensemble: wooden-chord layers only (no clarinet)
- Couleurs: `scripts/chord_pitch_colors.py` (macOS Crayons.clr — même boîte que `chord_visual_analysis.md`)
"""
    path.write_text(md, encoding="utf-8")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chords", type=Path, default=CHORD_JSON)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    if not args.chords.is_file():
        raise SystemExit(f"missing chord JSON: {args.chords}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.chords.read_text())
    timeline = data["timeline"]
    duration = chord_duration(data)

    p_timeline = args.out_dir / "chord_layers_timeline.png"
    p_sync = args.out_dir / "chord_layers_sync.png"
    facet_dir = args.out_dir / "chord_layers_facets"
    p_md = args.out_dir / "chord_visual_layers.md"

    print("plotting layered timeline…")
    plot_layered_timeline(timeline, duration, p_timeline)

    print("plotting sync figure…")
    full_times, thin_times = plot_layer_sync(timeline, duration, p_sync)

    print("plotting faceted PNGs…")
    facet_paths = plot_facet_pngs(timeline, duration, facet_dir)

    write_md(
        p_md,
        duration,
        len(timeline),
        full_times,
        thin_times,
        facet_paths,
        chords=display_path(args.chords),
    )

    print(f"wrote {p_timeline}")
    print(f"wrote {p_sync}")
    for p in facet_paths:
        print(f"wrote {p}")
    print(f"wrote {p_md}")
    print(f"full_band={len(full_times)} thin={len(thin_times)}")


if __name__ == "__main__":
    main()
