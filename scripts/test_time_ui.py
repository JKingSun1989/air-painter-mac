"""Production-loop TIME integration with one synthetic camera and one model.

Real OpenCV window and callbacks. Covers opening/closing playback, safety,
mode isolation and preservation of paint/undo/redo. No real-person claim.
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
from gesture_time import GestureTimeController
from particles import Particles
from config import FRAME_W, FRAME_H
import cv2
import numpy as np


def run_hand_case():
    engine = controller = particles = handler = None
    index = -1
    clock = 100.0
    timeline, rendered = [], []
    references = {}
    output = ROOT / "test-output/time"
    output.mkdir(parents=True, exist_ok=True)
    real_wait, real_show, real_callback, real_render = cv2.waitKey, cv2.imshow, cv2.setMouseCallback, app.render_controls

    def add(points=None, key=255, check=None, click=None, delta=.06):
        timeline.append((points, key, check, click, delta))

    def ink(x, y, **kwargs):
        add(hand((x+40, y), .8), **kwargs)

    def hold(x, ratio=.2, count=4, check=None):
        for i in range(count):
            add(hand((x, 300), ratio), check=check if i == count-1 else None)

    def record_full_paint():
        assert len(engine.objects) == 2
        references["full_paint"] = engine.snapshot()

    def record_baseline():
        assert len(engine.objects) == 1 and len(engine.redo_history) == 1
        references["baseline"] = engine.snapshot()
        references["history"] = tuple(engine.history)
        references["redo"] = tuple(engine.redo_history)

    def preserved():
        np.testing.assert_array_equal(engine.canvas, references["baseline"][0])
        np.testing.assert_array_equal(engine.alpha, references["baseline"][1])
        assert len(engine.objects) == len(references["baseline"][2])
        assert all(a is b for a, b in zip(engine.objects, references["baseline"][2]))
        assert len(engine.history) == len(references["history"])
        assert all(a is b for a, b in zip(engine.history, references["history"]))
        assert len(engine.redo_history) == len(references["redo"])
        assert all(a is b for a, b in zip(engine.redo_history, references["redo"]))
        assert engine.dragged_id is None and engine.previous is None
        assert not (particles.items or particles.embers)

    def at(progress, stage=None, dragging=None):
        def check():
            preserved()
            assert rendered[-1]["application_mode"] == "TIME"
            assert abs(controller.progress-progress) <= .01, (controller.progress, progress)
            if dragging is not None:
                assert controller.dragging == dragging
            if stage:
                assert cv2.imwrite(str(output / (stage+".png")), references["frame"])
        return check

    def held_time():
        preserved()
        assert controller.progress == references["held_progress"]

    def remember_progress():
        preserved()
        references["held_progress"] = controller.progress

    def returned():
        preserved()
        assert rendered[-1]["application_mode"] == "DRAW"
        assert not controller.dragging

    def redo_restored():
        np.testing.assert_array_equal(engine.canvas, references["full_paint"][0])
        assert len(engine.objects) == 2 and len(engine.history) == 2 and not engine.redo_history
        references["baseline"] = engine.snapshot()
        references["history"], references["redo"] = tuple(engine.history), tuple(engine.redo_history)

    def paint_resumed():
        assert len(engine.objects) == 3 and len(engine.history) == 3
        assert all(a is b for a, b in zip(engine.objects[:2], references["full_paint"][2]))
        assert engine.alpha[450, 660] > 0
        references["new_paint"] = engine.snapshot()

    def undo_resumed():
        np.testing.assert_array_equal(engine.canvas, references["full_paint"][0])

    def redo_resumed():
        np.testing.assert_array_equal(engine.canvas, references["new_paint"][0])

    add(key=32)
    for x in (200, 225, 250, 275):
        ink(x, 220)
    add(key=ord("3"))
    for x in (200, 225, 250, 275):
        ink(x, 400)
    add(check=record_full_paint, key=ord("z"))
    add(check=record_baseline, key=ord("k"))
    for _ in range(3):
        ink(500, 320, check=at(0, dragging=False))
    def opening(progress, x=350, check=None):
        ratio = .28 + progress*(controller_full_open-.28)
        add(hand((x, 300), ratio), check=check)

    controller_full_open = GestureTimeController.FULL_OPEN
    hold(350, check=at(0, "time_bud", True))
    for p, stage in ((.25, "time_quarter"), (.5, "time_half"), (.75, "time_three_quarters"), (1, "time_bloom")):
        opening(p, check=at(p, stage, True))
    hold(350, ratio=1.3, check=at(1, dragging=True))
    # Fully open finishes, closing reverses. Translating the hand is irrelevant.
    for p in (.75, .5, .25, 0):
        opening(p, x=750 if p == .5 else 350, check=at(p, "time_reversed_bud" if p == 0 else None, True))
    opening(.5, check=remember_progress)
    for x, y in ((400, 330), (700, 280), (250, 320)):
        add(hand((x, y), .715), check=held_time)
    # Pinch-release threshold jitter must not stop or restart aperture control.
    for ratio in (.44, .48, .43, .47):
        add(hand((350, 300), ratio), check=preserved)
    opening(.5, check=at(.5, dragging=True))
    add(click=(510, 684))
    add(check=at(0, dragging=False))
    hold(350, check=at(0, dragging=True))
    opening(.25, check=at(.25, dragging=True))
    add()
    add()
    opening(.5, check=at(.25, dragging=True))
    opening(.6, check=at(.6, dragging=True))
    add(delta=.8, check=at(.6, dragging=False))
    hold(500, check=at(.6, dragging=False))
    hold(500, ratio=1.3, check=at(.6, dragging=False))
    for key in "czyepmgfst":
        ink(500, 320, key=ord(key), check=preserved)
    ink(500, 320, click=(500, 300), check=preserved)
    ink(500, 320, check=preserved)
    # The former progress bar is inert and is no longer drawn.
    add(click=(790, 630))
    add(check=at(.6, dragging=False))
    hold(500, check=at(0, dragging=True))
    add(hand((500, 300), .2), key=ord("k"))
    for _ in range(4):
        add(hand((500, 300), .2), check=returned)
    for _ in range(4):
        ink(620, 450, check=returned)
    add(hand((650, 280), .8, "Idle"))
    add(key=ord("y"))
    add(check=redo_restored, click=(360, 684))
    ink(500, 320, check=at(0, dragging=False))
    hold(500, check=at(0, dragging=True))
    opening(1, check=at(1, dragging=True))
    add(key=ord("n"))
    add(check=at(0, dragging=False), key=ord("k"))
    # A mouse mode-button click is consumed before the next index frame.
    ink(620, 450, check=returned, click=(220, 684))
    ink(660, 450, check=at(0, dragging=False))
    add(key=ord("k"))
    add(hand((650, 280), .8, "Idle"))
    ink(620, 450)
    ink(660, 450)
    add(check=paint_resumed, key=ord("z"))
    add(check=undo_resumed, key=ord("y"))
    add(check=redo_resumed, key=ord("q"))

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = PaintEngine(*args, **kwargs)
        return engine

    def make_controller(*args, **kwargs):
        nonlocal controller
        controller = GestureTimeController(*args, **kwargs)
        return controller

    def make_particles():
        nonlocal particles
        particles = Particles()
        return particles

    class Camera:
        released = False
        def read(self):
            nonlocal index, clock
            index += 1
            assert index < len(timeline), "Application did not exit"
            clock += timeline[index][4]
            return True, np.full((FRAME_H, FRAME_W, 3), 55, np.uint8)
        def release(self):
            self.released = True

    class Model:
        closed = False
        calls = 0
        def detect_for_video(self, image, timestamp):
            self.calls += 1
            points = timeline[index][0]
            # Preserve integer fixture pixels through float normalisation; avoid
            # 359.999999 becoming 359 in the production int conversion.
            return SimpleNamespace(hand_landmarks=[] if points is None else [[SimpleNamespace(x=(x+1e-6)/FRAME_W, y=(y+1e-6)/FRAME_H) for x, y in points]], handedness=[])
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
        real_wait(5)
        points, key, check, click, delta = timeline[index]
        if check:
            check()
        if click:
            handler(cv2.EVENT_LBUTTONDOWN, *click, 0, None)
            handler(cv2.EVENT_LBUTTONUP, *click, 0, None)
        return key

    camera, model = Camera(), Model()
    with patch.object(sys, "argv", ["ai_virtual_painter.py", "--no-settings", "--smoothing", "1"]), \
         patch.object(app, "require_camera_permission"), patch.object(app, "open_camera", return_value=camera) as camera_factory, \
         patch.object(app, "create_landmarker", return_value=model) as model_factory, \
         patch.object(app, "PaintEngine", side_effect=make_engine), patch.object(app, "GestureTimeController", side_effect=make_controller), \
         patch.object(app, "Particles", side_effect=make_particles), patch.object(app, "render_controls", side_effect=render), \
         patch.object(app, "draw_skeleton"), patch.object(cv2, "setMouseCallback", side_effect=callback), \
         patch.object(cv2, "imshow", side_effect=show), patch.object(cv2, "waitKey", side_effect=wait), \
         patch.object(app.time, "monotonic", side_effect=lambda: clock):
        app.main()
    camera_factory.assert_called_once()
    model_factory.assert_called_once()
    assert model.calls == len(timeline)
    assert camera.released and model.closed
    report = dict(ok=True, actual_opencv_window=True, synthetic_hand_input=True, live_camera=False,
                  frames=len(timeline), camera_instances=1, model_instances=1,
                  verified=["pinch-to-open playback finishes at bloom; closing reverses", "translation/scale independent, stationary hold",
                            "short loss freezes and long loss safely releases", "reset and former timeline is inert",
                            "TIME blocks drawing/dragging/paint commands/particles", "mode switch cannot start a stroke",
                            "paint objects and original undo/redo unchanged", "drawing and undo/redo resume after TIME"],
                  artifacts=str(output.relative_to(ROOT)))
    return report


def run_no_camera_case():
    controller = handler = None
    ticks = 0
    real_wait, real_callback = cv2.waitKey, cv2.setMouseCallback

    def make_controller(*args, **kwargs):
        nonlocal controller
        controller = GestureTimeController(*args, **kwargs)
        return controller

    def callback(window, function):
        nonlocal handler
        handler = function
        real_callback(window, function)

    def wait(delay):
        nonlocal ticks
        real_wait(5)
        ticks += 1
        if ticks == 1:
            assert controller.progress == 0
            handler(cv2.EVENT_LBUTTONDOWN, 370, 630, 0, None)
        elif ticks == 2:
            assert controller.progress == 0
            handler(cv2.EVENT_MOUSEMOVE, 1200, 630, 0, None)
        elif ticks == 3:
            assert controller.progress == 0
            handler(cv2.EVENT_LBUTTONUP, 1200, 630, 0, None)
            return ord("n")
        elif ticks == 4:
            assert controller.progress == 0
            return ord("k")
        elif ticks == 5:
            return ord("q")
        return 255

    report_path = ROOT / "test-output/time_no_camera_loop.json"
    with patch.object(sys, "argv", ["ai_virtual_painter.py", "--no-camera", "--no-settings", "--time-demo", "--report", str(report_path)]), \
         patch.object(app, "require_camera_permission") as permission, patch.object(app, "open_camera") as camera, \
         patch.object(app, "create_landmarker") as model, patch.object(app, "GestureTimeController", side_effect=make_controller), \
         patch.object(cv2, "setMouseCallback", side_effect=callback), patch.object(cv2, "waitKey", side_effect=wait):
        app.main()
    permission.assert_not_called()
    camera.assert_not_called()
    model.assert_not_called()
    stats = json.loads(report_path.read_text())
    assert stats["application_mode"] == "DRAW" and stats["camera"] is None and not stats["local_inference"]
    return dict(ok=True, frames=ticks, camera_instances=0, model_instances=0,
                verified=["--no-camera --time-demo", "removed timeline clicks/drags do nothing", "return to mouse painting"])


def main():
    report = run_hand_case()
    report["no_camera_case"] = run_no_camera_case()
    (ROOT / "test-output/time_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
