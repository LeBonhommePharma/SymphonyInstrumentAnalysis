#!/usr/bin/env python3
"""Characterize sources and notes with the crayon-piano peak-picker + clusterer."""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from crayon_piano_lib import (  # noqa: E402
    FFT_SIZE,
    MIXED_LO_HZ,
    band_energy_db,
    extract_cluster_peaks,
    rfft_db,
)
from density_cluster import cluster_peaks, heuristic_label  # noqa: E402

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# 8192 @ 48 kHz is ~5.9 Hz/bin — too coarse for A0–C3. A longer bass FFT
# (~1.5 Hz/bin) is merged in below BASS_SPLIT_HZ.
BASS_FFT_SIZE = 32768
BASS_SPLIT_HZ = 150.0


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


def hz_to_note(f: float) -> str | None:
    if not math.isfinite(f) or f <= 0:
        return None
    midi = int(round(69 + 12 * math.log2(f / 440.0)))
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def frame_starts(n: int, hop: int, fft_size: int = FFT_SIZE) -> list[int]:
    """Inclusive last full window; one padded start if the clip is shorter."""
    if n <= 0 or hop <= 0:
        return []
    last = n - fft_size
    if last >= 0:
        return list(range(0, last + 1, hop))
    return [0] if n > 16 else []


def mixed_resolution_peaks(
    x: np.ndarray, start: int, sr: int
) -> tuple[list[dict], np.ndarray, float]:
    """8192 mid/high peaks + 32768 bass peaks, same hop."""
    seg = x[start : start + FFT_SIZE]
    spec, bin_hz = rfft_db(seg, sr, FFT_SIZE)
    mid = [p for p in extract_cluster_peaks(spec, bin_hz) if p["f"] >= BASS_SPLIT_HZ]
    bass_end = min(int(x.size), start + FFT_SIZE)
    bass_start = max(0, bass_end - BASS_FFT_SIZE)
    spec_b, bin_b = rfft_db(x[bass_start:bass_end], sr, BASS_FFT_SIZE)
    bass = [
        p
        for p in extract_cluster_peaks(spec_b, bin_b)
        if MIXED_LO_HZ <= p["f"] < BASS_SPLIT_HZ
    ]
    return bass + mid, spec, bin_hz


def analyze(x: np.ndarray, sr: int, ignore_vocals: bool = False) -> dict:
    if sr <= 0:
        raise SystemExit("sample rate must be positive")
    n = int(x.size)
    dur = n / sr
    if n == 0:
        rms = 0.0
        peak = 0.0
    else:
        rms = float(np.sqrt(np.mean(x * x)))
        peak = float(np.max(np.abs(x)))

    hop = max(1, int(0.08 * sr))
    env_starts = list(range(0, max(0, n - hop + 1), hop)) if n else []
    env = np.array(
        [np.sqrt(np.mean(x[i : i + hop] ** 2)) for i in env_starts]
    )
    thr = max(0.008, float(np.percentile(env, 55)) * 0.35) if env.size else 0.008
    active = np.where(env >= thr)[0]
    hop_sec = hop / sr
    active_span = None
    if active.size:
        active_span = [float(active[0] * hop_sec), float((active[-1] + 1) * hop_sec)]

    pitch_salience: collections.Counter[str] = collections.Counter()
    pitch_class: collections.Counter[str] = collections.Counter()
    pitch_hz: dict[str, list[float]] = collections.defaultdict(list)
    source_acc: dict[int, dict] = {}
    sequence: list[dict] = []
    band_lin: dict[str, float] = collections.defaultdict(float)
    band_hz = {
        "sub_bass": (27.5, 80.0),
        "bass": (80.0, 250.0),
        "low_mid": (250.0, 500.0),
        "mid": (500.0, 2000.0),
        "high_mid": (2000.0, 4000.0),
        "presence": (4000.0, 5000.0),
    }

    for start in frame_starts(n, hop, FFT_SIZE):
        seg = x[start : start + FFT_SIZE]
        if seg.size == 0:
            continue
        e = float(np.sqrt(np.mean(seg * seg)))
        if e < thr * 0.5:
            continue
        mix, spec, bin_hz = mixed_resolution_peaks(x, start, sr)
        for name, (lo, hi) in band_hz.items():
            band_lin[name] += band_energy_db(spec, bin_hz, lo, hi)
        clusters = cluster_peaks(mix, merge_nearby=False)
        t_sec = start / sr
        pitches = []
        for c in clusters:
            f0 = float(c["f0"])
            if f0 <= 0 or not math.isfinite(f0):
                continue
            name = hz_to_note(f0)
            if not name:
                continue
            w = max(0.0, float(c["db"]) + 80.0)
            pitch_salience[name] += w
            pitch_class["".join(ch for ch in name if not ch.isdigit())] += w
            pitch_hz[name].append(f0)
            pitches.append({"note": name, "hz": round(f0, 2)})
            midi = int(round(69 + 12 * math.log2(f0 / 440.0)))
            bucket = source_acc.setdefault(
                midi,
                {"f0s": [], "dbs": [], "harms": [], "centroids": [], "n": 0},
            )
            bucket["f0s"].append(f0)
            bucket["dbs"].append(c["db"])
            bucket["harms"].append(c["harm"])
            bucket["centroids"].append(float(c.get("centroid") or f0))
            bucket["n"] += 1
        if pitches:
            sequence.append({"t_sec": round(t_sec, 2), "pitches": pitches})

    tot = sum(band_lin.values()) or 1.0
    band_pct = {
        k: 100.0 * band_lin.get(k, 0.0) / tot
        for k in ["sub_bass", "bass", "low_mid", "mid", "high_mid", "presence"]
    }

    sources = []
    for _midi, acc in source_acc.items():
        f0 = float(np.median(acc["f0s"]))
        harm = float(np.mean(acc["harms"]))
        db = float(np.max(acc["dbs"]))
        centroid = float(np.median(acc["centroids"])) if acc["centroids"] else None
        label = heuristic_label(f0, harm, centroid)
        if ignore_vocals and label == "voix":
            continue
        note = hz_to_note(f0)
        if not note:
            continue
        sources.append(
            {
                "note": note,
                "hz": round(f0, 2),
                "db": round(db, 1),
                "harm": round(harm, 3),
                "label": label or note,
                "frames": acc["n"],
            }
        )
    sources.sort(key=lambda s: s["db"], reverse=True)

    instruments = []
    for src in sources:
        instruments.append(
            {
                "family": src["label"],
                "examples": src["note"],
                "hz_range": str(int(round(src["hz"]))),
                "salience": src["db"],
            }
        )

    top_pitches = []
    for name, sc in pitch_salience.most_common(15):
        fs = pitch_hz.get(name) or []
        top_pitches.append(
            {
                "note": name,
                "hz_median": round(float(np.median(fs)) if fs else 0.0, 2),
                "weight": round(sc, 3),
            }
        )

    pc_total = sum(pitch_class.values()) or 1.0
    top_pc = [
        {"pitch_class": n, "pct": round(100 * sc / pc_total, 1)}
        for n, sc in pitch_class.most_common(12)
    ]

    return {
        "duration_sec": round(dur, 3),
        "sample_rate": sr,
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "active_span_sec": active_span,
        "ignore_vocals": ignore_vocals,
        "band_energy_pct": {k: round(v, 1) for k, v in band_pct.items()},
        "instruments": instruments,
        "sources": sources,
        "note_sequence": sequence,
        "top_pitches": top_pitches,
        "pitch_classes": top_pc,
        "note_sequence_bins": len(sequence),
    }


