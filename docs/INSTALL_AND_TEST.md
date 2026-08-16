# Install and test — Ghostty, iPhone 15 Pro, iPad A16

Device-specific runbook for the crayon piano after the hub/piano unification
(vocals + dense highs, US / Canadian French CSA keys, held / need / hit scoring).

Public pages (already deployed from `main`):

- Hub: https://thebonhomme.com/SymphonyInstrumentAnalysis/
- Live listen: https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/
- Crayon piano: https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/

On every surface, **need** = the music wants this note (crayon fill), **held** = you
pressed a non-target key (ink outline), **hit** = you pressed a needed note (lime
ring, score goes up). High scores persist locally (browser `localStorage`, iOS
`UserDefaults`, TUI `~/.crayon_piano_scores.json`).

---

## 1. macOS — Ghostty TUI

### Install (once)

In **Ghostty**:

```bash
cd ~/Projects/SymphonyInstrumentAnalysis   # or your clone
bash scripts/install_macos.sh
```

That installs ffmpeg (Homebrew), creates `.venv`, and runs the non-mic checks
(density cluster, layout map, TUI `--self-test`, public-site strings, vocal /
psytrance discrimination).

If Homebrew is missing: https://brew.sh then retry.

### Run

```bash
bash scripts/run_tui.sh
```

Optional WAV: `bash scripts/run_tui.sh --wav /path/to/16bit.pcm.wav`

Ghostty must be allowed **Microphone** the first time you press **l** (Écouter):
System Settings → Privacy & Security → Microphone → Ghostty.

Resize the window to at least ~120×40 cells so the 88-key row is readable.

### Test in Ghostty

| Step | Expect |
|------|--------|
| `bash scripts/install_macos.sh` | prints `install_macos: OK` and `layout OK` |
| `bash scripts/run_tui.sh` | piano, score line (`0 · best … · US` or `CSA`), chip **Tous 27.5–5000 Hz** |
| **r** Rejouer | keys light from the built-in demo (no WAV needed) |
| Play along **Z=Do3**, **D=Do4**, **Q=La4** (same MIDI on US and CSA) | **need** fill, **held** outline, **hit** + score |
| **l** Écouter, then sing or play psytrance / a cappella | low + high (or sung) sources, not a blank / noise-only row |
| Quit and relaunch | best score restored |

Layout: the TUI infers US vs Canadian French CSA from the OS / typed glyphs.
Letter-row scan codes stay on the same piano notes; only punctuation glyphs change.

Command keys `l r c u a t q 0–5` do **not** play notes (they are transport).

---

## 2. iPhone 15 Pro (iOS)

Swift Playgrounds does **not** run on iPhone. Use HTTPS pages for a no-Mac test,
or Xcode on this Mac to install the native app.

### A — Safari (no build, mic works on HTTPS)

1. Open https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/
2. Tap **Listen with the mic** → Allow Microphone.
3. Play a vocal or high-frequency track **out loud** (Safari cannot read Now Playing).
4. Confirm Score increments when you tap a **needed** piano key.
5. Open https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/
6. Tap **Écouter**, then **Rejouer**. Confirm US / Canadien français picker, dual
   typing board, 88-key strip, and held / need / hit on the piano keys.

`file://` on iPhone **blocks** the mic. Always use the HTTPS URLs above.

### B — Native app via Xcode (this Mac → iPhone 15 Pro)

1. Unlock the phone. Settings → Privacy & Security → **Developer Mode** → On (reboot if asked).
2. Cable to the Mac. Trust this computer on the phone.
3. Open `ios/CrayonPiano.swiftpm` in **Xcode 27**.
4. Signing: select your **Personal Team** (free Apple ID is enough).
5. Destination: **LP’s iPhone** / **iPhone 15 Pro** (not a simulator).
6. Product → Run (▶). First launch: trust the developer certificate on the phone
   (Settings → General → VPN & Device Management).
7. Allow **Microphone** when you tap **Écouter**.

### Native test on the 15 Pro

| Step | Expect |
|------|--------|
| Écouter toward a speaker playing vocals-only | keys + clusters; mix goes to 5 kHz |
| Écouter toward dense high-frequency / psytrance | a low source **and** a high source stay split |
| Rejouer | demo phrase, waveform scrolls, score line in the header |
| Tap needed keys / type on a paired keyboard | hit vs held vs need; best score survives relaunch |
| US \| Canadien français | glyphs remap; the same physical keys still hit the same notes |

---

## 3. iPad A16 (iPadOS)

The A16 iPad (11-inch, 2025) runs the native package in **Swift Playgrounds**
with no Mac, or via Xcode USB like the iPhone.

### A — Swift Playgrounds (no Mac)

1. App Store → **Swift Playgrounds** (free).
2. Get `ios/CrayonPiano.swiftpm` onto the iPad:
   - GitHub → Code → Download ZIP → unzip in **Files**, or
   - AirDrop the `CrayonPiano.swiftpm` folder from this Mac, or
   - iCloud Drive.
3. Tap `CrayonPiano.swiftpm` → **Run**.
4. Allow Microphone on **Écouter**.

### B — Safari HTTPS (same URLs as the iPhone)

Use the public tutorial + piano links. Pair a hardware keyboard (US or CSA) and
confirm the layout picker remaps the board.

### C — Xcode USB

Same as iPhone 15 Pro, destination **iPad A16**.

### Native test on the A16

Same table as the 15 Pro, plus:

| Step | Expect |
|------|--------|
| Magic Keyboard / CSA keyboard | picker **Canadien français**; Slash = é still maps to the same MIDI as US `/` |
| Landscape | dual board + 88-key strip both usable; spectrum stays on the side when wide |
| Multi-touch on the piano | chords ≤ 8 when Accords is on |

---

## 4. What “pass” means (all three)

- Vocals-only material lights sung pitches and clusters as **one** harmonic source, not noise.
- Dense high-frequency / psytrance keeps a **low** cluster and a **high** cluster.
- Play-along scoring works on whatever is currently playing (mic, demo, or your WAV).
- US and Canadian French CSA share piano MIDI on the letter row.

CLI analyzer (Mac only, after install):

```bash
.venv/bin/python scripts/analyze_instruments.py captures/<file.wav>
```

Uses the same 27.5–5000 Hz peak-picker (vocals included).
