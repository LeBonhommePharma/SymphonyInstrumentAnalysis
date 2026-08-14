# Piano-crayon

Open [`keyboard.html`](keyboard.html) in Safari or Chrome. Prefer `python3 -m http.server 4173` in this folder, then http://localhost:4173/keyboard.html. Chrome often blocks mic and sample fetch on `file://`. On iPhone use the native app in `ios/`.

**Listen** (green ring) — live mic FFT, silent. Turns into a red square to stop.

**Replay** (play circle) — `samples/final_song.wav` if present. Muted until **Son**. Turns into a square while playing.

**Pistes** — empty until a band is heard. Click a chip to follow that musician; empty selection snaps back to the mix.

**Look** — Day, Light, Dark, Night, Stealth, plus **Auto** (ambient light / time of day). A manual swatch sticks until you tap Auto again.

**Spectre** — top-right. One log-Hz plot (A0–C8, **440** marked) in dBFS. Every clustered source and held key is a crayon tick on those same axes. No source cap.

**Keyboard** — full 88 keys, La0 to Do8, spanning the page (52 white keys × 28px minimum; swipe if the window is narrower). Hold keys for polyphony.
