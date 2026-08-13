# Symphony Instrument Analysis

Standalone Python spectral-analysis toolkit plus a crayon piano (native iOS/iPadOS/Mac app and a static web viewer).
See [`README.md`](README.md), [`ios/README.md`](ios/README.md), and [`web/README.md`](web/README.md).

- **iOS/iPadOS/Mac app** (`ios/CrayonPiano.swiftpm`): SwiftUI + AVAudioEngine, packaged as a
  Swift Playgrounds App (`.iOSApplication`). Tap keys, live mic, built-in demo, scrolling
  waveform. **No HTTP server, no ports.** Runs on iPadOS 27 in Swift Playgrounds (no Mac) or on
  macOS 27 via Xcode / Swift Playgrounds — open the `.swiftpm` directly (there is no `.xcodeproj`).
- **CLI pipeline** (`scripts/*.py`): numpy/scipy FFT analysis of recorded audio → instrument
  families + note sequences, chord visualizations (matplotlib), and resynthesis.
- **Web viewer** (`web/keyboard.html`): self-contained Web Audio page. Open the file directly
  (`file://`) — replay synthesizes a demo if the WAV is missing. Live mic on iPhone still
  needs the native app (Safari will not grant `getUserMedia` to `file://`).

There is no database, backend service, build step, or test/lint framework configured.

## Setup

Debian/Ubuntu — install OS packages first (`python3-venv` matches the default `python3`), then
create the venv:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or run `bash .cursor/install.sh` — the same commands as the Cloud Agent install script that
`.cursor/environment.json` invokes.

## Verify the environment

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/analyze_instruments.py --help
```

The smoke test checks ffmpeg, synthesizes tones for `analyze_instruments.py`, and confirms the
capture scripts exit cleanly when no AVFoundation devices exist.

## Cursor Cloud specific instructions

- The repo-managed `.cursor/environment.json` runs `bash .cursor/install.sh`, which creates
  `.venv` and installs `requirements.txt`. Use `.venv` before running Python (activate it or
  call `.venv/bin/python`).
- **matplotlib** is required by `scripts/visualize_chords.py`, `visualize_chord_layers.py`,
  `chord_pitch_colors.py`, and `resynth_from_chords.py`. It is pinned in `requirements.txt`, so
  the venv install covers it.
- **matplotlib is headless here:** run visualization scripts with `MPLBACKEND=Agg` (they
  `savefig` PNGs into `analysis_out/`; there is no display).
- `scripts/list_mics.py`, `scripts/probe_mics.py`, and `scripts/record_mic.py` use macOS
  AVFoundation via ffmpeg. On Linux they exit 1 with `No AVFoundation audio devices found.` —
  that is expected; do not treat it as a setup failure. Demonstrate the working path with
  `scripts/smoke_test.py` or by analyzing a 16-bit PCM WAV with `scripts/analyze_instruments.py`.
- **iOS app cannot be built on this Linux VM** (no Xcode/Swift toolchain). Edit Swift under
  `ios/CrayonPiano.swiftpm/` and verify the shared logic through the web piano at
  `file:///workspace/web/keyboard.html` (it mirrors the same crayon map, FFT peak-picker, and
  waveform transform).

### Input data is not committed
`captures/*.wav` and `web/samples/*.wav` are gitignored and **absent on a fresh checkout**.
The web replay button and the iOS **Rejouer** control both fall back to a built-in 8 s synth
demo, so you do **not** need a WAV or a local server to demonstrate the piano.

- `scripts/analyze_instruments.py <file.wav>` requires a **16-bit PCM** WAV.
- `scripts/visualize_chords.py` and `scripts/visualize_chord_layers.py` hardcode
  `captures/final_song.wav` (plus the committed `analysis_out/final_song_chords.json`).

If no real capture is available, generate a synthetic 16-bit PCM WAV with `wave` + `numpy` to
exercise the Python pipeline.

### Web viewer (no port)
Open the file directly (no server):

```bash
xdg-open web/keyboard.html   # or in Chrome/Safari: file:///workspace/web/keyboard.html
```

Hold piano keys or crayon-legend swatches to play notes. **Rejouer** runs the built-in demo.
Do not start `python3 -m http.server` unless you are specifically testing a WAV fetch.
