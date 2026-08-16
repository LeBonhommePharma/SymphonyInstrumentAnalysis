# Layered chord resynthesis (Audacity-style stems)

Reconstruction from **chord / pitch-class analysis only** (`final_song_chords.json`).
No mic capture WAV was used as an audio source.

## Ensemble guess (wooden chords, outdoor park)

Wooden-chord layers only (**no clarinet**; Parc Roland Beaudin outdoor vibe):

| Stem file | Musician / instrument | Role | Freq range | Timbre notes |
|-----------|----------------------|------|------------|--------------|
| `01_upright_bass.wav` | Upright double bass | lowest pitch / root-ish floor | 55–130 Hz | h=(0.12, 0.04) attack=0.05s |
| `02_cello.wav` | Cello | low-mid wooden sustain | 130–320 Hz | h=(0.28, 0.12, 0.04) attack=0.06s |
| `03_guitar_a.wav` | Acoustic guitar 1 (steel) | mid chord body | 196–440 Hz | h=(0.38, 0.18, 0.1, 0.05) attack=0.018s |
| `04_guitar_b.wav` | Acoustic guitar 2 (steel double) | mid chord body / alternate notes | 220–494 Hz | h=(0.42, 0.2, 0.12, 0.06) attack=0.022s |
| `05_nylon_guitar.wav` | Classical / nylon guitar | warm mid-high extensions | 247–587 Hz | h=(0.3, 0.14, 0.06) attack=0.028s |
| `06_viola_sheen.wav` | Viola / violin sheen | highest extension / sparkle | 392–880 Hz | h=(0.35, 0.22, 0.12, 0.07) attack=0.045s |

## How notes are split

For each timed chord segment:

1. Infer root from chord label (fallback: most-salient PC).
2. Sort PCs low→high; put root at the bottom of the stack.
3. **Upright bass** → lowest / root-ish in ~55–130 Hz.
4. **Cello** → next tone in ~130–320 Hz.
5. Remaining mid tones **round-robin** across **guitar A**, **guitar B**, and **nylon** (never dump all mids on one guitar).
6. With 4–5 PCs, the **highest extension** also feeds **viola/violin sheen** (~392–880 Hz).

Example assignments (first segments):

- **0.5–1.0s** `Aadd9` (pcs A, B, G, E, F) → upright_bass=110Hz; cello=165Hz; guitar_a=349Hz; guitar_b=392Hz; viola_sheen=494Hz
- **1.5–2.0s** `F#maj7` (pcs F#, F, A, G, E) → upright_bass=92Hz; cello=165Hz; guitar_a=349Hz; guitar_b=392Hz; viola_sheen=440Hz
- **2.0–2.5s** `G#maj7` (pcs G, G#, E) → upright_bass=104Hz; cello=165Hz; guitar_a=392Hz
- **2.5–3.0s** `Gadd9` (pcs A, A#, B, G, D) → upright_bass=98Hz; cello=147Hz; guitar_a=220Hz; guitar_b=466Hz; viola_sheen=494Hz
- **3.0–3.5s** `D6` (pcs D, A, F#, F, B) → upright_bass=73Hz; cello=175Hz; guitar_a=370Hz; guitar_b=440Hz; viola_sheen=494Hz
- **4.5–5.0s** `G7` (pcs G, B, F, A, G#) → upright_bass=98Hz; cello=175Hz; guitar_a=415Hz; guitar_b=440Hz; viola_sheen=494Hz
- **5.0–6.0s** `Dmin6` (pcs A, D, F, G, B) → upright_bass=73Hz; cello=175Hz; guitar_a=392Hz; guitar_b=440Hz; viola_sheen=494Hz
- **6.0–7.0s** `Fmaj7` (pcs A, E, F) → upright_bass=87Hz; cello=165Hz; guitar_a=220Hz
- **7.0–8.0s** `C6` (pcs A, C, E, G) → upright_bass=65Hz; cello=165Hz; guitar_a=392Hz; guitar_b=440Hz; viola_sheen=440Hz
- **8.0–8.5s** `A7` (pcs C#, A, E, G, D) → upright_bass=110Hz; cello=277Hz; guitar_a=294Hz; guitar_b=330Hz; viola_sheen=784Hz

## Outputs

### Individual mono stems
- `analysis_out/resynth_layers/01_upright_bass.wav`
- `analysis_out/resynth_layers/02_cello.wav`
- `analysis_out/resynth_layers/03_guitar_a.wav`
- `analysis_out/resynth_layers/04_guitar_b.wav`
- `analysis_out/resynth_layers/05_nylon_guitar.wav`
- `analysis_out/resynth_layers/06_viola_sheen.wav`

### Mixes
- `analysis_out/resynth_from_chords_stems.wav` — **stereo stems mix** (panned layers summed; play this)
- `analysis_out/resynth_from_chords.wav` — mono sum of the same layers (legacy path)
- `analysis_out/resynth_from_chords_preview.wav` — first 15s stereo preview
- `analysis_out/resynth_layers_map.png` — optional layer map figure

## Fidelity

Readable wooden-chord sketch of analyzed pitch stacks and timing — not the original performance.
Each layer has a distinct envelope/harmonic recipe so ears can separate musicians.
