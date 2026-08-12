# Analyse visuelle des accords — langage des crayons
# Chord visual analysis — crayon language

Pour les petits génies (environ 7–8 ans) : on lit avec les **yeux et les couleurs**.
For little geniuses (~7–8): read with your **eyes and colors**.

**Règle magique / Magic rule:** la même couleur = toujours le même son.
Same color = always the same pitch. Forever. Predictable. Safe.

## La boîte de crayons / The crayon box (apprends une fois)

Palette = **macOS Color Picker crayons** (`NSColorList` « Crayons » /
`/System/Library/Colors/Crayons.clr`). Ex. Maraschino (cherry red), Lime
(electric lime), Tangerine (orange), Magenta, Grape…

Chaque crayon a **cinq** étiquettes :
1. **Français** — Do Ré Mi Fa Sol La Si (comme à l’école au Québec)
2. **Anglais** — C D E F G A B
3. **Nom du crayon macOS** — Maraschino, Lime, Blueberry…
4. **Petite partition** — la note écrite sur la portée (clef de sol)
5. **~Hz** — un tout petit chiffre (vitesse de vibration) — optionnel

Astuce : **Blueberry = La / A** — c’est la note que les orchestres utilisent pour s’accorder (~440 Hz).

| Français | English | Crayon macOS | ~Hz | RGB |
|----------|---------|--------------|-----|-----|
| Do | C | Maraschino | ~262 | `rgb(251,2,7)` |
| Do♯ | C# | Cayenne | ~277 | `rgb(128,0,2)` |
| Ré | D | Tangerine | ~294 | `rgb(253,128,8)` |
| Ré♯ | D# | Lemon | ~311 | `rgb(255,255,10)` |
| Mi | E | Lime | ~330 | `rgb(128,255,8)` |
| Fa | F | Spring | ~349 | `rgb(33,255,6)` |
| Fa♯ | F# | Fern | ~370 | `rgb(64,128,2)` |
| Sol | G | Spindrift | ~392 | `rgb(102,255,204)` |
| Sol♯ | G# | Sky | ~415 | `rgb(102,204,255)` |
| **La** | **A** | **Blueberry** | **~440** | `rgb(0,0,255)` |
| La♯ | A# | Grape | ~466 | `rgb(128,0,255)` |
| Si | B | Magenta | ~494 | `rgb(251,2,255)` |

## Les images / The pictures

### 1. Carte des crayons / Pitch-color map
`chord_chroma_heatmap.png`

Les rangées sont les 12 crayons. Une **bande brillante** = ce crayon chante fort.
Plusieurs bandes ensemble = plusieurs sons en même temps (un accord).

### 2. Sandwich de crayons / Color sandwich
`chord_progression_stacks.png`

Chaque moment est un **sandwich de couleurs**. Regarde comment les couches changent.

### 3. Quand les crayons changent / When the crayons change
`chord_sync_dwell.png`

- Barres **hautes** = l’accord reste longtemps
- Barres **courtes** = changement rapide  
Médiane ici ≈ **0.50 s**.

### 4. Quel crayon suit quel crayon / Which colors follow which
`chord_transition_network.png`

Chaque bulle est un accord en parts de couleur. Les flèches montrent ce qui vient après
(plus épais = plus souvent). Tu peux suivre le voyage en couleurs seulement.

## Ce que ça raconte / What it feels like

Ce take (~75s) change souvent (médiane ≈ 0.50s).
Les crayons qu’on voit le plus : **La / A · Blueberry (~440 Hz), Mi / E · Lime (~329 Hz), Sol / G · Spindrift (~392 Hz), Fa / F · Spring (~349 Hz), Si / B · Magenta (~493 Hz)**.
Parfois un seul crayon change ; parfois tout le sandwich se recolore.

## Source

- Audio: `captures/final_song.wav`
- Accords: `analysis_out/final_song_chords.json`
- Couleurs partagées: `scripts/chord_pitch_colors.py` (macOS Crayons.clr)
