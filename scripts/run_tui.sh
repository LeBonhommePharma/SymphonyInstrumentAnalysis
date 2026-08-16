#!/usr/bin/env bash
# Launch the crayon-piano TUI in Ghostty (or any truecolor terminal).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  echo "Run bash scripts/install_macos.sh first." >&2
  exit 1
fi

export MPLBACKEND="${MPLBACKEND:-Agg}"
export COLORTERM="${COLORTERM:-truecolor}"
# Ghostty reports TERM=xterm-ghostty; Textual handles it. Keep a sane fallback.
if [ -z "${TERM:-}" ] || [ "$TERM" = "dumb" ]; then
  export TERM=xterm-256color
fi

exec .venv/bin/python scripts/crayon_piano.py "$@"
