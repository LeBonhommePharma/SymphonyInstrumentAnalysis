#!/usr/bin/env python3
"""Serve the silent live-listen tutorial on this computer only.

Phones on 5G cannot reach 127.0.0.1 or a LAN IP. Use the GitHub Pages URL:
https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/

Serves the whole docs/ folder so the shared English/French i18n file loads.
"""
from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TUTORIAL = DOCS / "tutorial"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print("[tutorial]", fmt % args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    if not (TUTORIAL / "index.html").is_file():
        raise SystemExit(f"missing {TUTORIAL / 'index.html'}")
    os.chdir(DOCS)
    url = f"http://127.0.0.1:{args.port}/tutorial/"
    print(f"Silent live-listen tutorial (this computer only): {url}")
    print("This page does not play music. It only draws what the device is already playing.")
    print("Languages: English and French (EN / FR). One track per instrument (max 6).")
    print("For a phone on 5G use https://thebonhomme.com/SymphonyInstrumentAnalysis/tutorial/")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        if not args.no_open:
            webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
