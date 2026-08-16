# Piano-crayon for iPad / iPhone / Mac

Native SwiftUI app — **no local server, no ports**. Tap keys, listen through the mic,
or replay the built-in demo on the DAW-style scrolling waveform.

It ships as a **Swift Playgrounds App package** (`CrayonPiano.swiftpm`), so you can build and
run it **directly on iPadOS 27** (no Mac needed) and on **macOS 27** (Xcode or Swift
Playgrounds). Requires iOS/iPadOS 17+.

---

## Test it now

Device matrix (Ghostty TUI, **iPhone 15 Pro**, **iPad A16**): [docs/INSTALL_AND_TEST.md](../docs/INSTALL_AND_TEST.md).

### Option A — instant, any device, zero build (HTTPS)
On the **iPhone 15 Pro** or **iPad A16**, Safari:

- Live listen: https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/
- Piano: https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/

Allow Microphone. `file://` blocks the mic on iPhone; use HTTPS.

Local file: open `web/keyboard.html` in Safari on the Mac (mic works). On iPad Files,
tap-to-play and **Rejouer** work offline; live mic still needs HTTPS or Option B/C.

### Option B — native app on **iPad A16** (Swift Playgrounds, no Mac)
1. Install **Swift Playgrounds** from the App Store (free).
2. Get `ios/CrayonPiano.swiftpm` onto the iPad. Any of:
   - On GitHub tap **Code ▸ Download ZIP**, unzip in **Files**, or
   - **AirDrop** the `CrayonPiano.swiftpm` folder from a Mac, or
   - Put it in **iCloud Drive** and open from Files.
3. Tap `CrayonPiano.swiftpm` → it opens in Swift Playgrounds → press **▶ Run**.
4. Allow the microphone the first time you tap **Écouter / Start listening**.

Swift Playgrounds builds a real app on the iPad — no developer account or provisioning needed
to run it there.

### Option C — native app on **iPhone 15 Pro** or iPad A16 via Xcode
Swift Playgrounds does **not** run on iPhone. On this Mac:

1. Enable **Developer Mode** on the phone/iPad, plug in USB, Trust.
2. Open `ios/CrayonPiano.swiftpm` in **Xcode 27**.
3. Signing → Personal Team. Destination → **iPhone 15 Pro** or **iPad A16**.
4. Run ▶. Trust the developer certificate on the device if prompted.

Mac destination **My Mac (Designed for iPad)** also works from the same package.

---

## What it does

Same crayon map as [`web/keyboard.html`](../web/keyboard.html):

- **Tap / hold keys** (multi-touch) — plays a tone and lights the macOS crayon for that pitch class.
- **Écouter / Start listening** — device mic → Accelerate FFT peak-picker → keys light up.
- **Rejouer / Replay demo** — built-in 8 s synth phrase (no WAV, no HTTP). Check **Entendre /
  Unmute** to hear it.
- **Waveform track** — DAW-style lane (Logic Pro / GarageBand feel): a fixed playhead with the
  waveform scrolling right→left as it plays. Drag the lane to scrub.
- Track chips (multi-select, color-coded) and stacked waveform lanes — one lane per density cluster.
- One typing board with a **US | Canadien français** picker. Switching remaps glyphs, ISO geometry, and hardware keys at once. Each character key is a crayon note (**Z = Do3**, **D = Do4**, **Q = La4**) and lights the matching 88-key. Ten-finger gate unless extras are well clustered.
- Auto-accord, day/light/dark/night/stealth + Auto ambient scenes, chords.
- Full 88-key piano (A0–C8) spanning the window (horizontal scroll only if white keys would drop below ~28pt).
- Log-frequency clustered spectrum (A0–C8, dBFS, 440 Hz tick) with unbounded regrouped sources.

## Files (`CrayonPiano.swiftpm/`)

| File | Role |
|------|------|
| `Package.swift` | Swift Playgrounds app manifest (`.iOSApplication`) |
| `CrayonPianoApp.swift` | `@main` app entry |
| `CrayonTheme.swift` | macOS Crayons.clr palette + day/light/dark/night/stealth |
| `SpectrumPlotView.swift` | log-frequency clustered spectrum (A0–C8) |
| `PitchMath.swift` | MIDI ↔ Hz, A0–C8 (88 keys) |
| `SpectrumAnalyzer.swift` | vDSP FFT + the web peak-picker |
| `PianoSession.swift` | mic, tap tones, built-in demo, waveform peaks |
| `PianoKeyboardView.swift` | multi-touch keyboard |
| `WaveformTrackView.swift` | scrolling DAW-style waveform timeline |
| `DualKeyboard.swift` / `DualKeyboardView.swift` | US / CSA typing board + hardware keys |
| `KeyboardLayout.swift` | held / need / hit + score store |
| `ContentView.swift` | iPhone 15 Pro / iPad A16 layout |
