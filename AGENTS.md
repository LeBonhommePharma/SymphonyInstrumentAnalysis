# Agent notes

Python CLI for mic capture + spectral instrument analysis. Public silent tutorial is static files under `docs/` (GitHub Pages). Local `scripts/serve_tutorial.py` is localhost-only.

ELI5 how-to and figure: `docs/HOW_TO_ELI5.md` (figure: `docs/howto-eli5.png`).

Silent live tutorial (visualizes the device’s current audio, does not play music).

Public HTTPS (phone on 5G): `https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/`

Local-only:

```bash
python3 scripts/serve_tutorial.py
```

Do not set this repo’s Pages custom domain to `thebonhomme.com` (that domain belongs to `lebonhommepharma.github.io`).

## Setup

Debian/Ubuntu — install OS packages before creating the venv (`python3-venv` matches default `python3`):

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or run `bash .cursor/install.sh` (same commands as the Cloud Agent install script).

## Verify the environment

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/analyze_instruments.py --help
```

The smoke test checks ffmpeg, synthesizes E2/A4/C5 for `analyze_instruments.py`, and confirms the capture scripts exit cleanly when no AVFoundation devices exist.

## Cursor Cloud specific instructions

- Use `.venv` created by `.cursor/install.sh` before running Python.
- `scripts/list_mics.py`, `scripts/probe_mics.py`, and `scripts/record_mic.py` use macOS AVFoundation via ffmpeg. On Linux they exit 1 with `No AVFoundation audio devices found.` That is expected.
- On cloud agents, demonstrate the working path with `scripts/smoke_test.py` or by analyzing a 16-bit PCM WAV with `scripts/analyze_instruments.py`.
- Do not treat mic-capture failure on Linux as an environment setup failure.
