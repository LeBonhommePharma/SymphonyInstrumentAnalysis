#!/usr/bin/env python3
"""Layered resynthesis from chord/frequency analysis only.

One stem per wooden musician/instrument (no clarinet). Notes are split by
register/role across layers; stems are written separately and also summed.
"""
from __future__ import annotations

import argparse
import json
import re
import wave
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CHORD_JSON = ROOT / "analysis_out" / "final_song_chords.json"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# Mid-register reference Hz (octave 4), A4=440
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
PC_INDEX = {pc: i for i, pc in enumerate(PC_HZ)}

SR = 44100
PREVIEW_SEC = 15.0


@dataclass(frozen=True)
class LayerSpec:
    key: str
    filename: str
    display: str
    role: str
    freq_range_hz: tuple[float, float]
    # harmonic amplitudes after fundamental (h2, h3, h4, ...)
    harmonics: tuple[float, ...]
    attack: float
    release: float
    sustain_decay: float
    amp: float
    # stereo pan -1..+1 for optional stereo mix; stems stay mono
    pan: float
    color: str


# Outdoor park wooden-chord ensemble (no clarinet)
LAYERS: list[LayerSpec] = [
    LayerSpec(
        key="upright_bass",
        filename="01_upright_bass.wav",
        display="Upright double bass",
        role="lowest pitch / root-ish floor",
        freq_range_hz=(55.0, 130.0),
        harmonics=(0.12, 0.04),
        attack=0.05,
        release=0.28,
        sustain_decay=0.22,
        amp=0.34,
        pan=-0.55,
        color="#8B5A2B",
    ),
    LayerSpec(
        key="cello",
        filename="02_cello.wav",
        display="Cello",
        role="low-mid wooden sustain",
        freq_range_hz=(130.0, 320.0),
        harmonics=(0.28, 0.12, 0.04),
        attack=0.06,
        release=0.24,
        sustain_decay=0.28,
        amp=0.26,
        pan=-0.25,
        color="#C47A3A",
    ),
    LayerSpec(
        key="guitar_a",
        filename="03_guitar_a.wav",
        display="Acoustic guitar 1 (steel)",
        role="mid chord body",
        freq_range_hz=(196.0, 440.0),
        harmonics=(0.38, 0.18, 0.10, 0.05),
        attack=0.018,
        release=0.16,
        sustain_decay=0.55,
        amp=0.22,
        pan=0.15,
        color="#2E8B57",
    ),
    LayerSpec(
        key="guitar_b",
        filename="04_guitar_b.wav",
        display="Acoustic guitar 2 (steel double)",
        role="mid chord body / alternate notes",
        freq_range_hz=(220.0, 494.0),
        harmonics=(0.42, 0.20, 0.12, 0.06),
        attack=0.022,
        release=0.15,
        sustain_decay=0.60,
        amp=0.20,
        pan=0.40,
        color="#3CB371",
    ),
    LayerSpec(
        key="nylon_guitar",
        filename="05_nylon_guitar.wav",
        display="Classical / nylon guitar",
        role="warm mid-high extensions",
        freq_range_hz=(247.0, 587.0),
        harmonics=(0.30, 0.14, 0.06),
        attack=0.028,
        release=0.18,
        sustain_decay=0.42,
        amp=0.18,
        pan=-0.05,
        color="#4682B4",
    ),
    LayerSpec(
        key="viola_sheen",
        filename="06_viola_sheen.wav",
        display="Viola / violin sheen",
        role="highest extension / sparkle",
        freq_range_hz=(392.0, 880.0),
        harmonics=(0.35, 0.22, 0.12, 0.07),
        attack=0.045,
        release=0.22,
        sustain_decay=0.30,
        amp=0.12,
        pan=0.55,
        color="#C0C0C0",
    ),
]


