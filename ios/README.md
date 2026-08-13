# Piano-crayon for iOS

Native SwiftUI app — **no local server, no ports**. Open the Xcode project, run on an iPhone or iPad, tap keys, listen through the mic, or replay the built-in demo.

## Open

```bash
open ios/CrayonPiano/CrayonPiano.xcodeproj
```

1. Select your Development Team under the **CrayonPiano** target → Signing & Capabilities.
2. Plug in an iPhone (or pick a simulator) and press Run.
3. Allow the microphone when prompted if you want live listening.

Requires **iOS 17+** / Xcode 15+. Bundle id: `com.lebonhommepharma.crayonpiano`.

## What it does

Same crayon map as [`web/keyboard.html`](../../web/keyboard.html):

- **Tap / hold keys** (multi-touch) — plays a tone and lights the macOS crayon for that pitch class.
- **Écouter / Start listening** — device mic → Accelerate FFT peak-picker → keys light up.
- **Rejouer / Replay demo** — built-in 8 s synth phrase (no WAV file, no HTTP). Check **Entendre / Unmute** to hear it.
- **Waveform track** — the replay timeline is a DAW-style lane (like Logic Pro / GarageBand): a fixed playhead with the waveform scrolling right→left as it plays. Drag the lane to scrub.
- Track chips, auto-accord, stealth/studio scene, sensitivity, chords — same behaviour as the web piano.

Live mic on iPhone **cannot** work from a `file://` web page (Safari requires a secure context). That is why this app exists: AVAudioEngine + `NSMicrophoneUsageDescription`, zero network.

## Files

| File | Role |
|------|------|
| `CrayonTheme.swift` | macOS Crayons.clr palette + stealth/studio |
| `PitchMath.swift` | MIDI ↔ Hz, C2–C7 |
| `SpectrumAnalyzer.swift` | vDSP FFT + the web peak-picker |
| `PianoSession.swift` | mic, tap tones, built-in demo, waveform peaks |
| `PianoKeyboardView.swift` | multi-touch keyboard |
| `WaveformTrackView.swift` | scrolling DAW-style waveform timeline |
| `ContentView.swift` | iPhone / iPad layout |
