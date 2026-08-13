# Agent notes

Python CLI for mic capture + spectral instrument analysis. There is no web server.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`ffmpeg` must be on `PATH`. On Debian/Ubuntu also install `python3.12-venv`.

## Verify the environment

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/analyze_instruments.py --help
```

The smoke test synthesizes E2/A4/C5 and checks that `analyze_instruments.py` recovers those notes. Use it on Linux/cloud VMs where there is no microphone.

## Cursor Cloud specific instructions

- Activate `.venv` (created by the environment install script) before running Python.
- `scripts/list_mics.py`, `scripts/probe_mics.py`, and `scripts/record_mic.py` use macOS AVFoundation via ffmpeg. They will exit with "No AVFoundation audio devices found" on Linux. That is expected.
- On cloud agents, demonstrate the working path with `scripts/smoke_test.py` or by analyzing a 16-bit PCM WAV with `scripts/analyze_instruments.py`.
- Do not treat mic-capture failure on Linux as an environment setup failure.
