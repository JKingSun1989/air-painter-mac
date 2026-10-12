"""All configuration constants for the AI Virtual Painter."""

import os

CAM_INDEX = 0
FRAME_W, FRAME_H = 1100, 720
TOPBAR_H = 100
SIDEBAR_W = 120
HOVER_TIME_TO_SELECT = 0.6

SMOOTHING_ALPHA = 0.45          # lower = smoother but laggier
MIN_BRUSH, MAX_BRUSH = 3, 55
PINCH_MIN_PX, PINCH_MAX_PX = 20, 220

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

PALETTE = [
    {"name": "Red", "bgr": (0, 0, 255)},
    {"name": "Green", "bgr": (0, 200, 0)},
    {"name": "Blue", "bgr": (255, 0, 0)},
    {"name": "Yellow", "bgr": (0, 220, 220)},
    {"name": "Purple", "bgr": (200, 0, 150)},
    {"name": "Cyan", "bgr": (220, 200, 0)},
    {"name": "White", "bgr": (255, 255, 255)},
]
CLEAR_INDEX = len(PALETTE)  # extra box at the bottom of the sidebar

MODE_COLORS = {
    "Draw": (0, 200, 0),
    "Select": (255, 160, 0),
    "Resize": (0, 210, 255),
    "Erase": (0, 0, 220),
    "Idle": (120, 120, 120),
}

HAND_DEFAULT_COLOR_IDX = {"Left": 0, "Right": 1}  # Red for left, Green for right

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paintings")

THUMB_TIP = 4
TIP_IDS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
PIP_IDS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]
