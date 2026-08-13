#!/usr/bin/env python3
"""Shared pitch→macOS pencil color system + kid-genius bilingual legend.

French solfège (fixed Do) first, then English letter names, macOS Color Picker
crayon/pencil name, ~Hz, and a tiny treble-staff note picture.
Same pencil color always means the same pitch class.

Palette source: macOS `NSColorList` named **Crayons**
(`/System/Library/Colors/Crayons.clr`) — the Color Picker crayon/pencil selector.
RGB values are genericRGB components from that catalog (queried on macOS).
"""
from __future__ import annotations

import math
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Ellipse, FancyBboxPatch

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Fixed Do solfège (Québec / France style). Sharps preferred for chromatic steps.
PC_FR = {
    "C": "Do",
    "C#": "Do♯",
    "D": "Ré",
    "D#": "Ré♯",
    "E": "Mi",
    "F": "Fa",
    "F#": "Fa♯",
    "G": "Sol",
    "G#": "Sol♯",
    "A": "La",
    "A#": "La♯",
    "B": "Si",
}

# Official macOS Crayons.clr pencil names (Color Picker crayon selector).
# Chromatic vivid set around the wheel; "Lime" is the electric lime pencil;
# "Maraschino" is the cherry-red pencil; "Tangerine" is the orange pencil.
PC_PENCIL = {
    "C": "Maraschino",
    "C#": "Cayenne",
    "D": "Tangerine",
    "D#": "Lemon",
    "E": "Lime",
    "F": "Spring",
    "F#": "Fern",
    "G": "Spindrift",
    "G#": "Sky",
    "A": "Blueberry",
    "A#": "Grape",
    "B": "Magenta",
}

# genericRGB 0–255 from NSColorList("Crayons") on macOS.
_PC_RGB_255 = {
    "C": (251, 2, 7),  # Maraschino
    "C#": (128, 0, 2),  # Cayenne
    "D": (253, 128, 8),  # Tangerine
    "D#": (255, 255, 10),  # Lemon
    "E": (128, 255, 8),  # Lime (electric lime)
    "F": (33, 255, 6),  # Spring
    "F#": (64, 128, 2),  # Fern
    "G": (102, 255, 204),  # Spindrift
    "G#": (102, 204, 255),  # Sky
    "A": (0, 0, 255),  # Blueberry
    "A#": (128, 0, 255),  # Grape
    "B": (251, 2, 255),  # Magenta
}

# On-screen enamel (same hue, lower sat, mid lightness). Keyboard uses these;
# matplotlib legends keep canonical crayon_rgb / _PC_RGB_255.
_PC_DISPLAY_RGB_255 = {
    "C": (196, 59, 61),  # Maraschino
    "C#": (159, 56, 57),  # Cayenne
    "D": (201, 131, 64),  # Tangerine
    "D#": (201, 201, 115),  # Lemon
    "E": (121, 176, 69),  # Lime
    "F": (75, 171, 63),  # Spring
    "F#": (101, 143, 61),  # Fern
    "G": (71, 174, 140),  # Spindrift
    "G#": (76, 151, 189),  # Sky
    "A": (69, 69, 186),  # Blueberry
    "A#": (128, 69, 186),  # Grape
    "B": (185, 79, 186),  # Magenta
}

PC_RGB = {n: (r / 255.0, g / 255.0, b / 255.0) for n, (r, g, b) in _PC_RGB_255.items()}
PC_DISPLAY_RGB = {
    n: (r / 255.0, g / 255.0, b / 255.0) for n, (r, g, b) in _PC_DISPLAY_RGB_255.items()
}
crayon_rgb = _PC_RGB_255
display_rgb = _PC_DISPLAY_RGB_255

# Back-compat alias: code that checked membership in PC_HUES still works.
PC_HUES = PC_RGB

# Approx mid-register reference Hz (octave 4), A4=440
PC_HZ = {
    "C": 261.63,
    "C#": 277.18,
    "D": 293.66,
    "D#": 311.13,
    "E": 329.63,
    "F": 349.23,
    "F#": 369.99,
    "G": 392.00,
    "G#": 415.30,
    "A": 440.00,
    "A#": 466.16,
    "B": 493.88,
}

