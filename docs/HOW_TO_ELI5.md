# How this works (explained like you are 5)

Sound is air wiggling. Slow wiggles are low notes. Fast wiggles are high notes. We count the wiggles in one second. That count is **Hertz (Hz)**.

A piano **A** is about **440 Hz**. A low bass note can be near **110 Hz**.

## 60-second live tutorial (nothing plays in the background)

Open this **on the device that is already making sound**, including a phone on 5G:

- https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/

The page stays silent. It only draws **whatever this device is making now** — speaker, piano, room, headphone bleed, or Now Playing if that sound reaches the mic. Soft auto-gain lifts quiet rooms. **Logic-style tracks** come from **density clustering** (lane count follows the sound; not a fixed parameter). If there is no melody (voices, noise), it still draws that live signal. It never invents a tune.

Public pages are **English and French** first (EN / FR toggle, or `?lang=en` / `?lang=fr`).

Local-only fallback:

```bash
python3 scripts/serve_tutorial.py
```

Then tap **Listen**. It asks for the microphone first. If nothing is around, live listen falls through to what this computer is playing (tab/window audio). On a phone, play it out loud — the web cannot read Apple Now Playing.

[Open the live tutorial](tutorial/index.html)

<figure>
  <img src="howto-eli5.png" alt="Four-step how-to: play a song, the mic listens, look at the wiggles, then name the sounds in Hertz." width="1600">
  <figcaption>Figure 1. The grown-up job in four steps. The live tutorial draws those same ideas from the device’s real sound. Vector: <a href="howto-eli5.svg">howto-eli5.svg</a>.</figcaption>
</figure>

### Why a kid should care (the useful part)

A song is a sandwich, not a blob:

- **Boom** on the bottom = left hand / bass
- **Tune** in the middle = the part you can hum
- **Sparkle** on top = extra shine

The tool writes that recipe in Hertz. Then you can practice **one layer at a time** instead of drowning in the whole song.

### Why doing it live is hard

Naming notes *while* the song is still happening is like reading a page someone is still flipping:

- Many notes stack (chords)
- Piano keys ring extra high copies called **overtones**
- The computer needs a little bite of sound before it can guess (this analyzer looks in chunks, about a quarter of a second)

So the grown-up tool **records, then looks**. Tiny delay, better answer. The live page shows you the messy moving picture so the delay makes sense.

### Piano superpower

If the loudest wiggle is **440 Hz**, that is the **A** key. Find it. Play it. Match it.

That is ear training: hearing a map (bass / tune / sparkle + note names), not a blur. Left hand lives in slower wiggles. Right hand lives in faster ones.

## The four grown-up steps

1. **Play a song** (or a piano) on the device.
2. **The mic listens** — we pick the best ear and record.
3. **Look at the wiggles** — wash out hiss, turn singing down.
4. **Name the sounds** — instrument families and notes with frequencies in Hz.

```bash
python3 scripts/list_mics.py
python3 scripts/probe_mics.py
python3 scripts/record_mic.py --seconds 90
python3 scripts/analyze_instruments.py captures/<file>.wav
```

Reports land in `analysis_out/` (Markdown + JSON). The raw recording stays in `captures/`.

## No microphone on this machine?

```bash
python3 scripts/smoke_test.py
```

The smoke test makes a fake song (E2, A4, C5) and checks that the analyzer can name those notes. Use the live tutorial on a real device when you want to see *your* sound.

## What the report is saying

| Kid words | Grown-up words | Typical Hz |
| --- | --- | --- |
| Boom / rumble | Bass foundation | 40–250 |
| Warm body | Low-mid | 250–500 |
| Tune you can hum | Mid melody | 500–2000 |
| Sparkle / air | High color | 2000–5000 |

Example: **A4 ≈ 440 Hz** means “that pitch wiggled 440 times in one second.”
