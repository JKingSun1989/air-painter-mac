"""Exercise the real OpenCV window/main loop with local hand-image inference.

Only the camera input and input events are supplied by the test. The actual
MediaPipe model, main loop, rendering, mouse callback and command handlers run.
This complements live camera tests without requiring a person at the computer.
"""
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
    fixture = cv2.imread(str(ROOT / "test-output/pointing_up.jpg"))
    assert fixture is not None, "Missing official hand fixture"
    real_wait = cv2.waitKey
    real_callback = cv2.setMouseCallback
    engine = None
    callback = None
    ticks = 0
    captures = {}
    saved = []
    output = ROOT / "test-output/ui-paintings"

    class TestEngine(PaintEngine):
        def save(self, directory=output, transparent=False):
            result = super().save(directory, transparent=transparent)
            saved.append(result)
            return result

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = TestEngine(*args, **kwargs)
        return engine

    class FixtureCamera:
        released = False
        def read(self):
            # Main loop mirrors input. Keep fingertip movement small and continuous.
            shift = ticks * 2
            moved = cv2.warpAffine(fixture, np.float32([[1, 0, shift], [0, 1, 0]]),
                                   (fixture.shape[1], fixture.shape[0]))
            return True, moved
        def release(self):
            self.released = True

    camera = FixtureCamera()

    def set_callback(window, handler):
        nonlocal callback
        callback = handler
        real_callback(window, handler)

    def click(x, y=65):
        callback(cv2.EVENT_LBUTTONDOWN, x, y, 0, None)

    def wait(delay):
        nonlocal ticks
        real_wait(12)
        ticks += 1
        if ticks == 1:
            assert not engine.enabled and not np.any(engine.canvas)
            click(280)  # start mouse callback
        elif ticks == 6:
            assert engine.enabled and np.any(engine.canvas)
            captures["red"] = engine.canvas.copy()
            return ord("3")  # blue keyboard
        elif ticks == 11:
            assert engine.color_idx == 2
            captures["blue"] = engine.canvas.copy()
            assert not np.array_equal(captures["red"], captures["blue"])
            click(390)  # stop
        elif ticks == 12:
            assert not engine.enabled
            captures["paused"] = engine.canvas.copy()
        elif ticks == 15:
            np.testing.assert_array_equal(captures["paused"], engine.canvas)
            click(500)  # undo blue stroke
        elif ticks == 16:
            np.testing.assert_array_equal(captures["red"], engine.canvas)
            click(610)  # clear
        elif ticks == 17:
            assert not np.any(engine.canvas)
            return ord("z")  # undo clear
        elif ticks == 18:
            np.testing.assert_array_equal(captures["red"], engine.canvas)
            click(720)  # save through mouse
        elif ticks == 19:
            assert len(saved) == 1
            np.testing.assert_array_equal(cv2.imread(str(saved[0])), captures["red"])
            return ord("2")  # green
        elif ticks == 20:
            assert engine.color_idx == 1
            return 32  # resume
        elif ticks == 25:
            assert engine.enabled
            captures["green"] = engine.canvas.copy()
            assert not np.array_equal(captures["green"], captures["red"])
            return 32  # pause
        elif ticks == 26:
            assert not engine.enabled
            return ord("c")
        elif ticks == 27:
            assert not np.any(engine.canvas)
            return ord("u")
        elif ticks == 28:
            np.testing.assert_array_equal(captures["green"], engine.canvas)
            return ord("s")
        elif ticks == 29:
            assert len(saved) == 2
            np.testing.assert_array_equal(cv2.imread(str(saved[1])), captures["green"])
            return ord("+")
        elif ticks == 30:
            assert engine.thickness == 10
            return ord("-")
        elif ticks == 31:
            assert engine.thickness == 8
            return ord("h")
        elif ticks == 32:
            return ord("q")
        return 255

    args = ["ai_virtual_painter.py", "--no-settings", "--report", str(ROOT / "test-output/ui_loop.json")]
    with patch.object(sys, "argv", args), patch.object(app, "require_camera_permission"), \
         patch.object(app, "open_camera", return_value=camera), patch.object(app, "PaintEngine", side_effect=make_engine), \
         patch.object(cv2, "setMouseCallback", side_effect=set_callback), patch.object(cv2, "waitKey", side_effect=wait):
        app.main()
    assert camera.released
    loop_report = ROOT / "test-output/ui_loop.json"
    stats = json.loads(loop_report.read_text())
    stats["input"] = "official hand fixture (not live camera)"
    loop_report.write_text(json.dumps(stats, indent=2) + "\n")
    report = {"ok": True, "input": "official hand fixture (not live camera)", "frames": ticks,
              "local_model": "MediaPipe HandLandmarker", "actual_opencv_window": True,
              "verified": ["start/stop mouse and keyboard", "red/blue/green", "undo stroke",
                           "clear and undo clear", "save mouse and keyboard", "brush size", "skeleton toggle", "quit/cleanup"],
              "saved_images": [str(path.relative_to(ROOT)) for path in saved]}
    (ROOT / "test-output/ui_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
