#!/usr/bin/env python3
"""Characterize instruments and note sequences in Hz; ignore voices/lyrics."""
from __future__ import annotations

import argparse
import collections
import json
import math
import wave
from pathlib import Path

import numpy as np

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


def analyze(x: np.ndarray, sr: int, ignore_vocals: bool = True) -> dict:
    dur = len(x) / sr
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))

    hop = int(0.25 * sr)
    env = np.array(
        [np.sqrt(np.mean(x[i : i + hop] ** 2)) for i in range(0, max(0, len(x) - hop), hop)]
    )
    thr = max(0.008, float(np.percentile(env, 55)) * 0.35) if env.size else 0.008
    active = np.where(env >= thr)[0]
    active_span = None
    if active.size:
        active_span = [float(active[0] * 0.25), float((active[-1] + 1) * 0.25)]

    N = 4096
    step = int(0.25 * sr)
    win = np.hanning(N)
    tracks: list[tuple[float, float, float, str, float]] = []
    band: dict[str, float] = collections.defaultdict(float)

    for start in range(0, max(0, len(x) - N), step):
        seg = x[start : start + N]
        e = float(np.sqrt(np.mean(seg * seg)))
        if e < thr * 0.75:
            continue
        mag = np.abs(np.fft.rfft(seg * win))
        freqs = np.fft.rfftfreq(N, 1 / sr)
        peaks: list[tuple[float, float, float]] = []
        for i in range(3, len(mag) - 3):
            if mag[i] > mag[i - 1] and mag[i] > mag[i + 1] and mag[i] >= mag[i - 2] and mag[i] >= mag[i + 2]:
                f = float(freqs[i])
                if 40 <= f <= 5000:
                    w = 1.0
                    if ignore_vocals and 250 <= f <= 3200:
                        w = 0.22  # de-emphasize speech/lyric band
                    if f < 200:
                        w *= 1.35
                    if f > 3500:
                        w *= 1.2
                    peaks.append((mag[i] * w, f, float(mag[i])))
        peaks.sort(reverse=True)
        chosen: list[float] = []
        for score, f, m in peaks:
            if any(abs(math.log2(f / cf)) < 1 / 12 for cf in chosen):
                continue
            chosen.append(f)
            name = hz_to_note(f)
            tracks.append((start / sr, f, m, name, score))
            if f < 80:
                band["sub_bass"] += score
            elif f < 250:
                band["bass"] += score
            elif f < 500:
                band["low_mid"] += score
            elif f < 2000:
                band["mid"] += score
            elif f < 4000:
                band["high_mid"] += score
            else:
                band["presence"] += score
            if len(chosen) >= 6:
                break

    tot = sum(band.values()) or 1.0
    band_pct = {k: 100.0 * band.get(k, 0.0) / tot for k in ["sub_bass", "bass", "low_mid", "mid", "high_mid", "presence"]}

    instruments = []
    sb = band_pct["sub_bass"] + band_pct["bass"]
    lm = band_pct["low_mid"]
    md = band_pct["mid"]
    hi = band_pct["high_mid"] + band_pct["presence"]
    if sb > 15:
        instruments.append(
            {
                "family": "Bass foundation",
                "examples": "double bass / cello / low brass / bass",
                "hz_range": "40–250",
                "salience": round(sb, 1),
            }
        )
    if lm > 10:
        instruments.append(
            {
                "family": "Low-mid body",
                "examples": "viola / trombone / piano left hand / low winds",
                "hz_range": "250–500",
                "salience": round(lm, 1),
            }
        )
    if md > 15:
        instruments.append(
            {
                "family": "Mid melody/harmony",
                "examples": "violins / woodwinds / brass / piano",
                "hz_range": "500–2000",
                "salience": round(md, 1),
            }
        )
    if hi > 10:
        instruments.append(
            {
                "family": "High color",
                "examples": "flute / high violin / cymbals / harmonics",
                "hz_range": "2000–5000",
                "salience": round(hi, 1),
            }
        )
    onset = np.diff(env) if env.size else np.array([])
    perc = float(np.mean(onset[onset > 0])) if onset.size and np.any(onset > 0) else 0.0
    if perc > thr * 0.12:
        instruments.append(
            {
                "family": "Percussion / rhythmic attacks",
                "examples": "drums / timpani / plucked attacks",
                "hz_range": "broadband",
                "salience": round(perc, 4),
            }
        )

    bins: dict[int, list[tuple[float, float, str]]] = collections.defaultdict(list)
    for t, f, m, name, score in tracks:
        bins[int(t / 0.5)].append((score, f, name))

    sequence = []
    for b in sorted(bins):
        items = sorted(bins[b], reverse=True)
        kept: list[tuple[float, float, str]] = []
        for score, f, name in items:
            if any(abs(math.log2(f / kf)) < 0.5 / 12 for _, kf, _ in kept):
                continue
            if ignore_vocals and 250 <= f <= 3200 and score < items[0][0] * 0.5:
                continue
            kept.append((score, f, name))
            if len(kept) >= 4:
                break
        if not kept:
            continue
        sequence.append(
            {
                "t_sec": round(b * 0.5, 2),
                "pitches": [{"note": name, "hz": round(f, 2)} for _, f, name in kept],
            }
        )

    pitch_salience = collections.Counter()
    pitch_class = collections.Counter()
    for t, f, m, name, score in tracks:
        pitch_salience[name] += score
        pitch_class["".join(c for c in name if not c.isdigit())] += score

    top_pitches = []
    for name, sc in pitch_salience.most_common(15):
        fs = [f for t, f, m, n, s in tracks if n == name]
        top_pitches.append({"note": name, "hz_median": round(float(np.median(fs)), 2), "weight": round(sc, 3)})

    pc_total = sum(pitch_class.values()) or 1.0
    top_pc = [
        {"pitch_class": n, "pct": round(100 * sc / pc_total, 1)} for n, sc in pitch_class.most_common(12)
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
        f"- Vocals/lyrics: {'ignored (speech band de-emphasized)' if report['ignore_vocals'] else 'included'}",
        "",
        "## Likely instrument families",
        "",
    ]
    if not report["instruments"]:
        lines.append("_No clear instrumental energy detected (silent or too quiet)._")
    else:
        for inst in report["instruments"]:
            lines.append(
                f"- **{inst['family']}** ({inst['hz_range']} Hz) — {inst['examples']} "
                f"(salience {inst['salience']})"
            )
    lines += ["", "## Band energy", ""]
    for k, v in report["band_energy_pct"].items():
        lines.append(f"- {k}: {v}%")
    lines += ["", "## Note sequence (0.5 s steps, Hz)", ""]
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
    ap.add_argument("--include-vocals", action="store_true")
    args = ap.parse_args()

    x, sr = load_wav(args.wav)
    report = analyze(x, sr, ignore_vocals=not args.include_vocals)
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
