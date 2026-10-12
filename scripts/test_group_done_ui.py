"""Actual window regression for F/DONE over the production hand-input loop.

Synthetic 21-point hands and callback-injected clicks; does not alter user
settings or rely on a person being in front of the camera.
"""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_drag import hand
import ai_virtual_painter as app
from painter_core import PaintEngine
from config import FRAME_W, FRAME_H
import cv2
import numpy as np


def run_case(trigger):
    engine = None
    handler = None
    clock = 100.0
    index = -1
    rendered = []
    references = {}
    timeline = []
    output = ROOT / "test-output/group-done"
    output.mkdir(parents=True, exist_ok=True)
    real_wait, real_callback, real_render, real_show = cv2.waitKey, cv2.setMouseCallback, app.render_controls, cv2.imshow

    def add(points=None, key=255, click=None, check=None):
        timeline.append((points, key, click, check))

    def ink(point, **kwargs):
        add(hand((point[0] + 40, point[1]), .8), **kwargs)

    def group_ready():
        assert engine.group_mode and engine.group_strokes == 0

    def before_done():
        assert engine.group_strokes == 2

    def completed():
        assert len(engine.objects) == 1 and engine.group_mode
        assert engine.group_strokes == 0 and engine.active_group is None
        assert rendered[-1]["completed_id"] == engine.objects[0].id
        assert "共 2 笔" in rendered[-1]["message"]
        references["completed"] = engine.snapshot()
        obj = engine.objects[0]
        x1, y1, _, _ = obj.bounds
        np.testing.assert_array_equal(references["frame"][y1-3, x1-3], (100, 240, 100))
        np.testing.assert_array_equal(references["frame"][110, 275], (30, 65, 30))
        assert cv2.imwrite(str(output / (trigger + "_done.png")), references["frame"])

    def held_after_done():
        assert len(engine.objects) == 1 and engine.previous is None
        assert len(engine.history) == 2
        np.testing.assert_array_equal(engine.canvas, references["completed"][0])
        np.testing.assert_array_equal(engine.alpha, references["completed"][1])

    def dragging():
        assert engine.dragged_id == references["completed"][2][0].id

    def moved():
        original, obj = references["completed"][2][0], engine.objects[0]
        assert max(abs(obj.x - original.x - 80), abs(obj.y - original.y - 40)) <= 1
        assert len(engine.objects) == 1 and engine.dragged_id is None
        np.testing.assert_array_equal(original.color, obj.color)
        np.testing.assert_array_equal(original.alpha, obj.alpha)
        np.testing.assert_array_equal(engine.canvas[300, 330], (0, 0, 255))
        np.testing.assert_array_equal(engine.canvas[380, 330], (255, 0, 0))
        references["moved"] = obj

    def next_object():
        assert len(engine.objects) == 2
        assert engine.objects[0] is references["moved"]
        assert engine.active_group.id == engine.objects[1].id
        assert engine.group_strokes == 1
        assert rendered[-1]["completed_id"] is None

    add(key=32)
    add(key=ord("g") if trigger == "keyboard_f" else 255,
        click=(150, 20) if trigger == "mouse_done" else None)
    add(check=group_ready)
    for x in (200, 240, 280, 320):
        ink((x, 260))
    add(key=ord("3"))
    for x in (200, 240, 280):
        ink((x, 340))
    ink((320, 340), key=ord("f") if trigger == "keyboard_f" else 255,
        click=(150, 65) if trigger == "mouse_done" else None, check=before_done)
    ink((320, 340), check=completed)
    for _ in range(5):
        ink((350, 340), check=held_after_done)
    # A completed group can be grabbed immediately, without an extra START.
    for _ in range(4):
        add(hand((250, 260), .2))
    add(hand((250, 260), .2), check=dragging)
    for dx in (20, 40, 60, 80):
        add(hand((250 + dx, 260 + dx/2), .2))
    for _ in range(4):
        add(hand((330, 300), .8))
    add(check=moved)
    add(hand((700, 300), .8, "Idle"))
    ink((620, 440))
    ink((660, 440))
    add(check=next_object, key=ord("q"))

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = PaintEngine(*args, **kwargs)
        return engine

    class Camera:
        released = False
        def read(self):
            nonlocal clock, index
            clock += .06
            index += 1
            assert index < len(timeline)
            return True, np.full((FRAME_H, FRAME_W, 3), 55, np.uint8)
        def release(self):
            self.released = True

    class Model:
        closed = False
        def detect_for_video(self, image, timestamp):
            points = timeline[index][0]
            return SimpleNamespace(hand_landmarks=[] if points is None else [[SimpleNamespace(x=x/FRAME_W, y=y/FRAME_H) for x, y in points]], handedness=[])
        def close(self):
            self.closed = True

    def callback(window, function):
        nonlocal handler
        handler = function
        real_callback(window, function)

    def render(frame, engine, fps, mode, message, input_mode, **kwargs):
        rendered.append(dict(message=message, **kwargs))
        real_render(frame, engine, fps, mode, message, input_mode, **kwargs)

    def show(window, frame):
        references["frame"] = frame.copy()
        real_show(window, frame)

    def wait(delay):
        real_wait(6)
        points, key, click, check = timeline[index]
        if check:
            check()
        if click:
            handler(cv2.EVENT_LBUTTONDOWN, *click, 0, None)
        return key

    camera, model = Camera(), Model()
    with patch.object(sys, "argv", ["ai_virtual_painter.py", "--no-settings", "--smoothing", "1"]), \
         patch.object(app, "require_camera_permission"), patch.object(app, "open_camera", return_value=camera), \
         patch.object(app, "create_landmarker", return_value=model), patch.object(app, "PaintEngine", side_effect=make_engine), \
         patch.object(app, "render_controls", side_effect=render), patch.object(cv2, "setMouseCallback", side_effect=callback), \
         patch.object(cv2, "imshow", side_effect=show), patch.object(cv2, "waitKey", side_effect=wait), \
         patch.object(app.time, "monotonic", side_effect=lambda: clock):
        app.main()
    assert camera.released and model.closed
    return dict(trigger=trigger, frames=len(timeline), ok=True)


def main():
    cases = [run_case(trigger) for trigger in ("keyboard_f", "mouse_done")]
    report = dict(ok=True, actual_opencv_windows=2, synthetic_hand_input=True, cases=cases,
                  verified=["F and mouse DONE complete two-colour multi-stroke group",
                            "visible confirmation and group counter reset", "held index does not start another stroke",
                            "immediate pinch moves both strokes", "next drawing starts a separate group"])
    (ROOT / "test-output/group_done_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
