#!/usr/bin/env python3
"""Color-first chord visual analysis for sensory / kid-genius readers."""
from __future__ import annotations

import json
import math
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chord_pitch_colors import (  # noqa: E402
    NOTE_NAMES,
    PC_FR,
    PC_HUES,
    PC_HZ,
    PC_PENCIL,
    draw_color_legend,
    legend_markdown_rows,
    pc_rgb,
)

ROOT = Path(__file__).resolve().parents[1]
WAV = ROOT / "captures" / "final_song.wav"
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


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise SystemExit(f"Expected 16-bit PCM, got sample width {sw}")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    x /= 32768.0
    return x, sr


def compute_chroma(x: np.ndarray, sr: int, hop_sec: float = 0.125, n_fft: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    """Return (chroma[12, T], times[T]). Bass slightly boosted; no vocal blanket."""
    hop = max(1, int(hop_sec * sr))
    win = np.hanning(n_fft)
    frames = []
    times = []
    rms_list = []
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    for start in range(0, max(0, len(x) - n_fft + 1), hop):
        seg = x[start : start + n_fft]
        rms = float(np.sqrt(np.mean(seg * seg)))
        mag = np.abs(np.fft.rfft(seg * win))
        chroma = np.zeros(12, dtype=np.float64)
        for i, f in enumerate(freqs):
            if f < 55 or f > 4200:
                continue
            w = 1.25 if f < 200 else 1.0
            midi = 69.0 + 12.0 * math.log2(f / 440.0)
            pc = int(round(midi)) % 12
            chroma[pc] += mag[i] * w
        frames.append(chroma)
        times.append((start + n_fft / 2) / sr)
        rms_list.append(rms)
    if not frames:
        return np.zeros((12, 1)), np.array([0.0])
    chroma_m = np.stack(frames, axis=1)
    rms_a = np.asarray(rms_list)
    thr = max(0.008, float(np.percentile(rms_a, 40)) * 0.45)
    # Keep absolute energy (not per-frame unit-sum) so quiet gaps go dark;
    # scale each active frame by its own max so colors stay readable.
    out = np.zeros_like(chroma_m)
    for t in range(chroma_m.shape[1]):
        if rms_a[t] < thr:
            continue
        col = chroma_m[:, t]
        m = float(col.max())
        if m > 1e-12:
            out[:, t] = (col / m) ** 1.15
    return out, np.asarray(times)


def style_fig(fig: plt.Figure) -> None:
    fig.patch.set_facecolor("#f7f5f1")

def ordered_pcs(pcs: list[str]) -> list[str]:
    """Unique pitch classes sorted low→high on the color wheel (C … B)."""
    seen = []
    for p in pcs:
        if p in PC_HUES and p not in seen:
            seen.append(p)
    return sorted(seen, key=lambda p: NOTE_NAMES.index(p))


def plot_progression_stacks(timeline: list[dict], duration: float, path: Path) -> None:
    fig = plt.figure(figsize=(16, 8.4))
    style_fig(fig)
    ax = fig.add_axes([0.06, 0.30, 0.88, 0.58])
    ax.set_facecolor("#eceae4")

    for seg in timeline:
        seen = ordered_pcs(seg["pcs"])
        if not seen:
            continue
        n = len(seen)
        h = 1.0 / n
        for i, p in enumerate(seen):
            # vertical = frequency order (Do/C near bottom, Si/B near top)
            ax.barh(
                i * h + h / 2,
                seg["end"] - seg["start"],
                left=seg["start"],
                height=h * 0.92,
                color=pc_rgb(p),
                edgecolor="white",
                linewidth=0.3,
                align="center",
            )
        # thin black tick at change
        ax.axvline(seg["start"], color="0.35", lw=0.4, alpha=0.5)

    ax.set_xlim(0, duration)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("Temps (secondes) / Time (seconds)", fontsize=11)
    ax.set_title(
        "Sandwich de crayons / Color sandwich over time\n"
        "Chaque tranche = un accord · chaque couche de couleur = un son (Do en bas → Si en haut)",
        fontsize=12.5,
        fontweight="bold",
        pad=10,
    )
    # optional tiny chord labels along top
    for seg in timeline:
        mid = 0.5 * (seg["start"] + seg["end"])
        if seg["end"] - seg["start"] >= 0.45:
            ax.text(
                mid,
                1.02,
                seg["chord"],
                ha="center",
                va="bottom",
                fontsize=5.5,
                rotation=70,
                color="0.35",
                clip_on=False,
            )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    draw_color_legend(fig, y=0.02, height=0.15)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_sync_dwell(timeline: list[dict], duration: float, path: Path) -> None:
    fig = plt.figure(figsize=(16, 9.2))
    style_fig(fig)
    ax = fig.add_axes([0.06, 0.40, 0.88, 0.46])
    ax.set_facecolor("#eceae4")

    dwells = []
    for idx, seg in enumerate(timeline):
        dwell = seg["end"] - seg["start"]
        dwells.append(dwell)
        pcs = ordered_pcs(seg["pcs"])
        # stacked color stem at mid-time; height = dwell; vertical = pitch order
        x = 0.5 * (seg["start"] + seg["end"])
        if not pcs:
            continue
        n = len(pcs)
        for i, p in enumerate(pcs):
            ax.bar(
                x,
                dwell / n,
                bottom=i * (dwell / n),
                width=max(0.18, dwell * 0.85),
                color=pc_rgb(p),
                edgecolor="white",
                linewidth=0.25,
                align="center",
            )
        # change markers
        ax.plot([seg["start"], seg["start"]], [0, dwell], color="0.25", lw=0.7, alpha=0.7)

    # dwell envelope line
    mids = [0.5 * (s["start"] + s["end"]) for s in timeline]
    ax.plot(
        mids,
        dwells,
        color="0.15",
        lw=1.2,
        alpha=0.55,
        label="durée / how long it stays",
    )

    ax.set_xlim(0, duration)
    ax.set_ylim(0, max(dwells) * 1.25 if dwells else 1)
    ax.set_xlabel("Temps (secondes) / Time (seconds)", fontsize=11)
    ax.set_ylabel("Combien de temps ça reste (s)", fontsize=10)
    ax.set_title(
        "Quand les crayons changent / When the crayons change\n"
        "Barres hautes = l’accord reste longtemps · barres courtes = changement rapide",
        fontsize=12.5,
        fontweight="bold",
        pad=10,
    )
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # histogram of dwell times under
    ax2 = fig.add_axes([0.06, 0.24, 0.88, 0.09])
    ax2.set_facecolor("#eceae4")
    bins = np.linspace(0, (max(dwells) if dwells else 0.0) + 0.05, 12)
    ax2.hist(dwells, bins=bins, color="#5a7d9a", edgecolor="white", alpha=0.85)
    ax2.set_xlabel(
        "Durée (secondes) — la plupart des accords sont des flashs courts",
        fontsize=9,
    )
    ax2.set_ylabel("compte", fontsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    draw_color_legend(fig, y=0.015, height=0.14)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_chroma_heatmap(chroma: np.ndarray, times: np.ndarray, timeline: list[dict], path: Path) -> None:
    """Rows = pitch classes colored by fixed hue; brightness = energy over time."""
    fig = plt.figure(figsize=(16, 8.6))
    style_fig(fig)
    ax = fig.add_axes([0.12, 0.28, 0.84, 0.58])

    T = chroma.shape[1]
    # Build RGBA image: each row tinted by PC hue, alpha/brightness from chroma
    img = np.ones((12, T, 4), dtype=np.float64)
    vmax = float(np.percentile(chroma, 98)) or 1.0
    for pc, name in enumerate(NOTE_NAMES):
        base = np.array(pc_rgb(name, value=0.95, saturation=0.98))
        energy = np.clip(chroma[pc] / vmax, 0, 1)
        # low energy → washed background; high → vivid color
        for t in range(T):
            e = float(energy[t])
            # blend toward paper when quiet
            paper = np.array([0.93, 0.91, 0.87])
            rgb = paper * (1 - e) + base * e
            img[pc, t, :3] = rgb
            img[pc, t, 3] = 1.0

    extent = [float(times[0]), float(times[-1]), -0.5, 11.5]
    ax.imshow(img, aspect="auto", origin="lower", extent=extent, interpolation="nearest")

    # chord segment boundaries
    for seg in timeline:
        ax.axvline(seg["start"], color="0.15", lw=0.35, alpha=0.35)

    ax.set_yticks(range(12))
    ax.set_yticklabels([])
    for i, name in enumerate(NOTE_NAMES):
        ax.text(
            -0.02 * (times[-1] - times[0]),
            i,
            "■",
            color=pc_rgb(name),
            fontsize=14,
            ha="right",
            va="center",
            transform=ax.get_yaxis_transform(),
            clip_on=False,
        )
        ax.text(
            -0.055 * (times[-1] - times[0]),
            i,
            f"{PC_FR[name]} / {name}",
            color="0.25",
            fontsize=7.5,
            ha="right",
            va="center",
            transform=ax.get_yaxis_transform(),
            clip_on=False,
        )

    ax.set_xlabel("Temps (secondes) / Time (seconds)", fontsize=11)
    ax.set_ylabel("Crayon / Pitch (Do en bas → Si en haut)", fontsize=10)
    ax.set_title(
        "Carte des crayons dans le temps / Pitch-color map over time\n"
        "Bande brillante = ce crayon chante fort. Plusieurs bandes = plusieurs sons ensemble.",
        fontsize=12.5,
        fontweight="bold",
        pad=10,
    )
    draw_color_legend(fig, y=0.02, height=0.15)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_transition_network(timeline: list[dict], path: Path) -> None:
    fig = plt.figure(figsize=(14, 12.2))
    style_fig(fig)
    ax = fig.add_axes([0.04, 0.22, 0.92, 0.70])
    ax.set_facecolor("#f0eee8")
    ax.set_aspect("equal")
    ax.axis("off")

    # transitions
    pairs = list(zip([s["chord"] for s in timeline], [s["chord"] for s in timeline][1:]))
    trans = Counter((a, b) for a, b in pairs if a != b)
    # chord → most common pcs from timeline
    chord_pcs: dict[str, list[str]] = {}
    for seg in timeline:
        if seg["chord"] not in chord_pcs:
            chord_pcs[seg["chord"]] = ordered_pcs(seg["pcs"])

    counts = Counter(s["chord"] for s in timeline)
    nodes = sorted(counts.keys(), key=lambda c: -counts[c])
    # keep top nodes for readability + any with strong transitions
    top = set(nodes[:18])
    for (a, b), _ in trans.most_common(40):
        top.add(a)
        top.add(b)
    nodes = [n for n in nodes if n in top]
    n = len(nodes)
    if n == 0:
        fig.savefig(path)
        plt.close(fig)
        return

    # layout on circle
    angles = {nodes[i]: 2 * math.pi * i / n for i in range(n)}
    R = 3.6
    pos = {c: (R * math.cos(angles[c]), R * math.sin(angles[c])) for c in nodes}

    # edges
    max_w = max(trans.values()) if trans else 1
    for (a, b), w in trans.items():
        if a not in pos or b not in pos:
            continue
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        alpha = 0.15 + 0.7 * (w / max_w)
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="-|>",
                color=(0.2, 0.2, 0.25, alpha),
                lw=0.6 + 2.2 * (w / max_w),
                connectionstyle="arc3,rad=0.12",
                shrinkA=18,
                shrinkB=18,
            ),
        )

    # nodes as mini color pies of their pitch classes
    for c in nodes:
        x, y = pos[c]
        pcs = chord_pcs.get(c, [])
        size = 0.28 + 0.12 * math.log1p(counts[c])
        if not pcs:
            circ = plt.Circle((x, y), size, facecolor="0.7", edgecolor="0.2", lw=1.2, zorder=5)
            ax.add_patch(circ)
        else:
            # wedge pie
            theta0 = 90.0
            step = 360.0 / len(pcs)
            for i, p in enumerate(pcs):
                wedge = mpatches.Wedge(
                    (x, y),
                    size,
                    theta0 + i * step,
                    theta0 + (i + 1) * step,
                    facecolor=pc_rgb(p),
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=5,
                )
                ax.add_patch(wedge)
            ring = plt.Circle((x, y), size, facecolor="none", edgecolor="0.15", lw=1.4, zorder=6)
            ax.add_patch(ring)
        # small secondary text label
        ax.text(x, y - size - 0.18, c, ha="center", va="top", fontsize=7.5, color="0.25", zorder=7)

    ax.set_xlim(-5.2, 5.2)
    ax.set_ylim(-5.4, 5.2)
    ax.set_title(
        "Quel crayon suit quel crayon / Which colors follow which\n"
        "Chaque bulle = un accord en parts de couleur. Flèche = ce qui vient après (plus épais = plus souvent).",
        fontsize=12.5,
        fontweight="bold",
        pad=8,
    )
    draw_color_legend(fig, y=0.02, height=0.15)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def write_markdown(
    paths: dict[str, Path],
    timeline: list[dict],
    duration: float,
    *,
    out_dir: Path,
    wav: str,
    chords: str,
    heatmap: Path | None,
) -> Path:
    dwells = [s["end"] - s["start"] for s in timeline]
    med = float(np.median(dwells)) if dwells else 0.0
    # most common pcs by time-weight
    pc_time: dict[str, float] = defaultdict(float)
    for s in timeline:
        for p in set(s["pcs"]):
            if p in PC_HUES:
                pc_time[p] += s["end"] - s["start"]
    top_pcs = sorted(pc_time.items(), key=lambda kv: -kv[1])[:5]
    top_colors = ", ".join(
        f"{PC_FR[p]} / {p} · {PC_PENCIL[p]} (~{int(PC_HZ[p])} Hz)" for p, _ in top_pcs
    )
    legend_rows = legend_markdown_rows()

    md = f"""# Analyse visuelle des accords — langage des crayons
# Chord visual analysis — crayon language

Pour les petits génies (environ 7–8 ans) : on lit avec les **yeux et les couleurs**.
For little geniuses (~7–8): read with your **eyes and colors**.

**Règle magique / Magic rule:** la même couleur = toujours le même son.
Same color = always the same pitch. Forever. Predictable. Safe.

## La boîte de crayons / The crayon box (apprends une fois)

Palette = **macOS Color Picker crayons** (`NSColorList` « Crayons » /
`/System/Library/Colors/Crayons.clr`). Ex. Maraschino (cherry red), Lime
(electric lime), Tangerine (orange), Magenta, Grape…

Chaque crayon a **cinq** étiquettes :
1. **Français** — Do Ré Mi Fa Sol La Si (comme à l’école au Québec)
2. **Anglais** — C D E F G A B
3. **Nom du crayon macOS** — Maraschino, Lime, Blueberry…
4. **Petite partition** — la note écrite sur la portée (clef de sol)
5. **~Hz** — un tout petit chiffre (vitesse de vibration) — optionnel

Astuce : **Blueberry = La / A** — c’est la note que les orchestres utilisent pour s’accorder (~440 Hz).

| Français | English | Crayon macOS | ~Hz | RGB |
|----------|---------|--------------|-----|-----|
{legend_rows}

## Les images / The pictures

### 1. Carte des crayons / Pitch-color map
`{heatmap.name if heatmap is not None else "(skipped — no WAV)"}`

Les rangées sont les 12 crayons. Une **bande brillante** = ce crayon chante fort.
Plusieurs bandes ensemble = plusieurs sons en même temps (un accord).

### 2. Sandwich de crayons / Color sandwich
`{paths['stacks'].name}`

Chaque moment est un **sandwich de couleurs**. Regarde comment les couches changent.

### 3. Quand les crayons changent / When the crayons change
`{paths['sync'].name}`

- Barres **hautes** = l’accord reste longtemps
- Barres **courtes** = changement rapide  
Médiane ici ≈ **{med:.2f} s**.

### 4. Quel crayon suit quel crayon / Which colors follow which
`{paths['network'].name}`

Chaque bulle est un accord en parts de couleur. Les flèches montrent ce qui vient après
(plus épais = plus souvent). Tu peux suivre le voyage en couleurs seulement.

## Ce que ça raconte / What it feels like

Ce take (~{duration:.0f}s) change souvent (médiane ≈ {med:.2f}s).
Les crayons qu’on voit le plus : **{top_colors}**.
Parfois un seul crayon change ; parfois tout le sandwich se recolore.

## Source

- Audio: `{wav}`
- Accords: `{chords}`
- Couleurs partagées: `scripts/chord_pitch_colors.py` (macOS Crayons.clr)
"""
    out = out_dir / "chord_visual_analysis.md"
    out.write_text(md, encoding="utf-8")
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--wav",
        type=Path,
        default=None,
        help=f"audio for the chroma heatmap (default: {WAV}; skip if that file is missing)",
    )
    ap.add_argument("--chords", type=Path, default=CHORD_JSON)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    if not args.chords.is_file():
        raise SystemExit(f"missing chord JSON: {args.chords}")
    wav = args.wav if args.wav is not None else WAV
    wav_explicit = args.wav is not None

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.chords.read_text(encoding="utf-8"))
    timeline = data["timeline"]
    duration = chord_duration(data)

    paths = {
        "stacks": args.out_dir / "chord_progression_stacks.png",
        "sync": args.out_dir / "chord_sync_dwell.png",
        "network": args.out_dir / "chord_transition_network.png",
    }

    print("Plotting stacks…")
    plot_progression_stacks(timeline, duration, paths["stacks"])
    print("Plotting sync/dwell…")
    plot_sync_dwell(timeline, duration, paths["sync"])
    print("Plotting network…")
    plot_transition_network(timeline, paths["network"])
    heatmap: Path | None = None
    if wav.is_file():
        print("Loading WAV…")
        x, sr = load_wav(wav)
        print(f"sr={sr}, samples={len(x)}, dur={len(x)/sr:.2f}s")
        print("Computing chroma…")
        chroma, times = compute_chroma(x, sr)
        heatmap = args.out_dir / "chord_chroma_heatmap.png"
        print("Plotting heatmap…")
        plot_chroma_heatmap(chroma, times, timeline, heatmap)
    elif wav_explicit:
        raise SystemExit(f"missing WAV: {wav}")
    else:
        print(f"WAV missing ({wav}); skipping chroma heatmap")

    md = write_markdown(
        paths,
        timeline,
        duration,
        out_dir=args.out_dir,
        wav=display_path(wav),
        chords=display_path(args.chords),
        heatmap=heatmap,
    )
    print("Wrote", md)
    written = list(paths.values())
    if heatmap is not None:
        written.append(heatmap)
    for p in written:
        if p.is_file():
            print(f"{p.name}: {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
