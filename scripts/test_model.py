"""Integration check using real local inference on an official MediaPipe image.

One-time fixture: curl -fL -o test-output/pointing_up.jpg
https://storage.googleapis.com/mediapipe-assets/pointing_up.jpg
No camera image is recorded, and no image is uploaded.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_virtual_painter import create_landmarker
from config import FRAME_W, FRAME_H, PALETTE
from painter_core import PaintEngine
from hand_utils import fingers_up, thumb_extended, classify_gesture
import cv2
import mediapipe as mp
import numpy as np


def main():
    fixture = cv2.imread(str(ROOT / "test-output/pointing_up.jpg"))
    if fixture is None:
        raise RuntimeError("请先按本文件说明下载官方测试图片。")
    frame = cv2.resize(fixture, (FRAME_W, FRAME_H))
    engine = PaintEngine(FRAME_W, FRAME_H)
    engine.set_enabled(True)
    points = []
    gestures = []
    with create_landmarker() as model:
        for i in range(21):
            moved = cv2.warpAffine(frame, np.float32([[1, 0, i * 4], [0, 1, 0]]), (FRAME_W, FRAME_H))
            rgb = cv2.cvtColor(moved, cv2.COLOR_BGR2RGB)
            result = model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), i * 33)
            assert len(result.hand_landmarks) == 1, f"No hand detected at frame {i}"
            landmarks = result.hand_landmarks[0]
            assert len(landmarks) == 21
            px = [(int(p.x * FRAME_W), int(p.y * FRAME_H)) for p in landmarks]
            gesture = classify_gesture(fingers_up(px), thumb_extended(px))
            assert gesture == "Draw", gesture
            gestures.append(gesture)
            if i % 3 == 0:
                engine.select_color(i // 3)
            points.append(engine.draw(px[8]))
    assert len(engine.history) == 7
    before_clear = engine.canvas.copy()
    engine.clear()
    engine.undo()
    np.testing.assert_array_equal(before_clear, engine.canvas)
    filename = engine.save(ROOT / "test-output/model-paintings")
    np.testing.assert_array_equal(cv2.imread(str(filename)), before_clear)
    engine.set_enabled(False)
    engine.draw((300, 300))
    np.testing.assert_array_equal(before_clear, engine.canvas)
    report = {"inference": "local CPU", "fixture": "MediaPipe official pointing_up.jpg",
              "detected_frames": len(points), "landmarks_per_hand": 21,
              "gesture": "Draw", "colors_tested": [p["name"] for p in PALETTE],
              "save_verified": True, "clear_undo_verified": True, "stop_verified": True,
              "painting": str(filename.relative_to(ROOT)), "ok": True}
    (ROOT / "test-output/model_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
