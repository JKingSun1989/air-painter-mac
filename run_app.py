"""Apply the same environment diagnostics to Finder and terminal launches."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
result = subprocess.run([sys.executable, str(ROOT / "doctor.py")])
if result.returncode:
    raise SystemExit(result.returncode)
os.execv(sys.executable, [sys.executable, str(ROOT / "ai_virtual_painter.py"), *sys.argv[1:]])
