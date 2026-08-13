# Piano-crayon

Open [`keyboard.html`](keyboard.html) in Safari or Chrome. Prefer `python3 -m http.server 4173` in this folder, then http://localhost:4173/keyboard.html. Chrome often blocks mic and sample fetch on `file://`. On iPhone use the native app in `ios/`.

**Listen** (green ring) — live mic FFT, silent. Turns into a red square to stop.

**Replay** (play circle) — `samples/final_song.wav` if present. Muted until **Son**. Turns into a square while playing.

**Pistes** — empty until a band is heard. Click a chip to follow that musician; empty selection snaps back to the mix.

**Look** — Day, Light, Dark, Night, and Stealth (dim stage). The five swatches sit next to the title.

**Keyboard** — full 88 keys, La0 to Do8. On a phone, swipe sideways; it opens on Do4.
