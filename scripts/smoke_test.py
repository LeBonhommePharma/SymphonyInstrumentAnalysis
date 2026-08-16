#!/usr/bin/env python3
"""Generate a known-pitch WAV and verify the analyzer recovers those notes.

Mic capture (list/probe/record) needs macOS AVFoundation. This smoke test
exercises the analysis path on any machine with numpy + ffmpeg-style 16-bit WAV,
and checks that the capture scripts exit cleanly when no devices exist.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from analyze_instruments import analyze, load_wav  # noqa: E402
from list_mics import NO_DEVICES_MESSAGE  # noqa: E402
from crayon_piano_lib import (  # noqa: E402
    MIXED_HI_HZ,
    extract_cluster_peaks,
    peak_hz_of_db,
    rfft_db,
    spec_x_of,
)
from density_cluster import cluster_peaks  # noqa: E402

SR = 48000
# Analyzer FFT size is 4096, so pick bin-centered tones (bin * sr / 4096).
TONES = [
    ("E2", 7 * SR / 4096),    # 82.03 Hz
    ("A4", 38 * SR / 4096),   # 445.31 Hz
    ("C5", 45 * SR / 4096),   # 527.34 Hz
]


def write_tone_wav(path: Path, duration_sec: float = 3.0) -> None:
    t = np.arange(int(SR * duration_sec), dtype=np.float64) / SR
    x = np.zeros_like(t)
    for _, hz in TONES:
        x += 0.22 * np.sin(2 * math.pi * hz * t)
        x += 0.04 * np.sin(2 * math.pi * hz * t) * np.sin(math.pi * t / duration_sec)
    peak = np.max(np.abs(x)) or 1.0
    pcm = np.clip(x / peak * 0.8, -1.0, 1.0)
    samples = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.tobytes())


def check_ffmpeg() -> None:
    proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("ffmpeg is required on PATH")
    first = (proc.stdout or proc.stderr).splitlines()[0] if (proc.stdout or proc.stderr) else "ffmpeg"
    print(f"ffmpeg: {first}")


def check_capture_scripts() -> None:
    py = sys.executable
    for name, extra in (
        ("list_mics.py", []),
        ("probe_mics.py", ["--seconds", "0.2"]),
        ("record_mic.py", ["--seconds", "0.2", "--probe-seconds", "0.2"]),
    ):
        proc = subprocess.run(
            [py, str(SCRIPTS / name), *extra],
            capture_output=True,
            text=True,
        )
        combined = proc.stdout + proc.stderr
        if proc.returncode == 0:
            print(f"{name}: devices present; skipped no-device check")
            continue
        if "Traceback" in combined:
            raise SystemExit(f"{name} raised a traceback:\n{combined}")
        if NO_DEVICES_MESSAGE not in combined:
            raise SystemExit(
                f"{name} exit {proc.returncode} without {NO_DEVICES_MESSAGE!r}:\n{combined}"
            )
        print(f"{name}: exit {proc.returncode} ({NO_DEVICES_MESSAGE})")


def _i18n_keys(pack_src: str) -> set[str]:
    return set(re.findall(r"^\s{6}(\w+):", pack_src, flags=re.M))


def check_i18n(docs: Path) -> None:
    i18n = (docs / "i18n.js").read_text(encoding="utf-8")
    if "en:" not in i18n or "fr:" not in i18n:
        raise SystemExit("i18n.js must define English and French packs")
    en_start = i18n.find("en: {")
    fr_start = i18n.find("fr: {")
    if en_start < 0 or fr_start < 0 or fr_start < en_start:
        raise SystemExit("i18n.js English/French packs are not in the expected order")
    en_keys = _i18n_keys(i18n[en_start:fr_start])
    strings_end = i18n.find("\n  };", fr_start)
    fr_keys = _i18n_keys(i18n[fr_start: strings_end if strings_end > 0 else None])
    missing_fr = sorted(en_keys - fr_keys)
    missing_en = sorted(fr_keys - en_keys)
    if missing_fr or missing_en:
        raise SystemExit(f"i18n key mismatch en vs fr: missing_fr={missing_fr} missing_en={missing_en}")
    for key in ("btnMic", "tutH1", "hubH1", "howH1", "familyBass", "nInstrument0", "nInstruments"):
        if key not in en_keys:
            raise SystemExit(f"i18n.js missing required key {key}")
    used: set[str] = set()
    for html_path in (docs / "index.html", docs / "how-to.html", docs / "tutorial" / "index.html"):
        html = html_path.read_text(encoding="utf-8")
        if 'data-lang-switch="en"' not in html or 'data-lang-switch="fr"' not in html:
            raise SystemExit(f"{html_path.name} is missing EN/FR language switch")
        if "i18n.js" not in html:
            raise SystemExit(f"{html_path.name} does not load i18n.js")
        used.update(re.findall(r'data-i18n(?:-title|-alt|-html)?="(\w+)"', html))
    missing_used = sorted(used - en_keys)
    if missing_used:
        raise SystemExit(f"HTML i18n keys missing from i18n.js: {missing_used}")
    print(f"i18n: OK ({len(en_keys)} en/fr keys)")


def check_public_site() -> None:
    docs = SCRIPTS.parent / "docs"
    required = [
        docs / "index.html",
        docs / "how-to.html",
        docs / "howto-eli5.png",
        docs / "i18n.js",
        docs / "theme.js",
        docs / "tutorial" / "index.html",
        docs / "tutorial" / "app.js",
        docs / "tutorial" / "styles.css",
        docs / "piano" / "index.html",
        docs / "piano" / "dual_keyboard.js",
        docs / ".nojekyll",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"public site files missing: {missing}")
    tutorial = (docs / "tutorial" / "index.html").read_text(encoding="utf-8")
    app_js = (docs / "tutorial" / "app.js").read_text(encoding="utf-8")
    if "data-action=\"mic\"" not in tutorial and "Listen" not in tutorial:
        raise SystemExit("tutorial is missing the mic listen control")
    if 'id="tracks"' not in tutorial:
        raise SystemExit("tutorial is missing Logic-style waveform tracks")
    if "tourFill" in tutorial or 'class="progress"' in tutorial:
        raise SystemExit("tutorial must not use a time slider")
    silent = tutorial.lower()
    if "does not play music" not in silent and "never plays a song" not in silent:
        raise SystemExit("tutorial must stay silent")
    if "densityCluster" not in app_js:
        raise SystemExit("tutorial must density-cluster live sources (no fixed instrument count)")
    if "groupHarmonicFunds" not in app_js:
        raise SystemExit("tutorial must fold harmonics before counting tracks")
    if "extractClusterPeaks" not in app_js or "pickLitMidis" not in app_js:
        raise SystemExit("tutorial hub must use the piano float-dB peak-picker")
    if "fftSize = 16384" not in app_js:
        raise SystemExit("tutorial hub FFT size must match the web piano")
    if "CODE_TO_MIDI" not in app_js:
        raise SystemExit("tutorial hub must map computer keys to piano midis")
    if "theme.js" not in tutorial:
        raise SystemExit("tutorial must load the shared theme switch")
    if "data-theme-auto" not in tutorial:
        raise SystemExit("tutorial must include Auto lighting")
    if "specYOfDb" not in app_js and "yOfDb" not in app_js:
        raise SystemExit("tutorial spectrum must plot dBFS, not byte-log")
    if "requestAnimationFrame(tick)" not in app_js:
        raise SystemExit("tutorial must redraw on animation frames")
    if '["440", 440]' not in app_js:
        raise SystemExit("tutorial spectrum must label the 440 Hz tick")
    if "softGain" not in app_js and "updateAutoGain" not in app_js:
        raise SystemExit("tutorial must soft-auto-gain quiet / headphone bleed")
    if "video: false" not in app_js and "audioOnlyStream" not in app_js:
        raise SystemExit("tutorial must prefer audio-only capture")
    if "density" not in tutorial.lower() and "audio only" not in tutorial.lower():
        raise SystemExit("tutorial copy must describe audio-only density clustering")
    if "listenSmart" not in app_js or "sniffHeard" not in app_js:
        raise SystemExit("tutorial must sniff the mic then fall through to live listen")
    piano = (docs / "piano" / "index.html").read_text(encoding="utf-8")
    piano_js = (docs / "piano" / "dual_keyboard.js").read_text(encoding="utf-8")
    if 'id="dualBoards"' not in piano or "Canadien français" not in piano:
        raise SystemExit("public piano must ship US and Canadian French layouts")
    if 'id="kbLayout"' not in piano or 'data-layout="csa"' not in piano:
        raise SystemExit("public piano must ship a US / Canadian French layout picker")
    if ">Rejouer<" not in piano or ">Accords<" not in piano or ">La auto<" not in piano:
        raise SystemExit("public piano must label transport and option chips")
    if "live-ring" in piano:
        raise SystemExit("public piano must not pulse candy-circle listen/replay buttons")
    if "function setLayout" not in piano or "crayon-kb-layout" not in piano:
        raise SystemExit("public piano must remap the whole board when the layout picker changes")
    if "grid-template-columns: 1fr 1fr" in piano:
        raise SystemExit("public piano must show one layout at a time, not two side-by-side boards")
    if "MAX_FINGERS" not in piano_js or "CLUSTER_EPS" not in piano_js:
        raise SystemExit("public piano must include the clustered 10-finger gate")
    if "midiForKid" not in piano_js or "noteLabelFr" not in piano_js:
        raise SystemExit("public piano must bind typing keys to crayon notes")
    if "function holdMidi" not in piano or "syncPianoBinds" not in piano:
        raise SystemExit("public piano must light the 88-key from the computer keyboard")
    if "pages-crumb" not in piano:
        raise SystemExit("public piano must link back to the Pages hub")
    if "loopWantsFrames" not in piano or "FFT_SIZE = 8192" not in piano:
        raise SystemExit("public piano must draw on vsync (loopWantsFrames, 8192 FFT)")
    bootstrap = tutorial.split('id="bootstrap"', 1)[-1]
    if 'data-action="system"' in bootstrap:
        raise SystemExit("bootstrap must not offer a mic vs tab choice")
    check_i18n(docs)
    print("public site files: OK")


def check_crayon_piano() -> None:
    html = (SCRIPTS.parent / "web" / "keyboard.html").read_text(encoding="utf-8")
    if 'id="scrub"' in html:
        raise SystemExit("HTML piano must not use a playback time slider")
    if 'id="sens"' in html:
        raise SystemExit("HTML piano must not use a sensitivity slider")
    if 'id="arrange"' not in html or 'id="playhead"' not in html:
        raise SystemExit("HTML piano must use a Logic-style arrange playhead")
    if "Contrebasse" in html or "Violoncelle" in html or "Guitare A" in html:
        raise SystemExit("HTML piano must not idle five hardcoded musician chips")
    if "groupHarmonicFunds" not in html or "densityClusterFunds" not in html:
        raise SystemExit("HTML piano must density-cluster independent tracks")
    if "selectedTrackIds" not in html:
        raise SystemExit("HTML piano must multi-select density-clustered tracks")
    if 'id="arrangeHeads"' not in html or "pushTrackHist" not in html:
        raise SystemExit("HTML piano must stack one waveform lane per density cluster")
    if 'id="dualBoards"' not in html or "dual_keyboard.js" not in html:
        raise SystemExit("HTML piano must ship the typing board and dual_keyboard.js")
    if 'id="kbLayout"' not in html or 'data-layout="us"' not in html or 'data-layout="csa"' not in html:
        raise SystemExit("HTML piano must expose a US / Canadian French layout picker")
    if "function setLayout" not in html or "crayon-kb-layout" not in html:
        raise SystemExit("HTML piano must remap glyphs and hardware together when the layout changes")
    if "grid-template-columns: 1fr 1fr" in html:
        raise SystemExit("HTML piano must show one typing layout at a time, not two side-by-side boards")
    if 'id="kbMeta"' not in html:
        raise SystemExit("HTML piano must show live finger / cluster counts")
    if "onKbPointerEnter" in html:
        raise SystemExit("HTML typing must not slide-type neighboring keys")
    if "fingerGate" not in html or "MAX_FINGERS" not in (SCRIPTS.parent / "web" / "dual_keyboard.js").read_text(encoding="utf-8"):
        raise SystemExit("HTML piano must gate 10 fingers unless keys are well clustered")
    gate_js = (SCRIPTS.parent / "web" / "dual_keyboard.js").read_text(encoding="utf-8")
    if "if (after <= MAX_FINGERS) return true" in gate_js:
        raise SystemExit("10-finger gate must count touches, not clusters")
    if "if (held.length < MAX_FINGERS) return true" not in gate_js:
        raise SystemExit("10-finger gate must allow keys until ten fingers are down")
    if "midiForKid" not in gate_js or "noteLabelFr" not in gate_js:
        raise SystemExit("typing keys must map to crayon notes")
    if "function holdMidi" not in html or "syncPianoBinds" not in html:
        raise SystemExit("HTML piano must play and label the computer-key note map")
    if 'note.className = "note"' not in html or 'bind.className = "bind"' not in html:
        raise SystemExit("HTML piano must show the note on the typing key and the glyph on the 88-key")
    if "class=\"act\"" not in html or ">Rejouer<" not in html or ">Écouter<" not in html:
        raise SystemExit("HTML piano must label Rejouer and Écouter")
    if ">Accords<" not in html or ">La auto<" not in html:
        raise SystemExit("HTML piano must label Accords / Son / La auto instead of mystery glyphs")
    if "live-ring" in html or "width: 56px" in html:
        raise SystemExit("HTML piano must not use pulsing candy-circle transport buttons")
    if "getDisplayMedia" not in html:
        raise SystemExit("HTML piano must capture tab/system audio for listen")
    if "loopWantsFrames" not in html or "requestAnimationFrame(loop)" not in html:
        raise SystemExit("HTML piano must keep a vsync rAF loop while keys, listen, or replay are active")
    if "FFT_SIZE = 8192" not in html:
        raise SystemExit("HTML piano FFT must stay light enough for display-rate drawing")
    if "WAVE_WINDOW_SEC" not in html:
        raise SystemExit("HTML piano waveform must scroll in seconds, not frames")
    if "makeDemoBuffer" not in html:
        raise SystemExit("HTML Rejouer must fall back to a built-in synth demo when the WAV is missing")
    if re.search(r'if\s*\(\s*mode\s*===\s*"idle"\s*\)\s*\{\s*loopOn\s*=\s*false', html):
        raise SystemExit("HTML piano must not freeze the draw loop when idle keys are held")
    if "16384" in html:
        raise SystemExit("HTML piano must not use a 16384 FFT that cannot keep up with vsync")
    wave_swift = (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "WaveformTrackView.swift").read_text(
        encoding="utf-8"
    )
    spec_swift = (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "SpectrumPlotView.swift").read_text(
        encoding="utf-8"
    )
    session_swift = (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "PianoSession.swift").read_text(
        encoding="utf-8"
    )
    pulse_swift = (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "DisplayPulse.swift").read_text(
        encoding="utf-8"
    )
    if "minimumInterval" in wave_swift:
        raise SystemExit("iOS waveform must follow the display refresh, not a 30 Hz cap")
    if ".periodic" in spec_swift or "1.0 / 24.0" in spec_swift:
        raise SystemExit("iOS spectrum must follow the display refresh, not a 24 Hz timer")
    if "Timer.scheduledTimer" in session_swift:
        raise SystemExit("iOS clock must not tick at 20 Hz; use the display pulse")
    if "waveWindowSec" not in session_swift or "tickDisplay" not in session_swift:
        raise SystemExit("iOS waveform history must advance in seconds, not per audio buffer")
    if "CADisplayLink" not in pulse_swift:
        raise SystemExit("iOS must drive the waveform from CADisplayLink")
    dual_view = (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "DualKeyboardView.swift").read_text(
        encoding="utf-8"
    )
    if 'board("us")' in dual_view and 'board("csa")' in dual_view:
        raise SystemExit("iOS piano must show one typing layout at a time, not two boards")
    if 'accessibilityIdentifier("kbLayout")' not in dual_view or "Picker" not in dual_view:
        raise SystemExit("iOS piano must expose a US / Canadian French layout picker")
    if "kbLayout" not in session_swift or "crayon-kb-layout" not in session_swift:
        raise SystemExit("iOS piano must persist the chosen typing layout")
    if "hardwareDown" not in session_swift:
        raise SystemExit("iOS piano must remap hardware keys to the chosen layout")
    if "DualNoteMap" not in (SCRIPTS.parent / "ios" / "CrayonPiano.swiftpm" / "DualKeyboard.swift").read_text(
        encoding="utf-8"
    ):
        raise SystemExit("iOS piano must bind typing keys to crayon notes")
    if "boundPressed" not in session_swift or "syncBoundNotes" not in session_swift:
        raise SystemExit("iOS piano must sound and light notes from the computer keyboard")
    if 'id="stealth"' in html:
        raise SystemExit("HTML piano must use the 5-scene picker, not a stealth checkbox")
    if 'data-theme-set="stealth"' not in html or 'data-theme-set="day"' not in html:
        raise SystemExit("HTML piano must include day/light/dark/night/stealth scenes")
    if "MIDI_LO = 21" not in html or "MIDI_HI = 108" not in html:
        raise SystemExit("HTML piano must be the full 88-key range (A0 to C8)")
    if 'id="spec"' not in html or "drawSpecPlot" not in html:
        raise SystemExit("HTML piano must draw the regrouped log-Hz spectrum")
    if '["440", 440]' not in html and "[440, \"440\"]" not in html:
        raise SystemExit("HTML spectrum must label the 440 Hz tick")
    if "data-theme-auto" not in html:
        raise SystemExit("HTML piano must include an Auto lighting control")
    if "calc(52 * 28px)" not in html:
        raise SystemExit("HTML piano must be full-size 88-key (52 white keys × 28px min)")
    if ">Nuit<" in html:
        raise SystemExit("HTML piano must not use the Nuit checkbox label")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "crayon_piano.py"), "--self-test"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"crayon_piano.py --self-test failed:\n{proc.stdout}\n{proc.stderr}"
        )
    print("crayon_piano.py --self-test: OK")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "density_cluster.py")],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"density_cluster.py failed:\n{proc.stdout}\n{proc.stderr}")
    print((proc.stdout or "").strip() or "density_cluster.py: OK")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "dual_keyboard.py")],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"dual_keyboard.py failed:\n{proc.stdout}\n{proc.stderr}")
    print((proc.stdout or "").strip() or "dual_keyboard.py: OK")
    try:
        node = subprocess.run(
            ["node", str(SCRIPTS.parent / "web" / "dual_keyboard.js")],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        node = None
    if node is not None:
        if node.returncode != 0:
            raise SystemExit(f"dual_keyboard.js failed:\n{node.stdout}\n{node.stderr}")
        print((node.stdout or "").strip() or "dual_keyboard.js: OK")





def _write_pcm(path: Path, x: np.ndarray, sr: int) -> None:
    peak = float(np.max(np.abs(x))) or 1.0
    pcm = np.clip(x / peak * 0.85, -1.0, 1.0)
    samples = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(samples.tobytes())


def check_discrimination() -> None:
    if MIXED_HI_HZ < 4999:
        raise SystemExit(f"shared mix peak range must reach 5 kHz, got {MIXED_HI_HZ}")

    sr = 48000
    n = 8192
    t = np.arange(int(sr * 2.0), dtype=np.float64) / sr
    # Vocals-only: 220 Hz + formant-ish harmonic stack.
    voice = np.zeros_like(t)
    for k, amp in enumerate((1.0, 0.7, 0.55, 0.35, 0.28, 0.18, 0.12, 0.08), start=1):
        voice += amp * np.sin(2 * math.pi * 220.0 * k * t)
    # Psytrance-like: 55 Hz kick + inharmonic highs.
    kick = np.sin(2 * math.pi * 55.0 * t) * np.exp(-((t % 0.25) * 28))
    highs = (
        0.35 * np.sin(2 * math.pi * 2100.0 * t)
        + 0.28 * np.sin(2 * math.pi * 3120.0 * t)
        + 0.22 * np.sin(2 * math.pi * 3800.0 * t)
    )
    psy = kick + highs

    with tempfile.TemporaryDirectory() as td:
        vpath = Path(td) / "voice.wav"
        ppath = Path(td) / "psy.wav"
        _write_pcm(vpath, voice, sr)
        _write_pcm(ppath, psy, sr)
        vrep = analyze(load_wav(vpath)[0], sr, ignore_vocals=False)
        vnotes = {p["note"] for p in vrep["top_pitches"]}
        if "A3" not in vnotes:
            raise SystemExit(f"vocal stack should light A3, got {sorted(vnotes)}")
        spec, bin_hz = rfft_db(psy[:n], sr, n)
        cl = cluster_peaks(extract_cluster_peaks(spec, bin_hz))
        if len(cl) < 2:
            raise SystemExit(f"psytrance mix-peaks must yield ≥2 sources, got {len(cl)}")
        if not any(c["f0"] < 90 for c in cl) or not any(c["f0"] > 1800 for c in cl):
            raise SystemExit(f"psytrance clusters missing low/high: {[round(c['f0']) for c in cl]}")
        spec_v, bin_v = rfft_db(voice[:n], sr, n)
        cl_v = cluster_peaks(extract_cluster_peaks(spec_v, bin_v))
        if len(cl_v) != 1:
            raise SystemExit(f"vocal harmonic stack must be 1 source, got {len(cl_v)}")
    print("discrimination: vocal A3 + 1 source; psytrance low+high clusters OK")


def check_spectrum_scale() -> None:
    sr = 44100
    n = 4096
    t = np.arange(n, dtype=np.float64) / sr
    tone = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    db, bin_hz = rfft_db(tone, sr, n)
    peak_f = peak_hz_of_db(db, bin_hz)
    if abs(peak_f - 440.0) > bin_hz * 1.5:
        raise SystemExit(f"440 Hz tone peaked at {peak_f:.2f} Hz (bin {bin_hz:.3f} Hz)")
    x440 = spec_x_of(440.0)
    x_left = spec_x_of(27.5)
    x_right = spec_x_of(440.0 * (2.0 ** (39.0 / 12.0)))
    if abs(x_left) > 1e-12 or abs(x_right - 1) > 1e-9:
        raise SystemExit(f"log axis ends wrong: A0={x_left} C8={x_right}")
    # 440 is 4 octaves above 27.5, so it is not the midpoint.
    if not (0.50 < x440 < 0.60):
        raise SystemExit(f"440 Hz should sit near 0.55 on a log A0–C8 axis, got {x440:.4f}")
    print(f"spectrum scale: 440 Hz peak={peak_f:.2f} Hz, log-x={x440:.4f} (440 tick)")


def main() -> None:
    check_ffmpeg()
    check_capture_scripts()
    check_public_site()
    check_spectrum_scale()
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        wav = out_dir / "smoke_tones.wav"
        write_tone_wav(wav)
        audio, sr = load_wav(wav)
        if sr != SR:
            raise SystemExit(f"unexpected sample rate {sr}")
        if audio.size < SR:
            raise SystemExit("synthetic WAV too short")
        report = analyze(audio, sr, ignore_vocals=False)
        cli = subprocess.run(
            [sys.executable, str(SCRIPTS / "analyze_instruments.py"), str(wav), "--out-dir", str(out_dir)],
            capture_output=True,
            text=True,
        )
        if cli.returncode != 0:
            raise SystemExit(f"analyze_instruments.py failed:\n{cli.stdout}\n{cli.stderr}")
        json_path = out_dir / "smoke_tones_report.json"
        md_path = out_dir / "smoke_tones_report.md"
        if not json_path.is_file() or not md_path.is_file():
            raise SystemExit("analyze_instruments.py did not write report files")

    notes = {p["note"] for p in report["top_pitches"]}
    missing = [name for name, _ in TONES if name not in notes]
    print("Smoke test source: synthetic E2 + A4 + C5 @ 48 kHz")
    print(f"duration={report['duration_sec']}s peak={report['peak']} rms={report['rms']}")
    print("top pitches:")
    for p in report["top_pitches"][:8]:
        print(f"  {p['note']}: ~{p['hz_median']} Hz")
    print("instrument families:")
    for inst in report["instruments"]:
        print(f"  {inst['family']} (salience {inst['salience']})")
    if report["peak"] <= 0:
        raise SystemExit("smoke WAV was silent")
    if missing:
        raise SystemExit(f"analyzer missed expected notes: {missing}; found {sorted(notes)}")
    print("SMOKE OK: recovered E2, A4, and C5")
    check_discrimination()
    check_crayon_piano()


if __name__ == "__main__":
    main()