# Treble-staff staff-step for octave-4 representatives (E4 bottom line = 0).
PC_STAFF_STEP = {
    "C": -1.5,
    "C#": -1.5,
    "D": -1.0,
    "D#": -1.0,
    "E": 0.0,
    "F": 0.5,
    "F#": 0.5,
    "G": 1.0,
    "G#": 1.0,
    "A": 1.5,
    "A#": 1.5,
    "B": 2.0,
}

PC_IS_SHARP = {n: "#" in n for n in NOTE_NAMES}

_MUSIC_FONT_PATH: str | None = None
_MUSIC_FONT_RESOLVED = False


def _music_font(size: float = 9.0) -> FontProperties | None:
    """Prefer a system font that has the treble-clef glyph."""
    global _MUSIC_FONT_PATH, _MUSIC_FONT_RESOLVED
    if not _MUSIC_FONT_RESOLVED:
        _MUSIC_FONT_RESOLVED = True
        for p in (
            Path("/System/Library/Fonts/Apple Symbols.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ):
            if p.is_file():
                _MUSIC_FONT_PATH = str(p)
                break
    if _MUSIC_FONT_PATH is None:
        return None
    return FontProperties(fname=_MUSIC_FONT_PATH, size=size)


def _luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pc_text_color(name: str) -> str:
    """White text on dark pencils; dark text on bright pencils."""
    return "white" if _luminance(PC_RGB[name]) < 0.45 else "0.05"


def pc_rgb(
    name: str,
    value: float = 1.0,
    saturation: float = 1.0,
) -> tuple[float, float, float]:
    """Return macOS pencil RGB in 0–1. Optional value/sat for heatmap blending."""
    r, g, b = PC_RGB[name]
    if saturation != 1.0:
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        r = gray + (r - gray) * saturation
        g = gray + (g - gray) * saturation
        b = gray + (b - gray) * saturation
    if value != 1.0:
        r, g, b = r * value, g * value, b * value
    return (max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b)))


def pc_label_fr_en(name: str) -> str:
    return f"{PC_FR[name]} / {name}"


def pc_label_full(name: str) -> str:
    """Kid-genius label: FR / EN · Pencil · ~Hz."""
    return f"{PC_FR[name]} / {name} · {PC_PENCIL[name]} · {pc_hz_short(name)}"


def pc_hz_short(name: str) -> str:
    return f"~{int(round(PC_HZ[name]))} Hz"


def _draw_simple_clef(ax, x: float, y: float, h: float) -> None:
    """Fallback hand-drawn G-clef swirl when no music font is available."""
    ax.plot([x, x], [y - h * 0.15, y + h * 0.95], color="0.1", lw=1.1, zorder=8)
    theta = [i * 0.35 for i in range(18)]
    xs = [x + 0.07 * math.cos(t) + 0.02 for t in theta]
    ys = [y + h * 0.55 + 0.09 * math.sin(t) for t in theta]
    ax.plot(xs, ys, color="0.1", lw=1.0, zorder=8)
    ax.plot(
        [x, x + 0.05, x + 0.02],
        [y - h * 0.05, y - h * 0.18, y - h * 0.05],
        color="0.1",
        lw=1.0,
        zorder=8,
    )


def draw_mini_staff(
    ax,
    cx: float,
    cy: float,
    pc: str,
    *,
    width: float = 0.72,
    height: float = 0.38,
) -> None:
    """Tiny treble-staff snippet with one notehead for this pitch class."""
    step = PC_STAFF_STEP[pc]
    sharp = PC_IS_SHARP[pc]

    x0 = cx - width / 2
    y0 = cy - height / 2
    ax.add_patch(
        FancyBboxPatch(
            (x0 - 0.02, y0 - 0.02),
            width + 0.04,
            height + 0.04,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            facecolor="#fffcf7",
            edgecolor="0.45",
            linewidth=0.4,
            zorder=6,
        )
    )

    line_gap = height / 4.5
    for i in range(5):
        yy = y0 + 0.08 + i * line_gap
        ax.plot(
            [x0 + 0.06, x0 + width - 0.04],
            [yy, yy],
            color="0.15",
            lw=0.55,
            solid_capstyle="butt",
            zorder=7,
        )

    fp = _music_font(size=max(8.0, height * 22))
    if fp is not None:
        ax.text(
            x0 + 0.01,
            y0 + height * 0.42,
            "𝄞",
            fontproperties=fp,
            ha="left",
            va="center",
            color="0.1",
            zorder=8,
            clip_on=False,
        )
    else:
        _draw_simple_clef(ax, x0 + 0.10, y0 + 0.08, height * 0.85)

    nx = x0 + width * (0.64 if sharp else 0.58)
    ny = y0 + 0.08 + step * line_gap

    if step <= -1.5:
        mid_c_y = y0 + 0.08 + (-1.5) * line_gap
        ax.plot(
            [nx - 0.11, nx + 0.11],
            [mid_c_y, mid_c_y],
            color="0.15",
            lw=0.55,
            zorder=7,
        )

    if sharp:
        ax.text(
            nx - 0.15,
            ny,
            "♯",
            fontsize=8,
            ha="center",
            va="center",
            color="0.1",
            fontweight="bold",
            zorder=8,
        )

    ax.add_patch(
        Ellipse(
            (nx, ny),
            width=0.13,
            height=line_gap * 0.95,
            facecolor="0.08",
            edgecolor="0.08",
            zorder=9,
            angle=-20,
        )
    )


