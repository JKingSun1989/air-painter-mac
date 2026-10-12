"""Pure geometry/gesture-classification helpers. No OpenCV drawing here —
these are the functions most worth unit-testing, since they take plain
data in and return plain data out (see tests/test_hand_utils.py)."""

from typing import Dict, List, Tuple

import numpy as np

from config import TIP_IDS, PIP_IDS

Point = Tuple[int, int]


def dist(a: Point, b: Point) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def fingers_up(landmarks_px: List[Point]) -> Dict[str, bool]:
    up = {}
    for name, tip_id in TIP_IDS.items():
        pip_id = PIP_IDS[name]
        up[name] = landmarks_px[tip_id][1] < landmarks_px[pip_id][1]
    return up


def thumb_extended(landmarks_px: List[Point]) -> bool:
    wrist = landmarks_px[0]
    middle_mcp = landmarks_px[9]
    pinky_mcp = landmarks_px[17]
    thumb_tip = landmarks_px[4]
    hand_scale = max(dist(wrist, middle_mcp), 1.0)
    return dist(thumb_tip, pinky_mcp) > 0.85 * hand_scale


def classify_gesture(up: Dict[str, bool], thumb_up: bool) -> str:
    idx, mid, ring, pinky = up["index"], up["middle"], up["ring"], up["pinky"]
    count_4 = sum([idx, mid, ring, pinky])

    # An extended thumb must not prevent ordinary index-finger drawing.
    if idx and not mid and not ring and not pinky:
        return "Draw"
    if idx and mid and not ring and not pinky:
        return "Select"
    if count_4 >= 4:
        return "Idle"  # open palm lifts the pen; never unexpectedly erase
    return "Idle"
