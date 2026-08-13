# How this works (explained like you are 5)

Sound is air wiggling. Slow wiggles are low notes. Fast wiggles are high notes. We count the wiggles in one second. That count is **Hertz (Hz)**.

A piano **A** is about **440 Hz**. A low bass note can be near **110 Hz**.

<figure>
  <img src="howto-eli5.png" alt="Four-step how-to: play a song, the mic listens, look at the wiggles, then name the sounds in Hertz." width="1600">
  <figcaption>Figure 1. The whole job in four steps. Vector version: <a href="howto-eli5.svg">howto-eli5.svg</a>.</figcaption>
</figure>

## The four steps

1. **Play a song.** Music makes the air wiggle. Keep it playing.
2. **The mic listens.** We list the mics, pick the best “ear,” and record.
3. **Look at the wiggles.** We wash out hiss, turn singing down, and look at slow vs fast wiggles.
4. **Name the sounds.** You get instrument families (bass, melody, sparkle) and notes with frequencies in Hz.

## Grown-up buttons for those steps

```bash
python3 scripts/list_mics.py
python3 scripts/probe_mics.py
python3 scripts/record_mic.py --seconds 90
python3 scripts/analyze_instruments.py captures/<file>.wav
```

Reports land in `analysis_out/` (Markdown + JSON). The raw recording stays in `captures/`.

## No microphone? Still try it

On Linux or a cloud machine there is usually no macOS mic. That is OK:

```bash
python3 scripts/smoke_test.py
```

The smoke test makes a fake song (E2, A4, C5) and checks that the analyzer can name those notes.

## What the report is saying

| Kid words | Grown-up words | Typical Hz |
| --- | --- | --- |
| Boom / rumble | Bass foundation | 40–250 |
| Warm body | Low-mid | 250–500 |
| Tune you can hum | Mid melody | 500–2000 |
| Sparkle / air | High color | 2000–5000 |

Example: **A4 ≈ 440 Hz** means “that pitch wiggled 440 times in one second.”
