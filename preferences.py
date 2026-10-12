"""Validated, local, atomic user preferences. Never store camera images."""
import json
import math
from pathlib import Path
import tempfile
import os

from config import SMOOTHING_ALPHA, PALETTE, MIN_BRUSH, MAX_BRUSH
from painter_core import TOOLS

DEFAULTS = {"thickness": 8, "smoothing": SMOOTHING_ALPHA, "color_idx": 0,
            "tool": "pen", "input_mode": "hand", "show_skeleton": True,
            "export_background": "black"}
DEFAULT_PATH = Path(__file__).resolve().parent / "settings.json"


def validate_preferences(data):
    values = DEFAULTS.copy()
    if not isinstance(data, dict):
        return values
    width = data.get("thickness")
    if type(width) is int and MIN_BRUSH <= width <= MAX_BRUSH:
        values["thickness"] = width
    alpha = data.get("smoothing")
    if type(alpha) in (int, float) and 0 < alpha <= 1 and math.isfinite(alpha):
        values["smoothing"] = float(alpha)
    color = data.get("color_idx")
    if type(color) is int and 0 <= color < len(PALETTE):
        values["color_idx"] = color
    for key, options in (("tool", TOOLS), ("input_mode", ("hand", "mouse")),
                         ("export_background", ("black", "white"))):
        if data.get(key) in options:
            values[key] = data[key]
    if type(data.get("show_skeleton")) is bool:
        values["show_skeleton"] = data["show_skeleton"]
    return values


def load_preferences(path=DEFAULT_PATH):
    try:
        return validate_preferences(json.loads(Path(path).read_text()))
    except (OSError, ValueError, UnicodeError):
        return DEFAULTS.copy()


def save_preferences(data, path=DEFAULT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                          prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(validate_preferences(data), stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
