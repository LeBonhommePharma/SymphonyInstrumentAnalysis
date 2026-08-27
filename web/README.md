# Piano-crayon

Open [`keyboard.html`](keyboard.html) in Safari or Chrome, or the public copy at
https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/ (HTTPS mic works on iPhone 15 Pro
and iPad A16). Prefer `python3 -m http.server 4173` in this folder, then http://localhost:4173/keyboard.html. Chrome often blocks mic, tab-audio share, and sample fetch on `file://`. On iPhone use HTTPS or the native app in `ios/`. See [docs/INSTALL_AND_TEST.md](../docs/INSTALL_AND_TEST.md).

**Rejouer** — `samples/final_song.wav` if present, else a built-in 8 s demo. Muted until **Son**. Reads **Arrêter** while playing.

**Écouter** — live **microphone** FFT, silent (never tapped to the speakers). Reads **Arrêter** while listening. Fallback when tab audio is unavailable.

**En cours** — follow whatever is **now playing** (headphones OK). Chrome: click En cours, share the **music tab**, check **Partager l’audio de l’onglet**. The page analyses that stream and stays mute so the song is not doubled in the headphones. Reads **Arrêter** while following.

Browser truth (do not expect Safari to do this):

| Browser | En cours (tab / now-playing audio) |
| --- | --- |
| **Chrome / Edge** (macOS, Windows, Linux) | **Works.** Share the tab that is playing. On Windows, whole-screen system audio may also appear. Chrome on macOS does **not** capture other apps’ system mix — share the **tab**, not the whole desktop. |
| **Safari** (macOS) | **Cannot.** `getDisplayMedia` is video-only; there is no tab or system audio track. The control stays visible and says so. Headphone path: route the song into a loopback device (BlackHole / Loopback), pick it under **Micro**, then **Écouter**. |
| **Safari** (iPhone / iPad) | **Cannot.** Use **Écouter** (mic, play out loud) or the native app. |
| **Firefox** | **Cannot** (audio flag is ignored). Use Chrome, or a loopback device + **Écouter**. |
| `file://` | Tab share is not a secure context. Serve `web/` over `http://localhost`. |

**Accords / Son / La auto** — chords (up to 8 notes), hear replay (not captured now-playing), estimate concert A (off locks 440 Hz).

**Pistes** — one color chip and one stacked lane per density cluster. Follow-along defaults to the **melody** cluster; click to solo, click more to stack, click the count for Tous. Empty selection snaps back to the mix.

**Clavier** — pick **US** or **Canadien français**. The whole board remaps at once (glyphs, ISO extra key, hardware `event.code`). Each character key is a crayon note: **Z = Do3**, **D = Do4** (red), **Q = La4**. Three highlights: **need** (music wants this note), **held** (you pressed a non-target), **hit** (correct — score persists in `localStorage`). The follow row under the transport is crayon chips in those three states — not a dump of typed characters. Type with up to 10 fingers; an 11th key is allowed only when it is well clustered with keys already held.

**Look** — Day, Light, Dark, Night, Stealth, plus **Auto** (ambient light / time of day). A manual swatch sticks until you tap Auto again.

**Spectre** — top-right. One log-Hz plot (A0–C8, **440** marked) in dBFS. Every clustered source and held key is a crayon tick on those same axes. No source cap. Need / held / hit are fill, ink outline, and bright ring — not colour alone.

**Piano strip** — full 88 keys, La0 to Do8 (52 white keys × 28px minimum) for listen/replay lighting.

### LP: headphones on a Mac

1. Play the song in Chrome (YouTube, Apple Music web, a file tab, …) with headphones on. Mute or unplug the mic.
2. Open the piano at `http://localhost:4173/keyboard.html` (not `file://`).
3. Click **En cours**. In the picker, choose the **music tab** (not the piano tab) and check **Partager l’audio de l’onglet**.
4. Crayons should follow. The piano must stay silent in the headphones (no echo).
5. **Safari:** skip En cours. Install BlackHole (or similar), set it as the song’s output and as **Micro**, then **Écouter**.
