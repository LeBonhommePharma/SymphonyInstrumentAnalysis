# Piano-crayon for iPad / iPhone / Mac

Native SwiftUI app — **no local server, no ports**. Tap keys, listen through the mic,
or replay the built-in demo on the DAW-style scrolling waveform.

It ships as a **Swift Playgrounds App package** (`CrayonPiano.swiftpm`), so you can build and
run it **directly on iPadOS 27** (no Mac needed) and on **macOS 27** (Xcode or Swift
Playgrounds). Requires iOS/iPadOS 17+.

---

## Test it now

### Option A — instant, any device, zero build (web)
Open `web/keyboard.html` in **Safari** on macOS 27 or iPadOS 27 (double-tap the file / open from
the Files app). Tap keys, tap the crayon swatches, hit **Rejouer** for the demo, drag the
waveform lane to scrub. Everything works offline.

- macOS Safari: **live mic works** too (click Écouter, allow the mic).
- iPadOS Safari from a `file://` page: tap-to-play, replay and the waveform work, but Safari
  blocks the mic on `file://` — use Option B for live mic on iPad.

### Option B — run the native app on iPadOS 27 (no Mac)
1. Install **Swift Playgrounds** from the App Store (free).
2. Get `ios/CrayonPiano.swiftpm` onto the iPad. Any of:
   - On GitHub tap **Code ▸ Download ZIP**, unzip in **Files**, or
   - **AirDrop** the `CrayonPiano.swiftpm` folder from a Mac, or
   - Put it in **iCloud Drive** and open from Files.
3. Tap `CrayonPiano.swiftpm` → it opens in Swift Playgrounds → press **▶ Run**.
4. Allow the microphone the first time you tap **Écouter / Start listening**.

Swift Playgrounds builds a real app on the iPad — no developer account or provisioning needed
to run it there.

### Option C — run the native app on macOS 27
Double-click `ios/CrayonPiano.swiftpm`. It opens in **Xcode 15+** (or **Swift Playgrounds for
Mac**). Then either:

- Press **▶** with destination **My Mac (Designed for iPad)** to run it on the Mac, or
- Pick an **iOS Simulator** (e.g. iPhone 16 / iPad Pro), or
- Select a plugged-in iPhone/iPad and Run (set your Team under Signing if prompted — free
  personal team is fine).

---

## What it does

Same crayon map as [`web/keyboard.html`](../web/keyboard.html):

- **Tap / hold keys** (multi-touch) — plays a tone and lights the macOS crayon for that pitch class.
- **Écouter / Start listening** — device mic → Accelerate FFT peak-picker → keys light up.
- **Rejouer / Replay demo** — built-in 8 s synth phrase (no WAV, no HTTP). Check **Entendre /
  Unmute** to hear it.
- **Waveform track** — DAW-style lane (Logic Pro / GarageBand feel): a fixed playhead with the
  waveform scrolling right→left as it plays. Drag the lane to scrub.
- Track chips, auto-accord, day/light/dark/night/stealth + Auto ambient scenes, chords.
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
| `ContentView.swift` | iPhone / iPad layout |
