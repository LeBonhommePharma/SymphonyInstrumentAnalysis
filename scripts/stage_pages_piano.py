#!/usr/bin/env python3
"""Copy the crayon piano into docs/piano for GitHub Pages.

The public site publishes docs/ from main. The US / Canadian French
layout picker lives in web/; this script stages that same page under /piano/.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_HTML = ROOT / "web" / "keyboard.html"
SRC_JS = ROOT / "web" / "dual_keyboard.js"
SRC_DSP = ROOT / "web" / "crayon_dsp.js"
OUT = ROOT / "docs" / "piano"
CANONICAL = "https://thebonhomme.com/SymphonyInstrumentAnalysis/piano/"

CRUMB = """  <p class="pages-crumb">
    <a href="../">Symphony</a>
    ·
    <a href="../tutorial/">Live listen</a>
    ·
    <a href="../how-to.html">ELI5</a>
  </p>
"""

# Structural breadcrumb: JetBrains Mono per the canonical spec, Mint (ΔH,
# brand primary) on hover the way docs/flexaid.css paints links, and the
# 12px floor cleared explicitly (0.78rem = 12.48px). This block ships into
# the published page, so it is design-system surface like any other and is
# covered by scripts/check_palette.py.
CRUMB_CSS = """
    .pages-crumb {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 10px;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      font-weight: 650;
      letter-spacing: var(--tracking-label);
      color: var(--muted);
    }
    .pages-crumb a {
      color: var(--muted);
      text-decoration: none;
      border-radius: var(--r-xs);
      transition: color var(--dt) var(--ease);
    }
    .pages-crumb a:hover,
    .pages-crumb a:focus-visible { color: var(--mint); }
"""

HEAD_INJECT = f"""  <link rel="canonical" href="{CANONICAL}">
  <meta name="description" content="Pick US ANSI or Canadian French CSA. One board remaps instantly. Ten fingers; extras only if well clustered.">
"""


def stage() -> None:
    if not SRC_HTML.is_file() or not SRC_JS.is_file() or not SRC_DSP.is_file():
        raise SystemExit("web/keyboard.html, dual_keyboard.js, and crayon_dsp.js are required")
    html = SRC_HTML.read_text(encoding="utf-8")
    if "</style>" not in html or "<body>" not in html:
        raise SystemExit("keyboard.html is missing expected markers")
    if "pages-crumb" not in html:
        html = html.replace("</style>", CRUMB_CSS + "  </style>", 1)
        html = html.replace("</head>", HEAD_INJECT + "</head>", 1)
        html = html.replace("<body>\n", "<body>\n" + CRUMB, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "dual_keyboard.js").write_text(SRC_JS.read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "crayon_dsp.js").write_text(SRC_DSP.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"staged {OUT / 'index.html'}, dual_keyboard.js, crayon_dsp.js")


def main() -> None:
    stage()


if __name__ == "__main__":
    main()
