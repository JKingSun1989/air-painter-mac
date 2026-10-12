"""Deterministic acceptance cases using the same 21-point hand interface as UI."""
import math
import unittest

import numpy as np

from painter_core import PaintEngine
from hand_interaction import HandInteraction, pinch_measurement


def hand(cursor, ratio=0.8, gesture="Draw", scale=100):
    x, y = cursor
    points = [(x, y + scale)] * 21
    points[0] = (x, y + 1.6 * scale)
    points[9] = (x, y + 0.6 * scale)
    points[5], points[17] = (x - 0.4 * scale, y + 0.7 * scale), (x + 0.4 * scale, y + 0.7 * scale)
    points[4], points[8] = (x + ratio * scale / 2, y), (x - ratio * scale / 2, y)
    points[6] = (points[8][0], y + 0.35 * scale)
    for tip, pip in ((12, 10), (16, 14), (20, 18)):
        points[tip], points[pip] = (x, y + scale), (x, y + 0.65 * scale)
    if gesture != "Draw":
        points[8] = (x - ratio * scale / 2, y + 0.9 * scale)
        points[4] = (x + ratio * scale / 2, y + 0.9 * scale)
    return points


def star(engine, center=(190, 190), radius=65):
    vertices = [(round(center[0] + radius * math.cos(-math.pi/2 + i * 4*math.pi/5)),
                 round(center[1] + radius * math.sin(-math.pi/2 + i * 4*math.pi/5))) for i in range(5)]
    for point in vertices + vertices[:1]:
        engine.draw(point, smooth=False)
    engine.lift()
    return vertices[0]


