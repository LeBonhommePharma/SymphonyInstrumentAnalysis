# Piano-crayon / Crayon piano

Live mic **or** yesterday’s Shannon capture → visual piano, color-coded with the macOS Crayons pitch map. Same AnalyserNode FFT peak-picker for both. Track chips pick which musician band to follow. Auto-accord estimates concert pitch so slightly-off outdoor tuning still lights the right crayon.

## Open

**Chrome or Safari** (allow the microphone for live mode).

Serve from this directory on a free port. **Do not use 8765** — that port is taken by Claude Science (you will get a “You've been signed out…” page instead of the piano). 8766 is also Claude Science; 8787 is often Cursor.

```bash
cd web
python3 -m http.server 4173
```

Then visit http://localhost:4173/keyboard.html

Safari can also open [`keyboard.html`](keyboard.html) via `file://` as a fallback (Chrome often blocks the mic **and** sample fetch on `file://`).

## Prepare yesterday’s sample

`*.wav` files are gitignored, so a clean checkout has no audio. Replay loads `web/samples/final_song.wav` (copy of `captures/final_song.wav`, Shannon, ~75 s).

From the **repository root** (if you already `cd web`, run `cd ..` first):

```bash
mkdir -p web/samples
cp captures/final_song.wav web/samples/final_song.wav
```

The piano does **not** download the WAV until you click **Rejouer l’échantillon / Replay yesterday**. If the file is missing, that click shows an error; live mic still works.

## Replay yesterday (Parc Roland Beaudin)

1. Click **Rejouer l’échantillon / Replay yesterday**.
2. Loads `samples/final_song.wav` (copy of `captures/final_song.wav`, Shannon, ~75 s) into Web Audio.
3. The **same FFT peak-picker** as live mic lights the crayon keys (polyphonic, brightness = dynamics).
4. Default is **muted** (visual only). Check **Entendre / Unmute sample** to hear it quietly.
5. Drag the waveform playhead to scrub time.

Status line: `Échantillon / Sample: final_song.wav (Shannon, hier)`.

## Live mic

1. Click **Écouter / Start listening** and allow the mic.
2. The piano **follows the macOS default input** (Shannon, LPhone, built-in, …). Change it in System Settings → Sound; this page switches with it.
3. Same crayon color = same pitch class (any octave). Do/C is Maraschino; La/A Blueberry is the concert A (auto-accord, not blindly 440).

## Pistes / Tracks

Big colored chips. Multi-select. There are no true stems — each musician is a **frequency band** on the same FFT (live mic and replay).

- **Tous / All** (default) — mixed FFT lighting, 60–2500 Hz (same as before).
- Click a musician while Tous is on → follow **only** that band.
- Click more musicians → **union** of those bands’ notes.
- Click Tous → everyone again.
- Empty selection snaps back to Tous (**All-if-none**).

Status: `Pistes / Tracks: Contrebasse + Guitare A`.

| Chip | Band | Notes |
|------|------|--------|
| Contrebasse / Bass | 40–180 Hz | Octave-mapped onto C2–C7 |
| Violoncelle / Cello | 130–400 Hz | Low-mid wooden sustain |
| Guitare A / Guitar A | 200–520 Hz | Lower-mid guitar body |
| Guitare B / Guitar B | 480–900 Hz | Upper guitar (offset so A/B differ) |
| Nylon / aigu / high | 600–2500 Hz | Sparkle / extensions |

Guitar A/B use a lower vs upper split (not even/odd frames) so the two chips stay visually distinct without flickering.

## Auto-accord / Auto-tune

**On by default.** Uncheck to **lock A = 440 Hz**.

1. Strong spectral peaks (80–1400 Hz) are interpolated, gated vs the noise floor, and grouped so harmonics don’t vote twice.
2. Each fundamental is mapped to the nearest 12-TET pitch at A=440; the **cents offset** is kept.
3. Median of those cents over a ~2 s window, clamped to ±50 cents (A4 ≈ 427–453 Hz). Offsets past a quarter-tone wrap to the neighboring note, so the estimator does not claim ±100 cents.
4. Leaky average so the estimate doesn’t jump every frame.
5. Keys snap with `midi = 69 + 12*log2(f / A_est)`. Crayon colors stay pitch-class (Do = Maraschino, …).

Readout: `La / A ≈ 442 Hz · +8 cents · un peu trop haut / a bit sharp`.

## Kid-genius how-to

Chante, joue, ou rejoue hier : la touche s’allume avec son crayon. Même couleur = même son (Do rouge Maraschino, La bleu Blueberry). Auto-accord trouve le La du parc; choisis Contrebasse ou Guitare A pour suivre un musicien.
