#!/usr/bin/env python3
"""Copy the crayon piano into docs/piano for GitHub Pages.

The public site publishes docs/ from main. The dual US + Canadian French
boards live in web/; this script stages that same page under /piano/.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_HTML = ROOT / "web" / "keyboard.html"
SRC_JS = ROOT / "web" / "dual_keyboard.js"
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

CRUMB_CSS = """
    .pages-crumb {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 10px;
      font-size: 0.78rem;
      font-weight: 650;
      color: var(--muted);
    }
    .pages-crumb a { color: var(--muted); text-decoration: none; }
    .pages-crumb a:hover { color: var(--ink); }
"""

HEAD_INJECT = f"""  <link rel="canonical" href="{CANONICAL}">
  <meta name="description" content="US ANSI and Canadian French CSA keyboards. Ten fingers; extras only if well clustered.">
"""


def stage() -> None:
    if not SRC_HTML.is_file() or not SRC_JS.is_file():
        raise SystemExit("web/keyboard.html and web/dual_keyboard.js are required")
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
    print(f"staged {OUT / 'index.html'} and {OUT / 'dual_keyboard.js'}")


def main() -> None:
    stage()


if __name__ == "__main__":
    main()
