"""Verify new drawing tools in a real window without camera or model access."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_virtual_painter as app
from painter_core import PaintEngine
import cv2
import numpy as np


def main():
    real_wait, real_callback, real_imshow = cv2.waitKey, cv2.setMouseCallback, cv2.imshow
    ticks = 0
    engine = None
    handler = None
    original = erased = None
    images = []
    output = ROOT / "test-output/mouse-paintings"

    class TestEngine(PaintEngine):
        def save(self, directory=output, transparent=False):
            image = super().save(directory, transparent=transparent)
            images.append(image)
            return image

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = TestEngine(*args, **kwargs)
        return engine

    def set_callback(window, callback):
        nonlocal handler
        handler = callback
        real_callback(window, callback)

    def event(code, x, y=300):
        handler(code, x, y, 0, None)

    def click(x, y=65):
        event(cv2.EVENT_LBUTTONDOWN, x, y)

    def show(window, frame):
        real_imshow(window, frame)
        if ticks == 3:
            assert cv2.imwrite(str(ROOT / "test-output/mouse_ui_preview.png"), frame)

    def wait(delay):
        nonlocal ticks, original, erased
        real_wait(12)
        ticks += 1
        if ticks == 1:
            click(280)
        elif ticks == 2:
            event(cv2.EVENT_LBUTTONDOWN, 200)
            event(cv2.EVENT_MOUSEMOVE, 450)
            event(cv2.EVENT_LBUTTONUP, 450)
        elif ticks == 3:
            assert engine.enabled and len(engine.history) == 1
            np.testing.assert_array_equal(engine.canvas[300, 325], (0, 0, 255))
            original = engine.snapshot()
            return ord("e")
        elif ticks == 4:
            assert engine.tool == "eraser"
            event(cv2.EVENT_LBUTTONDOWN, 325)
            event(cv2.EVENT_LBUTTONUP, 325)
        elif ticks == 5:
            assert engine.alpha[300, 325] == 0
            erased = engine.snapshot()
            click(500)  # undo erasing
        elif ticks == 6:
            np.testing.assert_array_equal(original[1], engine.alpha)
            click(860)  # redo erasing
        elif ticks == 7:
            np.testing.assert_array_equal(erased[1], engine.alpha)
            click(970)  # transparent save
        elif ticks == 8:
            assert len(images) == 1
            saved = cv2.imread(str(images[0]), cv2.IMREAD_UNCHANGED)
            assert saved.shape[2] == 4 and saved[300, 325, 3] == 0
            np.testing.assert_array_equal(saved[..., 3], erased[1])
            return ord("z")
        elif ticks == 9:
            np.testing.assert_array_equal(original[1], engine.alpha)
            return ord("y")
        elif ticks == 10:
            np.testing.assert_array_equal(erased[1], engine.alpha)
            return ord("t")
        elif ticks == 11:
            assert len(images) == 2
            return ord("c")
        elif ticks == 12:
            assert not np.any(engine.alpha)
            return ord("z")
        elif ticks == 13:
            np.testing.assert_array_equal(erased[1], engine.alpha)
            return ord("y")
        elif ticks == 14:
            assert not np.any(engine.alpha)
            click(40, 260)  # blue switches back to pen
        elif ticks == 15:
            assert engine.color_idx == 2 and engine.tool == "pen"
            event(cv2.EVENT_LBUTTONDOWN, 200)
            event(cv2.EVENT_MOUSEMOVE, 450)
            event(cv2.EVENT_LBUTTONUP, 450)
        elif ticks == 16:
            np.testing.assert_array_equal(engine.canvas[300, 325], (255, 0, 0))
            assert not engine.redo_history
            click(40, 630)  # eraser sidebar
        elif ticks == 17:
            assert engine.tool == "eraser"
            click(40, 630)  # return to pen
        elif ticks == 18:
            assert engine.tool == "pen"
            return 32  # pause
        elif ticks == 19:
            assert not engine.enabled
            event(cv2.EVENT_LBUTTONDOWN, 200, 400)
            event(cv2.EVENT_MOUSEMOVE, 450, 400)
            event(cv2.EVENT_LBUTTONUP, 450, 400)
        elif ticks == 20:
            assert not np.any(engine.alpha[400])
            return ord("m")  # no-camera cannot switch to unavailable hand input
        elif ticks == 21:
            return ord("q")
        return 255

    report_path = ROOT / "test-output/mouse_loop.json"
    args = ["ai_virtual_painter.py", "--no-camera", "--no-settings", "--report", str(report_path)]
    with patch.object(sys, "argv", args), patch.object(app, "require_camera_permission") as permission, \
         patch.object(app, "open_camera") as camera, patch.object(app, "create_landmarker") as model, \
         patch.object(app, "PaintEngine", side_effect=make_engine), \
         patch.object(cv2, "setMouseCallback", side_effect=set_callback), \
         patch.object(cv2, "waitKey", side_effect=wait), patch.object(cv2, "imshow", side_effect=show):
        app.main()
    permission.assert_not_called()
    camera.assert_not_called()
    model.assert_not_called()
    stats = json.loads(report_path.read_text())
    assert stats["camera"] is None and not stats["local_inference"] and stats["input_mode"] == "mouse"
    report = {"ok": True, "actual_opencv_window": True, "frames": ticks, "camera_accessed": False,
              "verified": ["mouse continuous drawing", "eraser", "undo/redo stroke and clear",
                           "RGBA PNG from button and keyboard", "transparent eraser hole", "palette returns to pen",
                           "paused mouse does not draw", "no-camera input stays mouse", "clean exit"],
              "saved_images": [str(path.relative_to(ROOT)) for path in images]}
    (ROOT / "test-output/mouse_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