class DragTests(unittest.TestCase):
    def setUp(self):
        self.engine = PaintEngine(800, 600, alpha=1)
        self.engine.set_enabled(True)
        self.control = HandInteraction(self.engine, (0, 0, 800, 600))
        self.now = 0.0

    def frame(self, cursor=None, ratio=.2, gesture="Draw", delta=.06):
        self.now += delta
        return self.control.update(None if cursor is None else hand(cursor, ratio, gesture), self.now)

    def grab(self, cursor):
        self.frame(cursor)
        self.frame(cursor)
        self.frame(cursor)
        self.assertEqual(self.control.state, "DRAG")

    def release(self, cursor):
        self.frame(cursor, ratio=.8)
        self.frame(cursor, ratio=.8)
        self.frame(cursor, ratio=.8)
        self.assertEqual(self.control.state, "IDLE")

    def test_star_circle_release_regrab_no_trails(self):
        tip = star(self.engine)
        original = self.engine.objects[0]
        self.grab(tip)
        for dx in (55, 110, 165, 220):
            self.frame((tip[0] + dx, tip[1]))
        self.release((tip[0] + 220, tip[1]))
        moved = self.engine.objects[0]
        self.assertEqual((moved.x, moved.y), (original.x + 220, original.y))
        np.testing.assert_array_equal(original.color, moved.color)
        np.testing.assert_array_equal(original.alpha, moved.alpha)
        released = self.engine.snapshot()
        for _ in range(5):
            self.frame((650, 450), ratio=.8)
        np.testing.assert_array_equal(released[0], self.engine.canvas)
        self.frame((600, 400), ratio=.8, gesture="Idle")
        self.engine.select_color(2)
        for angle in np.linspace(0, 2*math.pi, 80):
            self.engine.draw((round(180 + 55*math.cos(angle)), round(360 + 55*math.sin(angle))), smooth=False)
        self.engine.lift()
        circle = self.engine.objects[1]
        self.grab((235, 360))
        for dx in (50, 100, 150, 200):
            self.frame((235 + dx, 360 + dx/5))
        self.release((435, 400))
        self.assertIs(self.engine.objects[0], moved)
        self.assertEqual((self.engine.objects[1].x, self.engine.objects[1].y), (circle.x + 200, circle.y + 40))
        self.grab((tip[0] + 220, tip[1]))
        self.frame((tip[0] + 280, tip[1] + 50))
        self.release((tip[0] + 280, tip[1] + 50))
        self.assertEqual(len(self.engine.objects), 2)
        self.assertEqual(self.engine.alpha[190, 300], 0)  # no line along translation
        self.assertEqual((self.engine.objects[0].x, self.engine.objects[0].y), (original.x + 280, original.y + 50))

    def test_grab_offset_and_noop_keeps_redo(self):
        star(self.engine)
        obj = self.engine.objects[0]
        point = (190, 133)  # off-centre, near top stroke
        self.assertTrue(self.engine.begin_drag(point))
        self.engine.move_drag(point)
        self.assertIs(self.engine.objects[0], obj)
        self.engine.move_drag((point[0] + 80, point[1] + 25))
        self.engine.end_drag()
        self.assertEqual((self.engine.objects[0].x, self.engine.objects[0].y), (obj.x + 80, obj.y + 25))
        self.assertTrue(self.engine.undo())
        self.assertTrue(self.engine.begin_drag(point))
        self.engine.end_drag()
        self.assertTrue(self.engine.redo())

    def test_bbox_alone_cannot_hit_empty_circle_or_erased_hole(self):
        self.engine.set_tool("ellipse")
        self.engine.draw((100, 100), smooth=False)
        self.engine.draw((300, 300), smooth=False)
        self.engine.lift()
        self.assertFalse(self.engine.begin_drag((200, 200)))
        self.assertTrue(self.engine.begin_drag((301, 200)))
        self.engine.end_drag()
        self.engine.set_tool("eraser")
        self.engine.thickness = 30
        self.engine.draw((300, 200), smooth=False)
        self.engine.lift()
        self.assertFalse(self.engine.begin_drag((300, 200)))

    def test_topmost_only_and_underlying_object_restored(self):
        for color in (0, 2):
            self.engine.select_color(color)
            self.engine.draw((120, 180), smooth=False)
            self.engine.draw((260, 180), smooth=False)
            self.engine.lift()
        bottom, top = self.engine.objects
        self.assertTrue(self.engine.begin_drag((180, 180)))
        self.assertEqual(self.engine.dragged_id, top.id)
        self.engine.move_drag((180, 300))
        self.engine.end_drag()
        self.assertIs(self.engine.objects[0], bottom)
        np.testing.assert_array_equal(self.engine.canvas[180, 180], (0, 0, 255))
        np.testing.assert_array_equal(self.engine.canvas[300, 180], (255, 0, 0))

    def test_drag_undo_redo_restores_geometry_and_eraser(self):
        point = star(self.engine)
        original = self.engine.snapshot()
        self.grab(point)
        for dx in range(10, 110, 10):
            self.frame((point[0] + dx, point[1]))
        self.release((point[0] + 100, point[1]))
        self.assertEqual(len(self.engine.history), 2)
        moved = self.engine.snapshot()
        self.engine.undo()
        np.testing.assert_array_equal(original[0], self.engine.canvas)
        self.assertEqual(self.engine.objects[0].x, original[2][0].x)
        self.engine.redo()
        np.testing.assert_array_equal(moved[0], self.engine.canvas)
        self.engine.set_tool("eraser")
        self.engine.draw((point[0] + 100, point[1]), smooth=False)
        self.engine.lift()
        erased = self.engine.snapshot()
        self.engine.undo()
        np.testing.assert_array_equal(moved[1], self.engine.alpha)
        self.engine.redo()
        np.testing.assert_array_equal(erased[1], self.engine.alpha)
        self.engine.clear()
        self.engine.undo()
        np.testing.assert_array_equal(erased[1], self.engine.alpha)
        self.assertEqual(len(self.engine.objects), 1)

    def test_palm_normalisation_and_jitter_hysteresis(self):
        for size in (40, 100, 230):
            self.assertAlmostEqual(pinch_measurement(hand((200, 200), .25, scale=size))[0], .25)
        point = star(self.engine)
        for ratio in (.27, .31, .26, .34, .29, .25, .4):
            self.frame(point, ratio)
        self.assertIsNone(self.engine.dragged_id)
        self.grab(point)
        for ratio in (.29, .42, .45, .47, .40, .48, .3):
            self.frame(point, ratio)
            self.assertEqual(self.control.state, "DRAG")
        self.release(point)
        self.assertEqual(len(self.engine.history), 1)  # no movement, no undo item

    def test_short_loss_freezes_and_reanchors_long_loss_releases(self):
        point = star(self.engine)
        self.grab(point)
        self.frame((point[0] + 60, point[1]))
        before = self.engine.snapshot()
        self.frame(None)
        self.frame(None)
        self.frame((650, 350))
        np.testing.assert_array_equal(before[0], self.engine.canvas)
        self.frame((670, 360))
        self.assertEqual(self.engine.objects[0].x, before[2][0].x + 20)
        self.frame(None, delta=.7)
        self.assertEqual(self.control.state, "IDLE")
        self.assertIsNone(self.engine.dragged_id)
        released = self.engine.snapshot()
        for _ in range(5):
            self.frame((670, 360))
        np.testing.assert_array_equal(released[0], self.engine.canvas)
        self.assertIsNone(self.engine.dragged_id)

    def test_slow_reacquisition_without_missing_frame_still_safe(self):
        point = star(self.engine)
        self.grab(point)
        old = self.engine.snapshot()
        self.frame((650, 350), delta=.8)
        np.testing.assert_array_equal(old[0], self.engine.canvas)
        self.assertIsNone(self.engine.dragged_id)

    def test_tracking_jump_does_not_teleport(self):
        point = star(self.engine)
        self.grab(point)
        old = self.engine.snapshot()
        self.frame((650, 350))
        np.testing.assert_array_equal(old[0], self.engine.canvas)
        self.frame((670, 360))
        self.assertEqual(self.engine.objects[0].x, old[2][0].x + 20)

    def test_group_multistroke_multicolour_and_finish(self):
        self.engine.set_group_mode(True)
        self.engine.draw((100, 100), smooth=False)
        self.engine.draw((200, 100), smooth=False)
        self.engine.lift()
        self.engine.select_color(2)
        self.engine.draw((100, 180), smooth=False)
        self.engine.draw((200, 180), smooth=False)
        self.assertEqual(self.engine.group_strokes, 2)
        completed = self.engine.finish_object()
        self.assertEqual(len(self.engine.objects), 1)
        self.assertIs(completed, self.engine.objects[0])
        self.assertEqual(self.engine.group_strokes, 0)
        self.assertIsNone(self.engine.active_group)
        self.assertTrue(self.engine.group_mode)
        grouped = self.engine.objects[0]
        self.engine.draw((300, 300), smooth=False)
        self.engine.lift()
        self.assertEqual(len(self.engine.objects), 2)
        self.engine.begin_drag((150, 100))
        self.engine.move_drag((230, 120))
        self.engine.end_drag()
        moved = self.engine.objects[0]
        np.testing.assert_array_equal(grouped.color, moved.color)
        np.testing.assert_array_equal(self.engine.canvas[120, 230], (0, 0, 255))
        np.testing.assert_array_equal(self.engine.canvas[200, 230], (255, 0, 0))

    def test_pause_controls_and_draw_during_drag_are_safe(self):
        point = star(self.engine)
        self.grab(point)
        old = self.engine.snapshot()
        self.engine.draw((500, 500))
        np.testing.assert_array_equal(old[0], self.engine.canvas)
        self.control.reset()
        for _ in range(3):
            self.frame(point)
        self.assertIsNone(self.engine.dragged_id)
        self.engine.set_enabled(False)
        self.frame((600, 400), .8)
        np.testing.assert_array_equal(old[0], self.engine.canvas)

    def test_bounds_and_smoothing_preserve_object_pixels(self):
        point = star(self.engine)
        self.engine.set_smoothing(.35)
        original = self.engine.objects[0]
        self.engine.begin_drag(point)
        self.engine.move_drag((point[0] + 100, point[1]))
        self.assertEqual(self.engine.objects[0].x, original.x + 35)
        for _ in range(30):
            self.engine.move_drag((2000, 2000))
        self.engine.end_drag()
        moved = self.engine.objects[0]
        self.assertEqual(moved.bounds[2:], (800, 600))
        np.testing.assert_array_equal(moved.alpha, original.alpha)

    def test_subpixel_grab_and_toolbar_edge_do_not_jump(self):
        self.engine.draw((122, 102), smooth=False)
        self.engine.lift()
        self.engine.drag_bounds = (121, 101, 800, 546)
        original = self.engine.objects[0]
        self.assertTrue(self.engine.begin_drag((122.5, 102.5)))
        self.engine.move_drag((122.5, 102.5))
        self.assertIs(self.engine.objects[0], original)
        self.engine.reanchor_drag((180.5, 200.5))
        self.engine.move_drag((180.5, 200.5))
        self.assertIs(self.engine.objects[0], original)

    def test_finish_empty_group_does_not_finish_an_unrelated_object(self):
        star(self.engine)
        original = self.engine.snapshot()
        self.engine.set_group_mode(True)
        self.assertIsNone(self.engine.finish_object())
        self.assertIsNone(self.engine.finish_object())
        self.assertEqual(len(self.engine.history), 1)
        np.testing.assert_array_equal(original[0], self.engine.canvas)


if __name__ == "__main__":
    unittest.main()
