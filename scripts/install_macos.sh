#!/usr/bin/env bash
# macOS install for Ghostty TUI + local verification.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v brew >/dev/null 2>&1; then
  echo "Install Homebrew first: https://brew.sh" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  brew install ffmpeg
fi
if ! command -v python3 >/dev/null 2>&1; then
  brew install python
fi

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

export MPLBACKEND=Agg
.venv/bin/python scripts/density_cluster.py
.venv/bin/python scripts/keyboard_layout.py
.venv/bin/python scripts/crayon_piano.py --self-test
.venv/bin/python - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts")))
import smoke_test as st
st.check_ffmpeg()
st.check_spectrum_scale()
st.check_public_site()
st.check_discrimination()
st.check_keyboard_layout()
st.check_crayon_piano()
print("install_macos: OK")
PY

echo
echo "Ghostty TUI:  bash scripts/run_tui.sh"
echo "Web piano:    open web/keyboard.html"
echo "Public hub:   https://thebonhomme.com/SymphonyInstrumentAnalysis/"
echo "Device steps: docs/INSTALL_AND_TEST.md"
