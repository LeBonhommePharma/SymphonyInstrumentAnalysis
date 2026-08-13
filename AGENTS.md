# Symphony Instrument Analysis

Standalone Python spectral-analysis toolkit plus a crayon piano (native iOS app and a static web viewer).
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

## Cursor Cloud specific instructions

Dependencies are installed to the Python **user site** (`pip install --user`) by the update
script, so scripts run with plain `python3` — no venv to activate (the README's venv flow is
optional and needs the `python3.12-venv` apt package, which is not installed here).

- **Extra dependency:** several scripts import `matplotlib`
  (`visualize_chords.py`, `visualize_chord_layers.py`, `chord_pitch_colors.py`,
  `resynth_from_chords.py`) but it is **not** listed in `requirements.txt`. The update script
  installs it alongside `requirements.txt`.
- **matplotlib is headless here:** run visualization scripts with `MPLBACKEND=Agg` (they
  `savefig` PNGs into `analysis_out/`; there is no display).
- **iOS app cannot be built on this Linux VM** (no Xcode/Swift toolchain). Edit Swift under
  `ios/CrayonPiano.swiftpm/` and verify the shared logic through the web piano at
  `file:///workspace/web/keyboard.html` (it mirrors the same crayon map, FFT peak-picker, and
  waveform transform). The `.swiftpm` opens/runs in Swift Playgrounds (iPadOS/macOS) or Xcode.

### Input data is not committed
`captures/*.wav` and `web/samples/*.wav` are gitignored and **absent on a fresh checkout**.
The web replay button and the iOS **Rejouer** control both fall back to a built-in 8 s synth
demo, so you do **not** need a WAV or a local server to demonstrate the piano.

- `scripts/analyze_instruments.py <file.wav>` still requires a **16-bit PCM** WAV.
- `scripts/visualize_chords.py` and `scripts/visualize_chord_layers.py` hardcode
  `captures/final_song.wav` (plus the committed `analysis_out/final_song_chords.json`).

If no real capture is available, generate a synthetic 16-bit PCM WAV with `wave` + `numpy` to
exercise the Python pipeline.

### Web viewer (no port)
Open the file directly:

```bash
# no server
xdg-open web/keyboard.html
# or in Chrome: file:///workspace/web/keyboard.html
```

Hold piano keys or crayon-legend swatches to play notes. **Rejouer** runs the built-in demo.
Do not start `python3 -m http.server` unless you are specifically testing a WAV fetch.

- **Live mic does not work on this Linux VM** (no capture device). The mic scripts
  (`list_mics.py`, `probe_mics.py`, `record_mic.py`) are macOS/AVFoundation-only.
  On a real iPhone, use the native app in `ios/CrayonPiano`.
