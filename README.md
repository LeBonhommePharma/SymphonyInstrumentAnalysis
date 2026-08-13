# Symphony Instrument Analysis

Standalone mic-capture + spectral analysis project (**not** related to FlexAIDdS).

Records from the best available macOS mic, denoises, then estimates:

- likely instrument families (vocals/lyrics de-emphasized)
- note sequences with frequencies in Hz

## How-to (ELI5)

Sound is air wiggling. We count the wiggles per second (**Hz**), then name the instruments and notes.

**Live tutorial (silent — it only draws what the device is already playing):**

```bash
python3 scripts/serve_tutorial.py
```

![Figure 1. Play a song, the mic listens, look at the wiggles, name the sounds.](docs/howto-eli5.png)

Full walkthrough: [docs/HOW_TO_ELI5.md](docs/HOW_TO_ELI5.md). Live page: [docs/tutorial/index.html](docs/tutorial/index.html).

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
