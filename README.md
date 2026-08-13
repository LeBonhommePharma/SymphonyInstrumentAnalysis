# Symphony Instrument Analysis

Standalone mic-capture + spectral analysis project (**not** related to FlexAIDdS).

**iOS / iPadOS / Mac (no ports):** the app ships as a Swift Playgrounds package [`ios/CrayonPiano.swiftpm`](ios/CrayonPiano.swiftpm) — run it directly on **iPadOS 27** in Swift Playgrounds (no Mac needed) or on **macOS 27** in Xcode / Swift Playgrounds. Tap keys, listen through the mic, or replay the built-in demo on the scrolling waveform. See [`ios/README.md`](ios/README.md).

**Web, also no server:** open [`web/keyboard.html`](web/keyboard.html) in Safari (or Chrome). Hold keys to play crayon notes; **Rejouer** uses a built-in demo if `samples/final_song.wav` is missing. Live mic on iPhone needs the native app above (Safari blocks `getUserMedia` on `file://`). Details in [`web/README.md`](web/README.md).

**Terminal (same layout):** `.venv/bin/python scripts/crayon_piano.py` — Listen / Rejouer, musician lanes, chroma, keyboard. No time slider. Optional `--wav` 16-bit PCM.

Records from the best available macOS mic, denoises, then estimates:

- likely instrument families (vocals/lyrics de-emphasized)
- note sequences with frequencies in Hz

## Setup

Debian/Ubuntu (install OS packages first; `python3-venv` matches the default `python3`):

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cloud / repeatable install:

```bash
bash .cursor/install.sh
```

Verify the analysis path (works without a microphone):

```bash
python3 scripts/smoke_test.py
```

## Usage

```bash
# list mics
python3 scripts/list_mics.py

# probe which mic has best signal / least noise
python3 scripts/probe_mics.py

# record (auto-picks best mic; play music while it runs)
python3 scripts/record_mic.py --seconds 90

# analyze (ignores voices/lyrics by default)
python3 scripts/analyze_instruments.py captures/<file>.wav
```

Outputs land in `analysis_out/` (Markdown + JSON). Raw WAVs stay local in `captures/` (gitignored).

`list_mics.py` / `probe_mics.py` / `record_mic.py` use macOS AVFoundation. Without a capture device they exit 1 with `No AVFoundation audio devices found.` On Linux, use `smoke_test.py` or feed a 16-bit PCM WAV to `analyze_instruments.py`.
