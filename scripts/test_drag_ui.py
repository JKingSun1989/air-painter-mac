"""Acceptance sequence in a real OpenCV window with synthetic 21-point hands.

Exercises the production camera loop, gestures, history and exports. This is
deterministic interaction QA, not a claim of real-person/model pinch accuracy.
"""
import json
import math
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


def main():
    timeline = []
    engine = None
    clock = 100.0
    index = -1
    references = {}
    output = ROOT / "test-output/drag-paintings"
    output.mkdir(parents=True, exist_ok=True)
    real_wait = cv2.waitKey

    def add(points=None, key=255, check=None):
        timeline.append((points, key, check))

    def ink(point):
        add(hand((point[0] + 40, point[1]), .8))

    def hold(point, ratio, count=4):
        for _ in range(count):
            add(hand(point, ratio))

    def save_stage(name):
        assert cv2.imwrite(str(output / (name + ".png")), engine.export())

    def star_done():
        assert len(engine.objects) == 1
        references["original_star"] = engine.objects[0]
        save_stage("01_star_drawn")

    def star_moved():
        original, moved = references["original_star"], engine.objects[0]
        assert (moved.x, moved.y) == (original.x + 240, original.y)
        np.testing.assert_array_equal(original.color, moved.color)
        np.testing.assert_array_equal(original.alpha, moved.alpha)
        assert engine.dragged_id is None and len(engine.objects) == 1
        references["moved_star"] = moved
        references["released"] = engine.canvas.copy()
        save_stage("02_star_released_right")

    def stable():
        np.testing.assert_array_equal(references["released"], engine.canvas)

    def circle_done():
        assert len(engine.objects) == 2
        references["circle"] = engine.objects[1]
        assert engine.objects[0] is references["moved_star"]
        save_stage("03_circle_drawn")

    def circle_moved():
        circle, moved = references["circle"], engine.objects[1]
        assert engine.objects[0] is references["moved_star"]
        # The application converts normalised model points to integer pixels.
        assert max(abs(moved.x - circle.x - 160), abs(moved.y - circle.y - 40)) <= 1
        np.testing.assert_array_equal(circle.color, moved.color)
        np.testing.assert_array_equal(circle.alpha, moved.alpha)
        references["moved_circle"] = moved
        save_stage("04_circle_moved_star_unchanged")

    def regrab_done():
        original = references["original_star"]
        assert max(abs(engine.objects[0].x - original.x - 320), abs(engine.objects[0].y - original.y - 30)) <= 1
        assert engine.objects[1] is references["moved_circle"]
        assert len(engine.objects) == 2 and len(engine.history) == 5
        assert engine.alpha[180, 370] == 0  # no translation trail
        references["final"] = engine.snapshot()
        save_stage("05_star_regrabbed")

    def still_dragging():
        assert engine.dragged_id is not None, "jitter released grab"

    def undone():
        assert engine.objects[0].x == references["moved_star"].x
        assert engine.objects[1] is references["moved_circle"]

    def redone():
        np.testing.assert_array_equal(references["final"][0], engine.canvas)

    def exports():
        rgba = cv2.imread(str(references["saved"]), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(rgba, engine.export(True))
        assert rgba.shape == (FRAME_H, FRAME_W, 4)

    add(key=32)
    center = np.array((230, 210))
    vertices = [np.rint(center + 65*np.array((math.cos(-math.pi/2+i*4*math.pi/5),
                                            math.sin(-math.pi/2+i*4*math.pi/5)))).astype(int) for i in range(5)]
    ink(vertices[0])
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        for t in np.linspace(.1, 1, 10):
            ink(np.rint(a + t*(b-a)).astype(int))
    add(check=star_done)
    tip = tuple(vertices[0])
    hold(tip, .2)
    for dx in (60, 120, 180, 240):
        add(hand((tip[0]+dx, tip[1]), .2))
    hold((tip[0]+240, tip[1]), .8)
    add(hand((700, 480), .8), check=star_moved)
    add(hand((700, 480), .8), check=stable)
    add(hand((700, 400), .8, "Idle"), key=ord("3"))
    for angle in np.linspace(0, 2*math.pi, 65):
        ink((round(230 + 55*math.cos(angle)), round(420 + 55*math.sin(angle))))
    add(check=circle_done)
    hold((285, 420), .2)
    for dx in (40, 80, 120, 160):
        add(hand((285+dx, 420+dx/4), .2))
    hold((445, 460), .8)
    add(check=circle_moved)
    hold((tip[0]+240, tip[1]), .2)
    # Above/below release threshold for a single frame must never drop the grab.
    for ratio in (.30, .44, .48, .38, .47, .32):
        add(hand((tip[0]+240, tip[1]), ratio), check=still_dragging)
    for dx in (20, 40, 60, 80):
        add(hand((tip[0]+240+dx, tip[1]+dx*3/8), .2))
    hold((tip[0]+320, tip[1]+30), .8)
    add(check=regrab_done, key=ord("z"))
    add(check=undone, key=ord("y"))
    add(check=redone, key=ord("t"))
    add(check=exports, key=ord("q"))

    class TestEngine(PaintEngine):
        def save(self, directory=output, transparent=False):
            path = super().save(directory, transparent)
            references["saved"] = path
            return path

    def make_engine(*args, **kwargs):
        nonlocal engine
        engine = TestEngine(*args, **kwargs)
        return engine

    class Camera:
        released = False
        def read(self):
            nonlocal index, clock
            index += 1
            clock += .06
            assert index < len(timeline), "Test did not exit"
            return True, np.full((FRAME_H, FRAME_W, 3), 55, np.uint8)
        def release(self):
            self.released = True

    class Model:
        closed = False
        def detect_for_video(self, image, timestamp):
            points = timeline[index][0]
            landmarks = [] if points is None else [[SimpleNamespace(x=x/FRAME_W, y=y/FRAME_H) for x, y in points]]
            return SimpleNamespace(hand_landmarks=landmarks, handedness=[])
        def close(self):
            self.closed = True

    def wait(delay):
        real_wait(5)
        points, key, check = timeline[index]
        if check:
            check()
        return key

    camera, model = Camera(), Model()
    with patch.object(sys, "argv", ["ai_virtual_painter.py", "--no-settings", "--smoothing", "1"]), \
         patch.object(app, "require_camera_permission"), patch.object(app, "open_camera", return_value=camera), \
         patch.object(app, "create_landmarker", return_value=model), patch.object(app, "PaintEngine", side_effect=make_engine), \
         patch.object(app.time, "monotonic", side_effect=lambda: clock), patch.object(cv2, "waitKey", side_effect=wait):
        app.main()
    assert camera.released and model.closed
    report = {"ok": True, "actual_opencv_window": True, "frames": len(timeline),
              "hand_input": "synthetic 21-point landmarks; production application loop",
              "live_camera": False, "real_model": False,
              "verified": ["draw star and move right", "draw circle and move without changing star",
                           "release stays put", "regrab same star", "no drag ink trail",
                           "hysteresis ignores release jitter", "move undo/redo", "RGBA export after moves"],
              "artifacts": str(output.relative_to(ROOT))}
    (ROOT / "test-output/drag_integration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
