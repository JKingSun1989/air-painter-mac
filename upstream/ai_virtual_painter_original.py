"""
=========================================================================
  AI VIRTUAL PAINTER 
=========================================================================

KEYBOARD:
  c        -> clear canvas
  g        -> toggle glow/particle effects
  h        -> toggle hand-skeleton overlay
  s        -> save PNG
  q / ESC  -> quit

=========================================================================
SETUP (one-time):
  pip install opencv-python mediapipe numpy

  Download the hand-tracking model file once, into the SAME folder as
  this script:
      curl -L -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

  (No curl on Windows? Paste that URL into your browser and save the
  file as "hand_landmarker.task" next to this script.)

  Then run:
      python ai_virtual_painter.py
=========================================================================
"""

import os
import sys
import time
import random

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# ---------------------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------------------
CAM_INDEX = 0
FRAME_W, FRAME_H = 1100, 720
TOPBAR_H = 46
SIDEBAR_W = 120
HOVER_TIME_TO_SELECT = 0.6

SMOOTHING_ALPHA = 0.45          # lower = smoother but laggier
MIN_BRUSH, MAX_BRUSH = 3, 55
PINCH_MIN_PX, PINCH_MAX_PX = 20, 220

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")

PALETTE = [
    {"name": "Red",    "bgr": (0, 0, 255)},
    {"name": "Green",  "bgr": (0, 200, 0)},
    {"name": "Blue",   "bgr": (255, 0, 0)},
    {"name": "Yellow", "bgr": (0, 220, 220)},
    {"name": "Purple", "bgr": (200, 0, 150)},
    {"name": "Cyan",   "bgr": (220, 200, 0)},
    {"name": "White",  "bgr": (255, 255, 255)},
]
CLEAR_INDEX = len(PALETTE)  # extra box at the bottom of the sidebar

MODE_COLORS = {
    "Draw":   (0, 200, 0),
    "Select": (255, 160, 0),
    "Resize": (0, 210, 255),
    "Erase":  (0, 0, 220),
    "Idle":   (120, 120, 120),
}

HAND_DEFAULT_COLOR_IDX = {"Left": 0, "Right": 1}  # Red for left, Green for right

SAVE_DIR = os.path.join(os.getcwd(), "paintings")
os.makedirs(SAVE_DIR, exist_ok=True)

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


# ---------------------------------------------------------------------
# 2. MODEL FILE CHECK
# ---------------------------------------------------------------------
def ensure_model_present():
    if os.path.exists(MODEL_PATH):
        return
    print("=" * 70)
    print("Hand-tracking model file not found:")
    print(f"  {MODEL_PATH}")
    print()
    print("Download it once (about 8 MB) and place it next to this script:")
    print(f"  {MODEL_URL}")
    print()
    print("Or run this in your terminal (same folder as this script):")
    print(f'  curl -L -o hand_landmarker.task "{MODEL_URL}"')
    print("=" * 70)
    sys.exit(1)


# ---------------------------------------------------------------------
# 3. PARTICLE SYSTEM (just for visual fun)
# ---------------------------------------------------------------------
class Particles:
    def __init__(self, max_particles=180):
        self.items = []
        self.max_particles = max_particles

    def spawn(self, pos, color):
        if len(self.items) >= self.max_particles:
            return
        for _ in range(2):
            jitter = (random.randint(-6, 6), random.randint(-6, 6))
            self.items.append({
                "pos": (pos[0] + jitter[0], pos[1] + jitter[1]),
                "color": color,
                "life": random.randint(10, 18),
                "max_life": 18,
                "radius": random.randint(2, 4),
            })

    def update_and_draw(self, frame):
        alive = []
        for p in self.items:
            p["life"] -= 1
            if p["life"] > 0:
                fade = p["life"] / p["max_life"]
                overlay = frame.copy()
                cv2.circle(overlay, p["pos"], p["radius"], p["color"], -1, cv2.LINE_AA)
                cv2.addWeighted(overlay, fade * 0.6, frame, 1 - fade * 0.6, 0, dst=frame)
                alive.append(p)
        self.items = alive


