# Symphony Instrument Analysis

Standalone Python spectral-analysis toolkit plus a static "crayon piano" web viewer.
See [`README.md`](README.md) and [`web/README.md`](web/README.md) for the full usage docs.

- **CLI pipeline** (`scripts/*.py`): numpy/scipy FFT analysis of recorded audio → instrument
  families + note sequences, chord visualizations (matplotlib), and resynthesis.
- **Web viewer** (`web/keyboard.html`): a self-contained Web Audio API page that lights up a
  color-coded visual piano from either the live mic or a replayed WAV sample.

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

### Input data is not committed
`captures/*.wav` and `web/samples/*.wav` are gitignored and **absent on a fresh checkout**, so
you must supply audio before most things do anything useful:

- `scripts/analyze_instruments.py <file.wav>` requires a **16-bit PCM mono/stereo WAV**.
- `scripts/visualize_chords.py` and `scripts/visualize_chord_layers.py` hardcode
  `captures/final_song.wav` (plus the committed `analysis_out/final_song_chords.json`).
- The web replay button loads `web/samples/final_song.wav` (a copy of `captures/final_song.wav`).

If no real capture is available, generate a synthetic 16-bit PCM WAV with `wave` + `numpy` to
exercise the pipeline end-to-end.

### Web viewer
Serve the `web/` directory and open `keyboard.html`; use the replay sample for a headless demo:

```bash
cd web && python3 -m http.server 4173   # then http://localhost:4173/keyboard.html
```

- Use port **4173**. Per the READMEs, avoid **8765/8766** (Claude Science) and **8787** (Cursor).
- **Live mic does not work on this Linux VM** (the page shows "Requested device not found").
  The mic scripts (`list_mics.py`, `probe_mics.py`, `record_mic.py`) are macOS/AVFoundation-only
  and are effectively non-functional here even though `ffmpeg` is on PATH. Use the **Replay
  sample** button (or the CLI against a WAV) to demonstrate functionality.
# Agent notes

Python CLI for mic capture + spectral instrument analysis. Public silent tutorial is static files under `docs/` (GitHub Pages). Local `scripts/serve_tutorial.py` is localhost-only.

ELI5 how-to and figure: `docs/HOW_TO_ELI5.md` (figure: `docs/howto-eli5.png`).

Silent live tutorial (visualizes the device’s current audio, does not play music).

Public HTTPS (phone on 5G): `https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/`

The page draws this device’s live sound only (mic / shared tab). It does not read Apple’s Now Playing API. If there is no melody it still draws noise/voices. Time is Logic-style waveform tracks, not a slider.

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
