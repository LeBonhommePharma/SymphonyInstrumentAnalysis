# Piano-crayon

Open [`keyboard.html`](keyboard.html) in Safari or Chrome, or the public copy at
https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/ (HTTPS mic works on iPhone 15 Pro
and iPad A16). Prefer `python3 -m http.server 4173` in this folder, then http://localhost:4173/keyboard.html. Chrome often blocks mic and sample fetch on `file://`. On iPhone use HTTPS or the native app in `ios/`. See [docs/INSTALL_AND_TEST.md](../docs/INSTALL_AND_TEST.md).

**Écouter** — live mic (or computer audio) FFT, silent. The button reads **Arrêter** while listening.

**Rejouer** — `samples/final_song.wav` if present, else a built-in 8 s demo. Muted until **Son**. Reads **Arrêter** while playing.

**Accords / Son / La auto** — chords (up to 8 notes), hear replay, estimate concert A (off locks 440 Hz).

**Pistes** — one color chip and one stacked lane per density cluster. Click to solo, click more to stack, click the count to hear all. Empty selection snaps back to the mix.

**Clavier** — pick **US** or **Canadien français**. The whole board remaps at once (glyphs, ISO extra key, hardware `event.code`). Each character key is a crayon note: **Z = Do3**, **D = Do4** (red), **Q = La4**. Three highlights: **need** (music wants this note), **held** (you pressed a non-target), **hit** (correct — score persists in `localStorage`). Type with up to 10 fingers; an 11th key is allowed only when it is well clustered with keys already held.

**Look** — Day, Light, Dark, Night, Stealth, plus **Auto** (ambient light / time of day). A manual swatch sticks until you tap Auto again.

**Spectre** — top-right. One log-Hz plot (A0–C8, **440** marked) in dBFS. Every clustered source and held key is a crayon tick on those same axes. No source cap.

**Piano strip** — full 88 keys, La0 to Do8 (52 white keys × 28px minimum) for listen/replay lighting.