# ---------------------------------------------------------------------
# 4. UI DRAWING HELPERS
# ---------------------------------------------------------------------
def draw_topbar(frame, fps):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (FRAME_W, TOPBAR_H), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, dst=frame)
    cv2.putText(frame, "AI VIRTUAL PAINTER", (16, 30), cv2.FONT_HERSHEY_DUPLEX,
                0.62, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"FPS: {int(fps)}", (FRAME_W - 110, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, "1 finger=draw  2=pick color  pinch=resize  open palm=erase",
                (250, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 170, 170), 1, cv2.LINE_AA)


def sidebar_box_height():
    usable_h = FRAME_H - TOPBAR_H
    n_boxes = len(PALETTE) + 1  # +1 for the clear box
    return usable_h // n_boxes


def draw_sidebar(frame, hand_states):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, TOPBAR_H), (SIDEBAR_W, FRAME_H), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, dst=frame)

    box_h = sidebar_box_height()
    for i, item in enumerate(PALETTE):
        y1 = TOPBAR_H + i * box_h
        y2 = y1 + box_h - 6
        cv2.rectangle(frame, (10, y1 + 3), (SIDEBAR_W - 10, y2), item["bgr"], -1, cv2.LINE_AA)
        # highlight if either hand currently has this color selected
        for label, st in hand_states.items():
            if st["color_idx"] == i:
                ring_color = (255, 255, 255) if label == "Right" else (0, 255, 255)
                cv2.rectangle(frame, (10, y1 + 3), (SIDEBAR_W - 10, y2), ring_color, 2, cv2.LINE_AA)

    # clear box
    y1 = TOPBAR_H + len(PALETTE) * box_h
    y2 = y1 + box_h - 6
    cv2.rectangle(frame, (10, y1 + 3), (SIDEBAR_W - 10, y2), (40, 40, 40), -1, cv2.LINE_AA)
    cv2.putText(frame, "CLEAR", (18, (y1 + y2) // 2 + 5), cv2.FONT_HERSHEY_SIMPLEX,
                0.42, (255, 255, 255), 1, cv2.LINE_AA)

    return box_h


def sidebar_index_for_y(y, box_h):
    if y < TOPBAR_H:
        return -1
    idx = (y - TOPBAR_H) // box_h
    if 0 <= idx <= len(PALETTE):
        return int(idx)
    return -1


def draw_hand_badge(frame, label, pos, mode, color):
    text = f"{label}: {mode}"
    x, y = pos[0] - 40, max(pos[1] - 26, TOPBAR_H + 14)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x - 6, y - th - 6), (x + tw + 6, y + 6), (20, 20, 20), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x - 6, y - th - 6), (x + tw + 6, y + 6), color, 1, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_skeleton(frame, landmarks_px, tint):
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, landmarks_px[a], landmarks_px[b], tint, 2, cv2.LINE_AA)
    for pt in landmarks_px:
        cv2.circle(frame, pt, 3, (255, 255, 255), -1, cv2.LINE_AA)


