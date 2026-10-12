#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export PIP_CACHE_DIR="$PWD/.cache/pip"
mkdir -p "$MPLCONFIGDIR" "$PIP_CACHE_DIR"
if [ ! -x .venv/bin/python ]; then
    painter_python=""
    for candidate in python3.11 python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.12 "${HOME}/.local/bin/python3.12" python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)' 2>/dev/null; then
            painter_python="$candidate"
            break
        fi
    done
    if [ -z "$painter_python" ]; then
        echo '未找到兼容的 Python 3.11/3.12。请安装 Python 3.11 后重试（如 brew install python@3.11）。'
        exit 1
    fi
    "$painter_python" -m venv .venv
fi
.venv/bin/python -c 'import sys; print("使用 Python", sys.version.split()[0]); sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)'
if [ -f requirements.lock.txt ]; then
    .venv/bin/python -m pip install --disable-pip-version-check -r requirements.lock.txt
else
    .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
fi
if ! .venv/bin/python -c 'from pathlib import Path; import hashlib; from doctor import MODEL_SHA256; p=Path("hand_landmarker.task"); raise SystemExit(0 if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==MODEL_SHA256 else 1)'; then
    curl -fL --connect-timeout 15 --max-time 120 -o hand_landmarker.task.download https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
    .venv/bin/python -c 'from pathlib import Path; import hashlib; from doctor import MODEL_SHA256; p=Path("hand_landmarker.task.download"); assert hashlib.sha256(p.read_bytes()).hexdigest()==MODEL_SHA256, "模型校验失败"; p.replace("hand_landmarker.task")'
fi
.venv/bin/python doctor.py
./scripts/build-app.sh
touch .venv/.painter-ready
echo '安装完成，运行 ./start.sh。'
