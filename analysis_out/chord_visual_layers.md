# Accords par musicien — boîte de crayons
# Chord visuals by musician — crayon box

Pour les petits génies (~7–8 ans).
Chaque **rangée** = un musicien en bois. La couleur = le crayon macOS
(Do=Maraschino … La=Blueberry≈440 Hz … Si=Magenta) — **toujours la même règle**.

Palette = **macOS Color Picker crayons** (`NSColorList` « Crayons » /
`/System/Library/Colors/Crayons.clr`).

## Comment lire / How to read

1. **Haut/bas = qui.** Nylon/aigu en haut ; contrebasse en bas.
2. **Barre colorée** = ce musicien tient ce crayon-son.
3. **Couleurs différentes en même temps** = l’accord est partagé
   (basse prend le sol, violoncelle le suivant, guitares le milieu, aigu les étincelles).
4. **Trou dans une rangée** = ce musicien se tait un moment.
5. Lis d’abord le **français (Do Ré Mi…)**, puis l’anglais, puis le **nom du crayon macOS**, puis la petite partition, puis ~Hz.

## Boîte de crayons / Crayon box

Astuce : **Blueberry = La / A** — la note que les orchestres accordent (~440 Hz).

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

## Les cinq musiciens (bois seulement — pas de clarinette)

| Rangée | Rôle | Registre |
|--------|------|----------|
| Upright bass | lowest / root-ish floor | 55–130 Hz |
| Cello | low-mid wooden sustain | 130–320 Hz |
| Guitar A (steel) | mid chord body | 196–440 Hz |
| Guitar B (steel) | mid chord alternate | 220–494 Hz |
| Nylon / high (viola sheen) | mid-high extensions & sparkle | 247–880 Hz |

## Images / Pictures

### 1. Qui joue quel crayon / Who plays which crayon
`chord_layers_timeline.png`

Cinq panneaux empilés. Gauche→droite = temps ; haut/bas = qui.

### 2. Quand les crayons changent ensemble / When the crayons change together
`chord_layers_sync.png`

- **Ligne noire** → **tout le monde joue en même temps** (≥4 rangées)
- **Ligne ambre pointillée** → **quelques crayons seulement** (≤2 rangées)
- Bande du bas → combien de musiciens sonnent (noir=tous, bleu=3, ambre=peu)

Sur ce take (~75s, 100 segments) :
- tout le monde ensemble : **93**
- quelques crayons seulement : **2**

### 3. Un PNG par musicien / One PNG per musician
`chord_layers_facets/`

- `layer_upright_bass.png`
- `layer_cello.png`
- `layer_guitar_a.png`
- `layer_guitar_b.png`
- `layer_nylon_high.png`

## Ce que ça raconte / Plain story

La basse et le violoncelle peignent surtout le **plancher chaud**.
Les guitares A/B se partagent le **milieu** (pas les mêmes crayons tout le temps).
L’aigu s’allume quand il y a des **notes en plus en haut**.
Lignes noires = tout le monde change ensemble ; lignes ambre = texture mince.

## Source

- Accords: `analysis_out/final_song_chords.json`
- Ensemble: wooden-chord layers only (no clarinet)
- Couleurs: `scripts/chord_pitch_colors.py` (macOS Crayons.clr — même boîte que `chord_visual_analysis.md`)
