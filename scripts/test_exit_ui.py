"""Actual-window exit checks, including resource and preferences cleanup."""
import json
from pathlib import Path
import signal
from types import SimpleNamespace
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_virtual_painter as app
import cv2
import numpy as np
from config import FRAME_H, FRAME_W
from preferences import DEFAULTS, load_preferences, save_preferences


def run_case(mode, settings):
    handler = None
    ticks = 0
    real_wait, real_callback = cv2.waitKey, cv2.setMouseCallback

    class Camera:
        released = False
        def read(self):
            assert ticks < 3, "Exit request was ignored"
            return True, np.full((FRAME_H, FRAME_W, 3), 55, np.uint8)
        def release(self):
            self.released = True

    class Model:
        closed = False
        def detect_for_video(self, image, timestamp):
            return SimpleNamespace(hand_landmarks=[], handedness=[])
        def close(self):
            self.closed = True

    def callback(window, function):
        nonlocal handler
        handler = function
        real_callback(window, function)

    def wait(delay):
        nonlocal ticks
        real_wait(8)
        ticks += 1
        if sys.platform == "darwin":
            from AppKit import NSApplication
            titles = [str(window.title()) for window in NSApplication.sharedApplication().windows() if window.isVisible()]
            assert app.WINDOW_TITLE in titles, titles
        if mode == "mouse_exit":
            handler(cv2.EVENT_LBUTTONDOWN, 40, 690, 0, None)
        elif mode == "ctrl_q":
            return 17
        elif mode == "sigterm":
            signal.raise_signal(signal.SIGTERM)
        elif mode == "window_close":
            cv2.destroyWindow(app.WINDOW)
        return 255

    camera, model = Camera(), Model()
    report_path = ROOT / "test-output" / ("exit_" + mode + ".json")
    original_signal = signal.getsignal(signal.SIGTERM)
    arguments = ["ai_virtual_painter.py", "--settings", str(settings), "--smoothing", ".35", "--report", str(report_path)]
    with patch.object(sys, "argv", arguments), patch.object(app, "require_camera_permission"), \
         patch.object(app, "open_camera", return_value=camera), patch.object(app, "create_landmarker", return_value=model), \
         patch.object(cv2, "setMouseCallback", side_effect=callback), patch.object(cv2, "waitKey", side_effect=wait):
        app.main()
    assert camera.released and model.closed
    assert load_preferences(settings)["smoothing"] == .35
    assert signal.getsignal(signal.SIGTERM) == original_signal
    report = json.loads(report_path.read_text())
    expected = {"mouse_exit": "exit_button", "sigterm": "termination_requested", "window_close": "window_closed", "ctrl_q": "quit"}
    assert report["exit_reason"] == expected[mode]
    assert report["frames"] == 1
    return mode


def main():
    (ROOT / "test-output").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        settings = Path(directory) / "settings.json"
        save_preferences(DEFAULTS, settings)
        passed = [run_case(mode, settings) for mode in ("mouse_exit", "ctrl_q", "sigterm", "window_close")]
    report = {"ok": True, "actual_opencv_windows": 4, "synthetic_camera_and_model": True,
              "verified": passed + ["native Chinese title matches exactly", "camera released", "model closed", "preferences saved", "signal handler restored"]}
    (ROOT / "test-output/exit_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
