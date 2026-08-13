# Symphony Instrument Analysis

Standalone mic-capture + spectral analysis project (**not** related to FlexAIDdS).

Records from the best available macOS mic, denoises, then estimates:

- likely instrument families (vocals/lyrics de-emphasized)
- note sequences with frequencies in Hz

## Public live listen (phone on 5G, any network)

The tutorial is a static HTTPS page. Open it **on the device that is making sound**. It uses that device’s microphone. It does not play music. `127.0.0.1` and LAN IPs are not reachable on cellular.

**Canonical URL** after GitHub Pages is switched on for this repo (Settings → Pages → Source: **GitHub Actions**). Project Pages then appear under the existing `thebonhomme.com` user-site domain. Do **not** attach a CNAME of `thebonhomme.com` to this repo, or the homepage would be stolen:

- Hub: https://thebonhomme.com/SymphonyInstrumentAnalysis/
- Live listen: https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/
- ELI5: https://thebonhomme.com/SymphonyInstrumentAnalysis/how-to.html

One-click: [Pages settings](https://github.com/LeBonhommePharma/SymphonyInstrumentAnalysis/settings/pages). The deploy workflow is `.github/workflows/pages.yml`. `GITHUB_TOKEN` cannot create the Pages site from this agent; that toggle is the missing step.

Fastest 5G path that already has HTTPS: copy this `docs/` folder to `symphony/` on `lebonhommepharma.github.io` (this bot cannot push that repo). Then open https://thebonhomme.com/symphony/tutorial/ on the phone.

On an iPhone, tap **Listen with the mic** and allow Microphone. Tab/window capture is a desktop feature.

Local-only fallback (this computer, not 5G):

```bash
python3 scripts/serve_tutorial.py
```

## How-to (ELI5)

Sound is air wiggling. We count the wiggles per second (**Hz**), then name the instruments and notes.

![Figure 1. Play a song, the mic listens, look at the wiggles, name the sounds.](docs/howto-eli5.png)

Full walkthrough: [docs/HOW_TO_ELI5.md](docs/HOW_TO_ELI5.md) or [docs/how-to.html](docs/how-to.html). Live page: [docs/tutorial/index.html](docs/tutorial/index.html).

### Homepage card (layout-safe)

This bot cannot push `lebonhommepharma.github.io`. Add **one object** to the existing `footerLinks` and `products` arrays in the bundled `index.html` (same card grid, no header/nav/CSS changes). Point at the Pages URL above, or at `/symphony/` if you copy `docs/` into that folder on the homepage repo.

`footerLinks` (after Shannon):

```js
{ name: "Symphony", role: "live listen", glyph: "Hz", c: "var(--cyan)", href: "https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/", target: "", rel: "" },
```

`products` (after Shannon):

```js
{ name: "Symphony", kind: "Instrument Analysis", glyph: "Hz", c: "var(--cyan)", href: "https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/", cta: "Live listen", desc: "Silent live-listen: see the Hertz of whatever this device is already playing. No background music." },
```

### GoDaddy DNS (`thebonhomme.com`)

Registrar **and** nameservers are GoDaddy (`ns41.domaincontrol.com` / `ns42.domaincontrol.com`). Apex **A** records already match GitHub Pages; `https://thebonhomme.com` works. This agent has no GoDaddy API key, so these still need to be applied in the GoDaddy DNS panel:

Keep:

| Type | Name | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| existing TXT / MX / SPF / Apple / Microsoft 365 | | do not delete |

Change / add:

| Type | Name | Value |
| --- | --- | --- |
| CNAME | `www` | `lebonhommepharma.github.io` (not `thebonhomme.com`) |
| AAAA | `@` | `2606:50c0:8000::153` |
| AAAA | `@` | `2606:50c0:8001::153` |
| AAAA | `@` | `2606:50c0:8002::153` |
| AAAA | `@` | `2606:50c0:8003::153` |

Then in the homepage repo Pages settings, add `www.thebonhomme.com` as a custom domain so GitHub can issue a cert that includes `www`. Today `https://www.thebonhomme.com` presents `*.github.io` (name mismatch). HTTP `www` already 301s to the working apex.

Do **not** add a `_github-pages-challenge-…` TXT until GitHub shows the token (Pages → Custom domain → Verify). Domain state is currently `unverified`.

If GitHub Pages is not on for this repo yet: **Settings → Pages → Source: GitHub Actions** ([open](https://github.com/LeBonhommePharma/SymphonyInstrumentAnalysis/settings/pages)). The workflow is `.github/workflows/pages.yml`. Actions cannot create the site until that source is selected.

## Setup

Debian/Ubuntu (install OS packages first; `python3-venv` matches the default `python3`):

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cloud / repeatable install:

```bash
bash .cursor/install.sh
```

Verify the analysis path (works without a microphone):

```bash
python3 scripts/smoke_test.py
```

## Usage

```bash
# list mics
python3 scripts/list_mics.py

# probe which mic has best signal / least noise
python3 scripts/probe_mics.py

# record (auto-picks best mic; play music while it runs)
python3 scripts/record_mic.py --seconds 90

# analyze (ignores voices/lyrics by default)
python3 scripts/analyze_instruments.py captures/<file>.wav
```

Outputs land in `analysis_out/` (Markdown + JSON). Raw WAVs stay local in `captures/` (gitignored).

`list_mics.py` / `probe_mics.py` / `record_mic.py` use macOS AVFoundation. Without a capture device they exit 1 with `No AVFoundation audio devices found.` On Linux, use `smoke_test.py` or feed a 16-bit PCM WAV to `analyze_instruments.py`.