def draw_color_legend(
    fig: Figure,
    *,
    y: float = 0.015,
    height: float = 0.14,
    x: float = 0.04,
    width: float = 0.92,
    title: str | None = None,
    show_a440_hint: bool = True,
) -> None:
    """Kid-genius crayon box: FR → EN → macOS pencil → Hz → staff glyph."""
    if title is None:
        title = (
            "BOÎTE DE CRAYONS macOS / macOS CRAYON BOX  —  "
            "même couleur = même son  ·  same pencil = same pitch"
        )

    ax = fig.add_axes([x, y, width, height])
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 1.15)
    ax.axis("off")

    ax.add_patch(
        FancyBboxPatch(
            (-0.05, 0.02),
            12.1,
            1.08,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor="#fff8ee",
            edgecolor="0.25",
            linewidth=1.4,
            zorder=0,
        )
    )

    ax.set_title(title, fontsize=9.5, fontweight="bold", pad=2, loc="left", color="0.12")

    for i, name in enumerate(NOTE_NAMES):
        color = pc_rgb(name)
        text_color = pc_text_color(name)
        ax.add_patch(
            FancyBboxPatch(
                (i + 0.05, 0.10),
                0.90,
                0.88,
                boxstyle="round,pad=0.02,rounding_size=0.10",
                facecolor=color,
                edgecolor="0.12",
                linewidth=1.1,
                zorder=1,
            )
        )
        fr = PC_FR[name]
        pencil = PC_PENCIL[name]
        ax.text(
            i + 0.5,
            0.90,
            fr,
            ha="center",
            va="center",
            fontsize=8.5,
            color=text_color,
            fontweight="bold",
            zorder=2,
        )
        ax.text(
            i + 0.5,
            0.76,
            f"{name} · {pencil}",
            ha="center",
            va="center",
            fontsize=5.4,
            color=text_color,
            fontweight="bold",
            zorder=2,
        )
        ax.text(
            i + 0.5,
            0.62,
            f"~{int(round(PC_HZ[name]))} Hz",
            ha="center",
            va="center",
            fontsize=5.5,
            color=text_color,
            alpha=0.95,
            zorder=2,
        )
        draw_mini_staff(ax, i + 0.5, 0.32, name, width=0.78, height=0.32)

    if show_a440_hint:
        ax.text(
            6.0,
            0.04,
            "Astuce / Tip:  Blueberry = La / A  —  la note que les orchestres accordent (~440 Hz)",
            ha="center",
            va="bottom",
            fontsize=7,
            color="0.25",
            style="italic",
            zorder=3,
        )


def legend_markdown_rows() -> str:
    """Markdown table rows for docs (FR | EN | Pencil | Hz | RGB)."""
    lines = []
    for name in NOTE_NAMES:
        fr = PC_FR[name]
        hz = int(round(PC_HZ[name]))
        pencil = PC_PENCIL[name]
        r, g, b = _PC_RGB_255[name]
        bold = "**" if name == "A" else ""
        lines.append(
            f"| {bold}{fr}{bold} | {bold}{name}{bold} | {bold}{pencil}{bold} | "
            f"{bold}~{hz}{bold} | `rgb({r},{g},{b})` |"
        )
    return "\n".join(lines)
