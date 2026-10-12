#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export PIP_CACHE_DIR="$PWD/.cache/pip"
mkdir -p "$MPLCONFIGDIR" "$PIP_CACHE_DIR"
if [ ! -x .venv/bin/python ] || [ ! -f .venv/.painter-ready ]; then
    ./setup.sh
fi
if [ "${1:-}" = "--foreground" ]; then
    shift
    exec .venv/bin/python run_app.py "$@"
fi
if [ ! -x "Air Painter.app/Contents/MacOS/AirPainter" ]; then
    ./scripts/build-app.sh
fi
exec open "$PWD/Air Painter.app" --args "$@"
