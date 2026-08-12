# Piano-crayon / Crayon piano

Live mic **or** a built-in demo (or yesterday’s Shannon capture if present) → visual piano, color-coded with the macOS Crayons pitch map. Same AnalyserNode FFT peak-picker for both. Track chips pick which musician band to follow. Auto-accord estimates concert pitch so slightly-off outdoor tuning still lights the right crayon.

**On iPhone, use the native app** — [`ios/README.md`](../ios/README.md) — so you never pick a port. Safari will not give the microphone to a `file://` page.

## Open (no server)

Open [`keyboard.html`](keyboard.html) directly in Safari or Chrome (`file://`). Hold a key or a crayon in the legend to hear it. **Rejouer / Replay** synthesizes an 8 s demo when `samples/final_song.wav` is absent, so nothing needs to be served.

If you already have `samples/final_song.wav` and want to serve the folder, any free port is fine — there is no required port.

## Replay

1. Click **Rejouer l’échantillon / Replay yesterday** (or **Replay demo** when using the built-in phrase).
2. If `samples/final_song.wav` is present it loads that; otherwise a built-in synth demo is used. Same FFT peak-picker either way.
3. Default is **muted** (visual only). Check **Entendre / Unmute sample** to hear it quietly.
4. Scrub **Temps / Time** from 0 to the end.

Status line: file sample → `Échantillon / Sample: final_song.wav (Shannon, hier)`; otherwise `Démo intégrée / Built-in demo (pas de serveur / no server)`.

## Live mic

On **iPhone / iPad**, use the native app (`ios/CrayonPiano`) — Safari will not grant the microphone to a `file://` page.

On **macOS / desktop**:

1. Click **Écouter / Start listening** and allow the mic.
2. The piano follows the OS default input. Change it in System Settings → Sound; this page switches with it.
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
3. Median of those cents over a ~2 s window, clamped to ±100 cents (A4 ≈ 415–466 Hz) so park noise can’t yank tuning to nonsense.
4. Leaky average so the estimate doesn’t jump every frame.
5. Keys snap with `midi = 69 + 12*log2(f / A_est)`. Crayon colors stay pitch-class (Do = Maraschino, …).

Readout: `La / A ≈ 442 Hz · +8 cents · un peu trop haut / a bit sharp`.

## Kid-genius how-to

Chante, joue, ou rejoue hier : la touche s’allume avec son crayon. Même couleur = même son (Do rouge Maraschino, La bleu Blueberry). Auto-accord trouve le La du parc; choisis Contrebasse ou Guitare A pour suivre un musicien.
