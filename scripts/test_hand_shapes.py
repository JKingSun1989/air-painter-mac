"""Drive the real hand-input loop with the official image and local inference."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_virtual_painter as app
from painter_core import PaintEngine
from config import FRAME_W, FRAME_H
import cv2
import numpy as np


def main():
    fixture = cv2.imread(str(ROOT / "test-output/pointing_up.jpg"))
    assert fixture is not None
    fixture = cv2.resize(fixture, (FRAME_W, FRAME_H))
    engine = None
    ticks = 0
    real_wait = cv2.waitKey

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = PaintEngine(*args, **kwargs)
        return engine

    class FixtureCamera:
        frame = 0
        released = False
        def read(self):
            self.frame += 1
            phase = next((self.frame - start for start in (3, 11, 19) if start <= self.frame < start + 6), None)
            if phase is None:
                return True, np.zeros_like(fixture)
            image = cv2.warpAffine(fixture, np.float32([[1, 0, phase * 6], [0, 1, phase * 4]]), (FRAME_W, FRAME_H))
            return True, image
        def release(self):
            self.released = True

    camera = FixtureCamera()
    def wait(delay):
        nonlocal ticks
        real_wait(12)
        ticks += 1
        if ticks == 1:
            return ord("l")
        if ticks == 2:
            return 32
        if ticks in (8, 16, 24):
            assert engine.shape_start is not None, f"No {engine.tool} preview"
        if ticks == 9:
            assert len(engine.history) == 1 and engine.shape_start is None
        if ticks == 10:
            return ord("r")
        if ticks == 17:
            assert len(engine.history) == 2 and engine.shape_start is None
        if ticks == 18:
            return ord("o")
        if ticks == 25:
            assert len(engine.history) == 3 and engine.shape_start is None
        if ticks == 26:
            return ord("q")
        return 255

    report_path = ROOT / "test-output/hand_shapes_loop.json"
    args = ["ai_virtual_painter.py", "--no-settings", "--report", str(report_path)]
    with patch.object(sys, "argv", args), patch.object(app, "require_camera_permission"), \
         patch.object(app, "open_camera", return_value=camera), \
         patch.object(app, "PaintEngine", side_effect=make_engine), patch.object(cv2, "waitKey", side_effect=wait):
        app.main()
    assert camera.released
    stats = json.loads(report_path.read_text())
    assert stats["local_inference"] and stats["frames_with_hands"] == 18
    stats["input"] = "official MediaPipe hand fixture; blank frames simulate pen lift"
    report_path.write_text(json.dumps(stats, indent=2) + "\n")
    report = {"ok": True, "actual_opencv_window": True, "local_model": "MediaPipe HandLandmarker",
              "frames": ticks, "frames_with_hands": stats["frames_with_hands"], "live_camera": False,
              "verified": ["index fingertip drives line/rectangle/ellipse preview", "hand loss commits each shape once"],
              "committed_shapes": len(engine.history)}
    (ROOT / "test-output/hand_shapes_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