# ---------------------------------------------------------------------
# 5. HAND GEOMETRY HELPERS
# ---------------------------------------------------------------------
def dist(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def fingers_up(landmarks_px):
    up = {}
    for name, tip_id in TIP_IDS.items():
        pip_id = PIP_IDS[name]
        up[name] = landmarks_px[tip_id][1] < landmarks_px[pip_id][1]
    return up


def thumb_extended(landmarks_px):
    wrist = landmarks_px[0]
    middle_mcp = landmarks_px[9]
    pinky_mcp = landmarks_px[17]
    thumb_tip = landmarks_px[4]
    hand_scale = max(dist(wrist, middle_mcp), 1.0)
    return dist(thumb_tip, pinky_mcp) > 0.85 * hand_scale


def classify_gesture(up, thumb_up):
    idx, mid, ring, pinky = up["index"], up["middle"], up["ring"], up["pinky"]
    count_4 = sum([idx, mid, ring, pinky])

    if thumb_up and idx and not mid and not ring and not pinky:
        return "Resize"
    if idx and not mid and not ring and not pinky:
        return "Draw"
    if idx and mid and not ring and not pinky:
        return "Select"
    if count_4 >= 4:
        return "Erase"
    return "Idle"


# ---------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------
def new_hand_state(label):
    idx = HAND_DEFAULT_COLOR_IDX.get(label, 0)
    return {
        "color_idx": idx,
        "color": PALETTE[idx]["bgr"],
        "thickness": 8,
        "prev_pt": None,
        "smooth_pt": None,
        "hover_idx": None,
        "hover_start": None,
        "mode": "Idle",
    }


def main():
    ensure_model_present()

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = mp_vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    if not cap.isOpened():
        print("Could not open the webcam. Try changing CAM_INDEX to 1.")
        return

    canvas = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    glow_layer = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)

    hand_states = {"Left": new_hand_state("Left"), "Right": new_hand_state("Right")}
    particles = Particles()

    show_skeleton = True
    show_fx = True
    prev_time = time.time()
    frame_timestamp_ms = 0

    print("AI Virtual Painter (advanced) started. Press 'q' to quit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (FRAME_W, FRAME_H))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            frame_timestamp_ms += 33
            result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

            active_labels = set()

            if result.hand_landmarks:
                for i, lms in enumerate(result.hand_landmarks):
                    label = "Right"
                    if result.handedness and len(result.handedness) > i:
                        label = result.handedness[i][0].category_name or "Right"
                    if label not in hand_states:
                        hand_states[label] = new_hand_state(label)
                    active_labels.add(label)
                    st = hand_states[label]

                    landmarks_px = [(int(lm.x * FRAME_W), int(lm.y * FRAME_H)) for lm in lms]

                    if show_skeleton:
                        tint = (0, 255, 170) if label == "Right" else (255, 200, 0)
                        draw_skeleton(frame, landmarks_px, tint)

                    up = fingers_up(landmarks_px)
                    t_up = thumb_extended(landmarks_px)
                    mode = classify_gesture(up, t_up)
                    st["mode"] = mode
                    index_pt = landmarks_px[TIP_IDS["index"]]

                    if mode == "Draw":
                        st["hover_idx"] = None
                        if index_pt[0] > SIDEBAR_W and index_pt[1] > TOPBAR_H:
                            # smooth the point (exponential moving average) for clean lines
                            if st["smooth_pt"] is None:
                                st["smooth_pt"] = index_pt
                            else:
                                sx = int(SMOOTHING_ALPHA * index_pt[0] + (1 - SMOOTHING_ALPHA) * st["smooth_pt"][0])
                                sy = int(SMOOTHING_ALPHA * index_pt[1] + (1 - SMOOTHING_ALPHA) * st["smooth_pt"][1])
                                st["smooth_pt"] = (sx, sy)
                            pt = st["smooth_pt"]

                            if st["prev_pt"] is not None:
                                cv2.line(canvas, st["prev_pt"], pt, st["color"], st["thickness"], cv2.LINE_AA)
                                if show_fx:
                                    cv2.line(glow_layer, st["prev_pt"], pt, st["color"],
                                              st["thickness"] + 10, cv2.LINE_AA)
                                    particles.spawn(pt, st["color"])
                            st["prev_pt"] = pt
                            cv2.circle(frame, pt, st["thickness"] // 2 + 4, st["color"], -1, cv2.LINE_AA)
                            cv2.circle(frame, pt, st["thickness"] // 2 + 6, (255, 255, 255), 1, cv2.LINE_AA)
                        else:
                            st["prev_pt"] = None
                            st["smooth_pt"] = None

                    elif mode == "Select":
                        st["prev_pt"] = None
                        st["smooth_pt"] = None
                        box_h = sidebar_box_height()
                        idx = sidebar_index_for_y(index_pt[1], box_h) if index_pt[0] < SIDEBAR_W else -1
                        cv2.circle(frame, index_pt, 12, (255, 255, 255), 2, cv2.LINE_AA)

                        if idx != -1:
                            if idx == st["hover_idx"]:
                                elapsed = time.time() - st["hover_start"]
                                angle = int(360 * min(elapsed / HOVER_TIME_TO_SELECT, 1.0))
                                cv2.ellipse(frame, index_pt, (16, 16), 0, -90, -90 + angle,
                                            (255, 255, 255), 3)
                                if elapsed >= HOVER_TIME_TO_SELECT:
                                    if idx == CLEAR_INDEX:
                                        canvas[:] = 0
                                        glow_layer[:] = 0
                                    else:
                                        st["color_idx"] = idx
                                        st["color"] = PALETTE[idx]["bgr"]
                                    st["hover_start"] = time.time()
                            else:
                                st["hover_idx"] = idx
                                st["hover_start"] = time.time()
                        else:
                            st["hover_idx"] = None

                    elif mode == "Resize":
                        st["prev_pt"] = None
                        st["smooth_pt"] = None
                        thumb_pt = landmarks_px[THUMB_TIP]
                        d = dist(thumb_pt, index_pt)
                        d = max(PINCH_MIN_PX, min(PINCH_MAX_PX, d))
                        new_thickness = int(np.interp(d, [PINCH_MIN_PX, PINCH_MAX_PX], [MIN_BRUSH, MAX_BRUSH]))
                        st["thickness"] = new_thickness
                        mid_pt = ((thumb_pt[0] + index_pt[0]) // 2, (thumb_pt[1] + index_pt[1]) // 2)
                        cv2.line(frame, thumb_pt, index_pt, (255, 255, 255), 1, cv2.LINE_AA)
                        cv2.circle(frame, mid_pt, new_thickness // 2 + 2, st["color"], -1, cv2.LINE_AA)
                        cv2.circle(frame, mid_pt, new_thickness // 2 + 4, (255, 255, 255), 1, cv2.LINE_AA)
                        cv2.putText(frame, f"{new_thickness}px", (mid_pt[0] + 20, mid_pt[1]),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

                    elif mode == "Erase":
                        st["prev_pt"] = None
                        st["smooth_pt"] = None
                        st["hover_idx"] = None
                        wrist = landmarks_px[0]
                        index_mcp = landmarks_px[5]
                        pinky_mcp = landmarks_px[17]
                        palm_cx = (wrist[0] + index_mcp[0] + pinky_mcp[0]) // 3
                        palm_cy = (wrist[1] + index_mcp[1] + pinky_mcp[1]) // 3
                        eraser_radius = 40 + st["thickness"]
                        if palm_cx > SIDEBAR_W and palm_cy > TOPBAR_H:
                            cv2.circle(canvas, (palm_cx, palm_cy), eraser_radius, (0, 0, 0), -1)
                            cv2.circle(glow_layer, (palm_cx, palm_cy), eraser_radius, (0, 0, 0), -1)
                        cv2.circle(frame, (palm_cx, palm_cy), eraser_radius, (0, 0, 220), 2, cv2.LINE_AA)

                    else:  # Idle
                        st["prev_pt"] = None
                        st["smooth_pt"] = None
                        st["hover_idx"] = None

                    draw_hand_badge(frame, label, landmarks_px[0], mode, MODE_COLORS.get(mode, (150, 150, 150)))

            # reset state for hands that disappeared this frame
            for label, st in hand_states.items():
                if label not in active_labels:
                    st["prev_pt"] = None
                    st["smooth_pt"] = None
                    st["hover_idx"] = None
                    st["mode"] = "Idle"

            # ---- composite glow (soft, blurred) then the crisp canvas on top ----
            if show_fx:
                blurred_glow = cv2.GaussianBlur(glow_layer, (0, 0), sigmaX=9, sigmaY=9)
                frame = cv2.addWeighted(frame, 1.0, blurred_glow, 0.55, 0)

            gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
            _, inv_mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
            inv_mask_bgr = cv2.cvtColor(inv_mask, cv2.COLOR_GRAY2BGR)
            frame = cv2.bitwise_and(frame, inv_mask_bgr)
            frame = cv2.bitwise_or(frame, canvas)

            if show_fx:
                particles.update_and_draw(frame)

            now = time.time()
            fps = 1 / (now - prev_time) if now != prev_time else 0
            prev_time = now

            draw_topbar(frame, fps)
            draw_sidebar(frame, hand_states)

            footer = "c: clear   g: fx on/off   h: skeleton   s: save   q: quit"
            cv2.putText(frame, footer, (SIDEBAR_W + 14, FRAME_H - 14), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)

            cv2.imshow("AI Virtual Painter", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            elif key == ord('c'):
                canvas[:] = 0
                glow_layer[:] = 0
            elif key == ord('g'):
                show_fx = not show_fx
            elif key == ord('h'):
                show_skeleton = not show_skeleton
            elif key == ord('s'):
                filename = os.path.join(SAVE_DIR, f"painting_{int(time.time())}.png")
                cv2.imwrite(filename, canvas)
                print(f"Saved: {filename}")

    finally:
        landmarker.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