def render_markdown(report: dict, source: str) -> str:
    lines = [
        "# Instrument / Frequency Analysis",
        "",
        f"- Source: `{source}`",
        f"- Duration: {report['duration_sec']}s @ {report['sample_rate']} Hz",
        f"- Level: rms={report['rms']}, peak={report['peak']}",
        f"- Vocals: {'ignored after labeling' if report['ignore_vocals'] else 'included (harmonic-folded fundamentals)'}",
        "",
        "## Clustered sources (same logic as the piano)",
        "",
    ]
    if not report.get("sources") and not report["instruments"]:
        lines.append("_No clear pitched sources (silent or too quiet)._")
    else:
        for src in report.get("sources") or []:
            lines.append(
                f"- **{src['label']}** {src['note']} {src['hz']} Hz "
                f"(harm {src['harm']}, {src['db']} dB, {src['frames']} frames)"
            )
    lines += ["", "## Band energy", ""]
    for k, v in report["band_energy_pct"].items():
        lines.append(f"- {k}: {v}%")
    lines += ["", "## Note sequence (peak-picker, Hz)", ""]
    for row in report["note_sequence"][:60]:
        parts = [f"{p['note']} {p['hz']} Hz" for p in row["pitches"]]
        lines.append(f"- **{row['t_sec']:.1f}s** — " + " | ".join(parts))
    if report["note_sequence_bins"] > 60:
        lines.append(f"- … +{report['note_sequence_bins'] - 60} more bins in JSON")
    lines += ["", "## Top pitches", ""]
    for p in report["top_pitches"]:
        lines.append(f"- {p['note']}: ~{p['hz_median']} Hz")
    lines += ["", "## Pitch-class weights", ""]
    for p in report["pitch_classes"]:
        lines.append(f"- {p['pitch_class']}: {p['pct']}%")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("wav", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    vocals = ap.add_mutually_exclusive_group()
    vocals.add_argument("--include-vocals", action="store_true", help="default; vocals are first-class")
    vocals.add_argument("--ignore-vocals", action="store_true", help="drop sources labeled voix")
    args = ap.parse_args()

    x, sr = load_wav(args.wav)
    report = analyze(x, sr, ignore_vocals=args.ignore_vocals)
    out_dir = args.out_dir or (Path(__file__).resolve().parents[1] / "analysis_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.wav.stem
    json_path = out_dir / f"{stem}_report.json"
    md_path = out_dir / f"{stem}_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report, str(args.wav)), encoding="utf-8")
    print(md_path.read_text(encoding="utf-8"))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    if report["peak"] <= 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
