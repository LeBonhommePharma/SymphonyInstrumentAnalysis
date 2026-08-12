# Symphony Instrument Analysis

Standalone mic-capture + spectral analysis project (**not** related to FlexAIDdS).

**iOS (no ports):** open [`ios/CrayonPiano/CrayonPiano.xcodeproj`](ios/CrayonPiano/CrayonPiano.xcodeproj) in Xcode and run on an iPhone. Tap keys, listen through the mic, or replay the built-in demo. See [`ios/README.md`](ios/README.md).

**Web, also no server:** open [`web/keyboard.html`](web/keyboard.html) in Safari (or Chrome). Hold keys to play crayon notes; **Rejouer** uses a built-in demo if `samples/final_song.wav` is missing. Live mic on iPhone needs the native app above (Safari blocks `getUserMedia` on `file://`). Details in [`web/README.md`](web/README.md).

Records from the best available macOS mic, denoises, then estimates:

- likely instrument families (vocals/lyrics de-emphasized)
- note sequences with frequencies in Hz

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# also requires ffmpeg on PATH
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
