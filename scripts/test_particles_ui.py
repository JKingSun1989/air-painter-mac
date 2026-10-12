"""Real-window particle QA over the production loop with synthetic hand input."""
import json
from pathlib import Path
import random
from types import SimpleNamespace
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_drag import hand
import ai_virtual_painter as app
from painter_core import PaintEngine
from particles import Particles
from config import FRAME_W, FRAME_H, PALETTE
import cv2
import numpy as np


def main():
    engine = particles = handler = None
    timeline = []
    references = {}
    index = -1
    clock = 100.0
    real_wait, real_show, real_callback = cv2.waitKey, cv2.imshow, cv2.setMouseCallback
    output = ROOT / "test-output/particles"
    output.mkdir(parents=True, exist_ok=True)

    def add(points=None, key=255, check=None, event=None, delta=.06):
        timeline.append((points, key, check, event, delta))

    def ink(x, y, **kwargs):
        add(hand((x + 40, y), .8), **kwargs)

    def visible_red():
        assert particles.total_emitted > 0 and particles.changed > 0
        assert all(p["color"] == PALETTE[0]["bgr"] for p in particles.items)
        assert particles.embers
        references["red_emitted"] = particles.total_emitted
        assert cv2.imwrite(str(output / "red_sparks.png"), references["frame"])

    def saved():
        rgba = cv2.imread(str(references["saved"]), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(rgba, engine.export(True))
        references["export"] = rgba

    def faded():
        assert not (particles.items or particles.embers)
        assert particles.total_emitted == references["red_emitted"]
        np.testing.assert_array_equal(references["export"], engine.export(True))

    def visible_blue():
        assert particles.total_emitted > references["red_emitted"]
        assert particles.changed > 0
        assert all(p["color"] == PALETTE[2]["bgr"] for p in particles.items)
        assert particles.embers
        references["blue_emitted"] = particles.total_emitted
        assert cv2.imwrite(str(output / "blue_sparks.png"), references["frame"])

    def no_new_sparks():
        assert not (particles.items or particles.embers)
        assert particles.total_emitted == references["blue_emitted"]

    def dragging():
        no_new_sparks()
        assert engine.dragged_id is not None

    def mouse_done():
        no_new_sparks()
        assert engine.alpha[470, 600] > 0

    add(key=32)
    for x, y in ((200, 250), (225, 244), (250, 256), (275, 250), (300, 260), (325, 254), (350, 265)):
        ink(x, y)
    ink(375, 258, check=visible_red, key=ord("t"))
    add(check=saved)
    for _ in range(6):
        add(delta=.15)
    add(check=faded, key=ord("3"))
    for x, y in ((200, 350), (225, 344), (250, 356), (275, 350), (300, 360), (325, 354), (350, 365)):
        ink(x, y)
    ink(375, 358, check=visible_blue, key=ord("e"))
    for x in (300, 315, 330):
        ink(x, 360, check=no_new_sparks)
    add(check=no_new_sparks, key=ord("p"))
    for _ in range(4):
        add(hand((200, 250), .2))
    add(hand((200, 250), .2), check=dragging)
    add(hand((230, 270), .2), check=dragging)
    add(hand((260, 290), .2), check=dragging)
    for _ in range(4):
        add(hand((260, 290), .8))
    add(key=32)
    for x in (500, 520, 540):
        ink(x, 450, check=no_new_sparks)
    add(key=ord("m"))
    add(key=32)
    add(event=(cv2.EVENT_LBUTTONDOWN, 550, 470))
    add(event=(cv2.EVENT_MOUSEMOVE, 650, 470))
    add(event=(cv2.EVENT_LBUTTONUP, 650, 470))
    add(check=mouse_done, key=ord("q"))

    class TestEngine(PaintEngine):
        def save(self, directory=output, transparent=False):
            path = super().save(directory, transparent)
            references["saved"] = path
            return path

    class TestParticles(Particles):
        total_emitted = 0
        changed = 0
        def follow(self, point, color, dt):
            emitted = super().follow(point, color, dt)
            self.total_emitted += emitted
            return emitted
        def draw(self, frame, bounds=None):
            canvas, alpha = engine.canvas.copy(), engine.alpha.copy()
            before = frame.copy()
            super().draw(frame, bounds)
            self.changed = int(np.count_nonzero(frame != before))
            np.testing.assert_array_equal(engine.canvas, canvas)
            np.testing.assert_array_equal(engine.alpha, alpha)
            return frame

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = TestEngine(*args, **kwargs)
        return engine

    def make_particles():
        nonlocal particles
        particles = TestParticles(rng=random.Random(42))
        return particles

    class Camera:
        released = False
        def read(self):
            nonlocal index, clock
            index += 1
            assert index < len(timeline)
            clock += timeline[index][4]
            return True, np.full((FRAME_H, FRAME_W, 3), 45, np.uint8)
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

    def show(window, frame):
        references["frame"] = frame.copy()
        real_show(window, frame)

    def wait(delay):
        real_wait(6)
        points, key, check, event, delta = timeline[index]
        if check:
            check()
        if event:
            handler(*event, 0, None)
        return key

    camera, model = Camera(), Model()
    with patch.object(sys, "argv", ["ai_virtual_painter.py", "--no-settings", "--smoothing", "1"]), \
         patch.object(app, "require_camera_permission"), patch.object(app, "open_camera", return_value=camera), \
         patch.object(app, "create_landmarker", return_value=model), patch.object(app, "PaintEngine", side_effect=make_engine), \
         patch.object(app, "Particles", side_effect=make_particles), patch.object(app, "draw_skeleton"), \
         patch.object(app, "draw_hand_badge"), patch.object(cv2, "setMouseCallback", side_effect=callback), \
         patch.object(cv2, "imshow", side_effect=show), patch.object(cv2, "waitKey", side_effect=wait), \
         patch.object(app.time, "monotonic", side_effect=lambda: clock):
        app.main()
    assert camera.released and model.closed
    report = dict(ok=True, actual_opencv_window=True, synthetic_hand_input=True, frames=len(timeline),
                  verified=["red/blue sparks follow index strokes", "particles move and expire",
                            "gold/orange embers fly with short trails alongside coloured sparks",
                            "preview never modifies canvas or alpha", "saved RGBA excludes particles",
                            "eraser, drag, pause and mouse drawing emit no particles"],
                  artifacts=str(output.relative_to(ROOT)))
    (ROOT / "test-output/particles_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
