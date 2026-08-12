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
