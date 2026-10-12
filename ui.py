"""All OpenCV UI-drawing helpers (topbar, sidebar, badges, skeleton overlay)."""

import cv2

from config import FRAME_W, FRAME_H, TOPBAR_H, SIDEBAR_W, PALETTE, HAND_CONNECTIONS
from chinese_text import draw_text, text_bounds
from ui_labels import HAND_NAMES, MODE_NAMES


def draw_topbar(frame, fps):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (FRAME_W, TOPBAR_H), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, dst=frame)
    draw_text(frame, "AI 隔空绘画", (16, 30), .62, (255, 255, 255))
    draw_text(frame, f"{int(fps)} 帧/秒", (FRAME_W - 110, 30), .5, (200, 200, 200))
    draw_text(frame, "食指绘画 · 两指选择 · 捏合拖动 · 张掌抬笔",
              (250, 30), .42, (170, 170, 170))


def sidebar_box_height():
    usable_h = FRAME_H - TOPBAR_H
    n_boxes = len(PALETTE) + 1
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
        for label, st in hand_states.items():
            if st["color_idx"] == i:
                ring_color = (255, 255, 255) if label == "Right" else (0, 255, 255)
                cv2.rectangle(frame, (10, y1 + 3), (SIDEBAR_W - 10, y2), ring_color, 2, cv2.LINE_AA)

    y1 = TOPBAR_H + len(PALETTE) * box_h
    y2 = y1 + box_h - 6
    cv2.rectangle(frame, (10, y1 + 3), (SIDEBAR_W - 10, y2), (40, 40, 40), -1, cv2.LINE_AA)
    draw_text(frame, "清空", (18, (y1 + y2) // 2 + 5), .42, (255, 255, 255))

    return box_h


def sidebar_index_for_y(y, box_h):
    if y < TOPBAR_H:
        return -1
    idx = (y - TOPBAR_H) // box_h
    if 0 <= idx <= len(PALETTE):
        return int(idx)
    return -1


def draw_hand_badge(frame, label, pos, mode, color):
    text = f"{HAND_NAMES.get(label, label)}：{MODE_NAMES.get(mode, mode)}"
    x, y = pos[0] - 40, max(pos[1] - 26, TOPBAR_H + 14)
    left, top, right, bottom = text_bounds(text, .5)
    cv2.rectangle(frame, (x + left - 6, y + top - 6), (x + right + 6, y + bottom + 6), (20, 20, 20), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x + left - 6, y + top - 6), (x + right + 6, y + bottom + 6), color, 1, cv2.LINE_AA)
    draw_text(frame, text, (x, y), .5, (255, 255, 255))


def draw_skeleton(frame, landmarks_px, tint):
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, landmarks_px[a], landmarks_px[b], tint, 2, cv2.LINE_AA)
    for pt in landmarks_px:
        cv2.circle(frame, pt, 3, (255, 255, 255), -1, cv2.LINE_AA)
