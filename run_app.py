"""Apply the same environment diagnostics to Finder and terminal launches."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
result = subprocess.run([sys.executable, str(ROOT / "doctor.py")])
if result.returncode:
    raise SystemExit(result.returncode)
command = [sys.executable, str(ROOT / "ai_virtual_painter.py"), *sys.argv[1:]]
if sys.platform == "win32":
    # Windows execv does not quote arguments containing spaces and detaches
    # the app's exit status from the calling PowerShell script.
    raise SystemExit(subprocess.call(command))
os.execv(sys.executable, command)
