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
    SENS_DEFAULT,
    PeakPicker,
    TrackSet,
    extract_cluster_peaks,
    rfft_db,
)
from density_cluster import cluster_peaks, heuristic_label  # noqa: E402

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


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


def hz_to_note(f: float) -> str:
    midi = int(round(69 + 12 * math.log2(f / 440.0)))
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def _band_name(f: float) -> str:
    if f < 80:
        return "sub_bass"
    if f < 250:
        return "bass"
    if f < 500:
        return "low_mid"
    if f < 2000:
        return "mid"
    if f < 4000:
        return "high_mid"
    return "presence"


def analyze(x: np.ndarray, sr: int, ignore_vocals: bool = False) -> dict:
    dur = len(x) / sr
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))

    hop = max(1, int(0.08 * sr))
    env = np.array(
        [np.sqrt(np.mean(x[i : i + hop] ** 2)) for i in range(0, max(0, len(x) - hop), hop)]
    )
    thr = max(0.008, float(np.percentile(env, 55)) * 0.35) if env.size else 0.008
    active = np.where(env >= thr)[0]
    hop_sec = hop / sr
    active_span = None
    if active.size:
        active_span = [float(active[0] * hop_sec), float((active[-1] + 1) * hop_sec)]

    picker = PeakPicker()
    tracks_set = TrackSet()
    band: dict[str, float] = collections.defaultdict(float)
    pitch_salience: collections.Counter[str] = collections.Counter()
    pitch_class: collections.Counter[str] = collections.Counter()
    pitch_hz: dict[str, list[float]] = collections.defaultdict(list)
    source_acc: dict[int, dict] = {}
    sequence: list[dict] = []
    now = 0.0

    for start in range(0, max(0, len(x) - FFT_SIZE), hop):
        seg = x[start : start + FFT_SIZE]
        e = float(np.sqrt(np.mean(seg * seg)))
        if e < thr * 0.5:
            picker.smooth *= 0.85
            now += hop_sec
            continue
        spec, bin_hz = rfft_db(seg, sr, FFT_SIZE)
        frame = picker.process(
            spec,
            bin_hz,
            tracks_set,
            chords=True,
            sensitivity=SENS_DEFAULT,
            autotune=False,
            now=now,
        )
        mix = frame.mix_peaks or extract_cluster_peaks(spec, bin_hz)
        clusters = cluster_peaks(mix)
        t_sec = start / sr
        pitches = []
        for note in frame.lit:
            name = hz_to_note(note.freq)
            w = max(0.0, note.score + 80.0)
            pitch_salience[name] += w
            pitch_class["".join(c for c in name if not c.isdigit())] += w
            pitch_hz[name].append(note.freq)
            band[_band_name(note.freq)] += w
            pitches.append({"note": name, "hz": round(note.freq, 2)})
        if pitches:
            sequence.append({"t_sec": round(t_sec, 2), "pitches": pitches})
        for c in clusters:
            midi = int(round(69 + 12 * math.log2(c["f0"] / 440.0))) if c["f0"] > 0 else 0
            bucket = source_acc.setdefault(
                midi,
                {"f0s": [], "dbs": [], "harms": [], "n": 0},
            )
            bucket["f0s"].append(c["f0"])
            bucket["dbs"].append(c["db"])
            bucket["harms"].append(c["harm"])
            bucket["n"] += 1
        now += hop_sec

    tot = sum(band.values()) or 1.0
    band_pct = {
        k: 100.0 * band.get(k, 0.0) / tot
        for k in ["sub_bass", "bass", "low_mid", "mid", "high_mid", "presence"]
    }

    sources = []
    for _midi, acc in source_acc.items():
        f0 = float(np.median(acc["f0s"]))
        harm = float(np.mean(acc["harms"]))
        db = float(np.max(acc["dbs"]))
        label = heuristic_label(f0, harm)
        if ignore_vocals and label == "voix":
            continue
        note = hz_to_note(f0)
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
        f"- Vocals: {'ignored after labeling' if report['ignore_vocals'] else 'included (crayon-piano peak-picker)'}",
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
    ap.add_argument("--include-vocals", action="store_true", help="default; vocals are first-class")
    ap.add_argument("--ignore-vocals", action="store_true", help="drop sources labeled voix")
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
