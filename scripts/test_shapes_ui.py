"""Real-window shape preview, export and preferences restart integration test."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_virtual_painter as app
from painter_core import PaintEngine
from preferences import DEFAULTS, load_preferences, save_preferences
import cv2
import numpy as np


def main():
    real_wait, real_callback, real_show = cv2.waitKey, cv2.setMouseCallback, cv2.imshow
    engine = handler = None
    ticks = 0
    round_number = 1
    committed = None
    images = []
    output = ROOT / "test-output/shape-paintings"

    class TestEngine(PaintEngine):
        def save(self, directory=output, transparent=False):
            result = super().save(directory, transparent=transparent)
            images.append(result)
            return result

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = TestEngine(*args, **kwargs)
        return engine

    def set_callback(window, callback):
        nonlocal handler
        handler = callback
        real_callback(window, callback)

    def event(code, x, y):
        handler(code, x, y, 0, None)

    def click(x, y=20):
        event(cv2.EVENT_LBUTTONDOWN, x, y)

    def drag(start, end, release=True):
        event(cv2.EVENT_LBUTTONDOWN, *start)
        event(cv2.EVENT_MOUSEMOVE, *end)
        if release:
            event(cv2.EVENT_LBUTTONUP, *end)

    def show(window, frame):
        real_show(window, frame)
        if round_number == 1 and ticks == 14:
            assert cv2.imwrite(str(ROOT / "test-output/shapes_ui_preview.png"), frame)

    def wait(delay):
        nonlocal ticks, committed
        real_wait(12)
        ticks += 1
        if round_number == 2:
            if ticks == 1:
                assert engine.thickness == 12 and engine.smoother.alpha == 0.45
                assert engine.color_idx == 2 and engine.tool == "pen"
                assert engine.export_background == "white" and not engine.enabled
                assert not np.any(engine.alpha)
                return ord("l")
            return ord("q")
        if ticks == 1:
            assert engine.thickness == 10 and engine.smoother.alpha == 0.3
            assert engine.color_idx == 2 and engine.export_background == "white"
            click(280, 65)
            click(400)
        elif ticks == 2:
            assert engine.tool == "line"
            drag((180, 220), (380, 280), release=False)
        elif ticks == 3:
            assert engine.shape_start is not None and not np.any(engine.alpha)
            event(cv2.EVENT_LBUTTONUP, 380, 280)
        elif ticks == 4:
            assert len(engine.history) == 1 and engine.alpha[250, 280] > 0
            return ord("r")
        elif ticks == 5:
            drag((200, 350), (360, 490))
        elif ticks == 6:
            assert len(engine.history) == 2 and engine.alpha[420, 280] == 0
            return ord("o")
        elif ticks == 7:
            return ord("2")
        elif ticks == 8:
            assert engine.tool == "ellipse" and engine.color_idx == 1
            drag((520, 350), (720, 490))
        elif ticks == 9:
            assert len(engine.history) == 3 and engine.alpha[420, 620] == 0
            assert engine.alpha[350, 620] > 0
            committed = engine.snapshot()
        elif ticks == 10:
            drag((800, 200), (950, 300), release=False)
        elif ticks == 11:
            assert engine.shape_start is not None
            return ord("x")
        elif ticks == 12:
            assert engine.shape_start is None and len(engine.history) == 3
            np.testing.assert_array_equal(committed[1], engine.alpha)
            return ord("z")
        elif ticks == 13:
            assert len(engine.history) == 2
            return ord("y")
        elif ticks == 14:
            np.testing.assert_array_equal(committed[1], engine.alpha)
            return ord("b")
        elif ticks == 15:
            assert engine.export_background == "black"
            return ord("b")
        elif ticks == 16:
            assert engine.export_background == "white"
            return ord("s")
        elif ticks == 17:
            assert len(images) == 1
            image = cv2.imread(str(images[0]))
            np.testing.assert_array_equal(image[150, 150], (255, 255, 255))
            np.testing.assert_array_equal(image[250, 280], (255, 0, 0))
            return ord("t")
        elif ticks == 18:
            assert len(images) == 2
            image = cv2.imread(str(images[1]), cv2.IMREAD_UNCHANGED)
            np.testing.assert_array_equal(image[..., 3], engine.alpha)
            return ord("+")
        elif ticks == 19:
            return ord("]")
        elif ticks == 20:
            assert engine.smoother.alpha == 0.35
            click(700)
        elif ticks == 21:
            assert engine.smoother.alpha == 0.45
            return ord("p")
        elif ticks == 22:
            return ord("3")
        elif ticks == 23:
            return ord("h")
        elif ticks == 24:
            return ord("q")
        return 255

    with tempfile.TemporaryDirectory() as directory:
        settings = Path(directory) / "settings.json"
        initial = dict(DEFAULTS, thickness=10, smoothing=0.3, color_idx=2,
                       input_mode="mouse", export_background="white", show_skeleton=False)
        save_preferences(initial, settings)
        for round_number in (1, 2):
            ticks = 0
            args = ["ai_virtual_painter.py", "--no-camera", "--settings", str(settings)]
            with patch.object(sys, "argv", args), patch.object(app, "PaintEngine", side_effect=make_engine), \
                 patch.object(cv2, "setMouseCallback", side_effect=set_callback), \
                 patch.object(cv2, "waitKey", side_effect=wait), patch.object(cv2, "imshow", side_effect=show):
                app.main()
        restored = load_preferences(settings)
        assert restored == dict(DEFAULTS, thickness=12, smoothing=0.45, color_idx=2,
                                tool="line", input_mode="mouse", export_background="white", show_skeleton=True)
    report = {"ok": True, "actual_opencv_windows": 2, "camera_accessed": False,
              "verified": ["line/rectangle/ellipse", "live preview before commit", "commit on mouse release",
                           "cancel preview", "undo/redo shape", "color preserves selected shape",
                           "white PNG and RGBA PNG", "smoothing button and keyboard", "settings restored after restart"],
              "restored_preferences": restored, "saved_images": [str(path.relative_to(ROOT)) for path in images]}
    (ROOT / "test-output/shapes_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
