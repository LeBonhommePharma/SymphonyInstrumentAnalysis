# Resynthesis from chord analysis (layered)

This audio is a **reconstruction synthesized from chord / pitch-class / frequency analysis only**,
now as **separate musician/instrument layers** (not one flattened pad).

- Source data: `analysis_out/final_song_chords.json`
- Ensemble: upright bass, cello, acoustic guitar ×2, nylon guitar, viola/violin sheen
- Constraints: wooden chords only; **no clarinet**; outdoor park guess
- **No original recording** used as an audio source

See **`analysis_out/resynth_layers.md`** for the Audacity-style stem → role → freq table and split rules.

## Outputs

| File | Notes |
|------|--------|
| `analysis_out/resynth_layers/*.wav` | One mono stem per musician (6 files) |
| `analysis_out/resynth_from_chords_stems.wav` | Stereo mix of all layers (~75.5s, 100 segments) |
| `analysis_out/resynth_from_chords.wav` | Mono sum (legacy) |
| `analysis_out/resynth_from_chords_preview.wav` | First 15s stereo preview |
| `analysis_out/resynth_layers_map.png` | Layer activity over time |

## Fidelity

Crude but separable: each stem carries only its register/role notes with a distinct timbre.