def soft_env(
    n: int,
    sr: int,
    attack: float,
    release: float,
    sustain_decay: float,
) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    dur = n / sr
    a = max(0.008, min(attack, dur * 0.35))
    r = max(0.04, min(release, dur * 0.55))
    env = np.ones(n, dtype=np.float64)
    na = int(a * sr)
    nr = int(r * sr)
    if na > 0:
        env[:na] = np.linspace(0.0, 1.0, na, endpoint=False) ** 0.7
    if nr > 0 and nr < n:
        sustain_end = n - nr
        if sustain_end > na:
            mid = t[na:sustain_end] - t[na]
            env[na:sustain_end] = np.exp(-sustain_decay * mid)
            end_level = float(env[sustain_end - 1]) if sustain_end > 0 else 1.0
        else:
            end_level = float(env[max(0, na - 1)]) if na else 1.0
            sustain_end = na
        rel = np.linspace(1.0, 0.0, nr, endpoint=True) ** 1.4
        env[sustain_end:] = end_level * rel
    elif nr >= n:
        env *= np.linspace(1.0, 0.0, n) ** 1.2
    return env


def tone_for_layer(freq: float, n: int, sr: int, layer: LayerSpec, seed: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    rng = np.random.default_rng(seed)
    phase0 = float(rng.random() * 2 * np.pi)
    sig = np.sin(2 * np.pi * freq * t + phase0)
    for hi, hamp in enumerate(layer.harmonics, start=2):
        ph = phase0 * (0.6 + 0.2 * hi) + float(rng.random())
        sig = sig + hamp * np.sin(2 * np.pi * (hi * freq) * t + ph)
    env = soft_env(n, sr, layer.attack, layer.release, layer.sustain_decay)
    return layer.amp * sig * env


def parse_chord_root(chord: str | None) -> str | None:
    if not chord:
        return None
    m = re.match(r"^([A-G]#?)", chord)
    if not m:
        return None
    return m.group(1)


def hz_in_range(pc: str, lo: float, hi: float) -> float:
    """Place pitch-class into [lo, hi] preferring the octave nearest the geometric mid."""
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
    # clamp soft
    return float(np.clip(best, lo * 0.9, hi * 1.1))


def assign_pcs_to_layers(pcs: list[str], chord: str | None) -> dict[str, list[float]]:
    """Distribute chord tones across musicians by register/role.

    - upright bass → lowest / root-ish
    - cello → low-mid
    - guitars → mid body/extensions split across A / B / nylon
    - viola sheen → highest extension (when available)
    """
    clean = [p for p in pcs if p in PC_HZ][:5]
    out: dict[str, list[float]] = {L.key: [] for L in LAYERS}
    if not clean:
        return out

    root = parse_chord_root(chord)
    if root not in PC_HZ:
        root = clean[0]

    # Sort unique pcs low→high by chroma for open voicing
    uniq = list(dict.fromkeys(clean))
    sorted_pcs = sorted(uniq, key=lambda p: PC_INDEX[p])

    # Prefer putting true root at the bottom of the stack when present
    if root in sorted_pcs:
        sorted_pcs = [root] + [p for p in sorted_pcs if p != root]

    n = len(sorted_pcs)
    bass_L = LAYERS[0]
    cello_L = LAYERS[1]
    gA, gB, nylon, viola = LAYERS[2], LAYERS[3], LAYERS[4], LAYERS[5]

    # Always give bass the root-ish lowest
    out["upright_bass"].append(hz_in_range(sorted_pcs[0], *bass_L.freq_range_hz))

    if n == 1:
        # soft cello octave support so the chord still has body
        out["cello"].append(hz_in_range(sorted_pcs[0], *cello_L.freq_range_hz))
        return out

    if n == 2:
        out["cello"].append(hz_in_range(sorted_pcs[1], *cello_L.freq_range_hz))
        out["guitar_a"].append(hz_in_range(sorted_pcs[1], *gA.freq_range_hz))
        return out

    # n >= 3: cello takes next-low; remaining split across guitars; top → viola if enough
    out["cello"].append(hz_in_range(sorted_pcs[1], *cello_L.freq_range_hz))

    mid = sorted_pcs[2:]
    if n >= 5:
        # highest extension to viola; rest to guitars
        top = mid[-1]
        mid = mid[:-1]
        out["viola_sheen"].append(hz_in_range(top, *viola.freq_range_hz))
    elif n == 4:
        # light viola on highest mid note (sparkle), also nylon gets it softer via split
        out["viola_sheen"].append(hz_in_range(mid[-1], *viola.freq_range_hz))

    guitar_layers = [gA, gB, nylon]
    for i, pc in enumerate(mid):
        L = guitar_layers[i % 3]
        out[L.key].append(hz_in_range(pc, *L.freq_range_hz))

    return out


def synthesize_layers(
    timeline: list[dict], duration_sec: float, sr: int = SR
) -> dict[str, np.ndarray]:
    n_total = int(round(duration_sec * sr))
    buffers = {L.key: np.zeros(n_total, dtype=np.float64) for L in LAYERS}
    layer_by_key = {L.key: L for L in LAYERS}

    for si, seg in enumerate(timeline):
        start = float(seg["start"])
        end = float(seg["end"])
        pcs = list(seg.get("pcs") or [])
        chord = seg.get("chord")
        if end <= start or not pcs:
            continue
        i0 = max(0, int(round(start * sr)))
        i1 = min(n_total, int(round(end * sr)))
        if i1 <= i0:
            continue
        n = i1 - i0
        fade = min(int(0.012 * sr), n // 4)
        assigned = assign_pcs_to_layers(pcs, chord)

        for key, freqs in assigned.items():
            if not freqs:
                continue
            layer = layer_by_key[key]
            chunk = np.zeros(n, dtype=np.float64)
            for fi, freq in enumerate(freqs):
                seed = (si * 9973 + fi * 131 + (zlib.adler32(key.encode()) % 10007)) & 0xFFFFFFFF
                # slight amp taper if a layer somehow gets multiple notes
                chunk += tone_for_layer(freq, n, sr, layer, seed) * (0.85**fi)
            if fade > 1:
                ramp = np.linspace(0.0, 1.0, fade)
                chunk[:fade] *= ramp
                chunk[-fade:] *= ramp[::-1]
            buffers[key][i0:i1] += chunk

    return buffers


def normalize_peak(audio: np.ndarray, peak_target: float = 0.85) -> np.ndarray:
    peak = float(np.max(np.abs(audio)))
    if peak > 1e-9:
        return audio * (peak_target / peak)
    return audio


def write_wav_mono(path: Path, audio: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm_i16 = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm_i16.tobytes())


def write_wav_stereo(path: Path, left: np.ndarray, right: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = min(len(left), len(right))
    interleaved = np.empty(n * 2, dtype=np.float64)
    interleaved[0::2] = left[:n]
    interleaved[1::2] = right[:n]
    pcm = np.clip(interleaved, -1.0, 1.0)
    pcm_i16 = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm_i16.tobytes())


def mix_stereo(buffers: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    n = len(next(iter(buffers.values())))
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)
    for L in LAYERS:
        mono = buffers[L.key]
        # equal-power pan
        angle = (L.pan + 1.0) * 0.25 * np.pi  # -1→0, +1→π/2
        gL = float(np.cos(angle))
        gR = float(np.sin(angle))
        left += mono * gL
        right += mono * gR
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    scale = 0.85 / peak
    return left * scale, right * scale


def mix_mono(buffers: dict[str, np.ndarray]) -> np.ndarray:
    mix = np.zeros_like(next(iter(buffers.values())))
    for L in LAYERS:
        mix += buffers[L.key]
    return normalize_peak(mix, 0.85)


def build_assignment_log(timeline: list[dict], max_rows: int = 12) -> list[str]:
    rows: list[str] = []
    for seg in timeline[:max_rows]:
        assigned = assign_pcs_to_layers(list(seg.get("pcs") or []), seg.get("chord"))
        parts = []
        for L in LAYERS:
            freqs = assigned[L.key]
            if freqs:
                hz = ", ".join(f"{f:.0f}Hz" for f in freqs)
                parts.append(f"{L.key}={hz}")
        rows.append(
            f"- **{seg['start']:.1f}–{seg['end']:.1f}s** `{seg.get('chord')}` "
            f"(pcs {', '.join(seg.get('pcs') or [])}) → " + "; ".join(parts)
        )
    return rows


def save_layer_figure(timeline: list[dict], duration: float, path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(12, 4.2))
    y_labels = [L.display for L in LAYERS]
    y_pos = {L.key: i for i, L in enumerate(LAYERS)}

    for seg in timeline:
        assigned = assign_pcs_to_layers(list(seg.get("pcs") or []), seg.get("chord"))
        start, end = float(seg["start"]), float(seg["end"])
        for L in LAYERS:
            if not assigned[L.key]:
                continue
            # color intensity by mean freq within layer range
            freqs = assigned[L.key]
            ax.barh(
                y_pos[L.key],
                end - start,
                left=start,
                height=0.7,
                color=L.color,
                alpha=0.75,
                edgecolor="none",
            )
            # annotate first freq lightly for a few segments
            if end - start >= 0.4 and start < 20:
                ax.text(
                    start + 0.02,
                    y_pos[L.key],
                    f"{freqs[0]:.0f}",
                    va="center",
                    ha="left",
                    fontsize=6,
                    color="#222",
                )

    ax.set_yticks(range(len(LAYERS)))
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Time (s)")
    ax.set_xlim(0, min(duration, 75))
    ax.set_title("Chord tones → musician layers (color = instrument)")
    ax.invert_yaxis()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chords", type=Path, default=CHORD_JSON)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "analysis_out")
    args = ap.parse_args()
    if not args.chords.is_file():
        raise SystemExit(f"missing chord JSON: {args.chords}")

    out = args.out_dir
    out_dir = out / "resynth_layers"
    out_mix = out / "resynth_from_chords_stems.wav"
    out_legacy = out / "resynth_from_chords.wav"
    out_preview = out / "resynth_from_chords_preview.wav"
    out_md = out / "resynth_from_chords.md"
    out_layers_md = out / "resynth_layers.md"
    out_fig = out / "resynth_layers_map.png"

    data = json.loads(args.chords.read_text())
    timeline = data["timeline"]
    duration = float(data.get("duration_sec") or (timeline[-1]["end"] if timeline else 60.0))
    if timeline:
        duration = max(duration, float(timeline[-1]["end"]) + 0.5)

    buffers = synthesize_layers(timeline, duration, SR)
    # per-layer peak normalize lightly so quiet layers remain audible when soloed,
    # but keep relative mix balance via a shared scale from the mono sum first.
    mono_raw = np.zeros_like(next(iter(buffers.values())))
    for L in LAYERS:
        mono_raw += buffers[L.key]
    shared_peak = float(np.max(np.abs(mono_raw))) or 1.0
    shared_scale = 0.85 / shared_peak
    for key in buffers:
        buffers[key] = buffers[key] * shared_scale

    out_dir.mkdir(parents=True, exist_ok=True)
    stem_paths: list[Path] = []
    for L in LAYERS:
        p = out_dir / L.filename
        write_wav_mono(p, buffers[L.key], SR)
        stem_paths.append(p)

    left, right = mix_stereo(buffers)
    write_wav_stereo(out_mix, left, right, SR)
    write_wav_mono(out_legacy, (left + right) * 0.5, SR)
    n_prev = int(PREVIEW_SEC * SR)
    write_wav_stereo(out_preview, left[:n_prev], right[:n_prev], SR)

    save_layer_figure(timeline, duration, out_fig)

    n_chords = len(timeline)
    example_rows = "\n".join(build_assignment_log(timeline, 10))
    layer_table_rows = "\n".join(
        f"| `{L.filename}` | {L.display} | {L.role} | "
        f"{L.freq_range_hz[0]:.0f}–{L.freq_range_hz[1]:.0f} Hz | "
        f"h={L.harmonics} attack={L.attack}s |"
        for L in LAYERS
    )
    stem_list = "\n".join(f"- `{display_path(p)}`" for p in stem_paths)

    layers_md = f"""# Layered chord resynthesis (Audacity-style stems)

Reconstruction from **chord / pitch-class analysis only** (`{args.chords.name}`).
No mic capture WAV was used as an audio source.

## Ensemble guess (wooden chords, outdoor park)

Wooden-chord layers only (**no clarinet**; Parc Roland Beaudin outdoor vibe):

| Stem file | Musician / instrument | Role | Freq range | Timbre notes |
|-----------|----------------------|------|------------|--------------|
{layer_table_rows}

## How notes are split

For each timed chord segment:

1. Infer root from chord label (fallback: most-salient PC).
2. Sort PCs low→high; put root at the bottom of the stack.
3. **Upright bass** → lowest / root-ish in ~55–130 Hz.
4. **Cello** → next tone in ~130–320 Hz.
5. Remaining mid tones **round-robin** across **guitar A**, **guitar B**, and **nylon** (never dump all mids on one guitar).
6. With 4–5 PCs, the **highest extension** also feeds **viola/violin sheen** (~392–880 Hz).

Example assignments (first segments):

{example_rows}

## Outputs

### Individual mono stems
{stem_list}

### Mixes
- `{display_path(out_mix)}` — **stereo stems mix** (panned layers summed; play this)
- `{display_path(out_legacy)}` — mono sum of the same layers (legacy path)
- `{display_path(out_preview)}` — first {PREVIEW_SEC:.0f}s stereo preview
- `{display_path(out_fig) if out_fig.exists() else "resynth_layers_map.png"}` — optional layer map figure

## Fidelity

Readable wooden-chord sketch of analyzed pitch stacks and timing — not the original performance.
Each layer has a distinct envelope/harmonic recipe so ears can separate musicians.
"""
    out_layers_md.write_text(layers_md)

    md = f"""# Resynthesis from chord analysis (layered)

This audio is a **reconstruction synthesized from chord / pitch-class / frequency analysis only**,
now as **separate musician/instrument layers** (not one flattened pad).

- Source data: `{display_path(args.chords)}`
- Ensemble: upright bass, cello, acoustic guitar ×2, nylon guitar, viola/violin sheen
- Constraints: wooden chords only; **no clarinet**; outdoor park guess
- **No original recording** used as an audio source

See **`{display_path(out_layers_md)}`** for the Audacity-style stem → role → freq table and split rules.

## Outputs

| File | Notes |
|------|--------|
| `{display_path(out_dir)}/*.wav` | One mono stem per musician ({len(LAYERS)} files) |
| `{display_path(out_mix)}` | Stereo mix of all layers (~{duration:.1f}s, {n_chords} segments) |
| `{display_path(out_legacy)}` | Mono sum (legacy) |
| `{display_path(out_preview)}` | First {PREVIEW_SEC:.0f}s stereo preview |
| `{display_path(out_fig)}` | Layer activity over time |

## Fidelity

Crude but separable: each stem carries only its register/role notes with a distinct timbre.
"""
    out_md.write_text(md)

    print(f"duration_sec={duration:.2f} segments={n_chords}")
    for p in stem_paths:
        print(f"stem {p}")
    print(f"mix {out_mix}")
    print(f"legacy_mono {out_legacy}")
    print(f"md {out_layers_md}")
    if out_fig.exists():
        print(f"fig {out_fig}")


if __name__ == "__main__":
    main()
