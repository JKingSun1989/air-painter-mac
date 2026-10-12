import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np

from painter_core import PaintEngine, PointSmoother
from controls import DwellControl, hit_test, render_controls
from hand_utils import classify_gesture, fingers_up
from config import FRAME_W, FRAME_H, PALETTE


class PainterTests(unittest.TestCase):
    def test_stopped_does_not_draw(self):
        engine = PaintEngine(400, 300)
        engine.draw((50, 50))
        self.assertFalse(np.any(engine.canvas))
        self.assertEqual(len(engine.history), 0)
        engine.set_enabled(True)
        engine.draw((80, 80))
        engine.set_enabled(False)
        saved = engine.canvas.copy()
        engine.draw((180, 180))
        np.testing.assert_array_equal(saved, engine.canvas)

    def test_undo_whole_stroke_and_clear(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((40, 40))
        engine.draw((80, 40))
        first = engine.canvas.copy()
        engine.lift()
        engine.draw((40, 150))
        engine.draw((80, 150))
        self.assertTrue(engine.undo())
        np.testing.assert_array_equal(first, engine.canvas)
        engine.clear()
        self.assertFalse(np.any(engine.canvas))
        engine.undo()
        np.testing.assert_array_equal(first, engine.canvas)
        engine.undo()
        self.assertFalse(np.any(engine.canvas))

    def test_resume_and_color_change_do_not_bridge(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((50, 50))
        engine.set_enabled(False)
        engine.set_enabled(True)
        engine.draw((130, 50))
        self.assertFalse(np.any(engine.canvas[50, 90]))
        engine.select_color(2)
        engine.draw((210, 50))
        self.assertFalse(np.any(engine.canvas[50, 170]))
        np.testing.assert_array_equal(engine.canvas[50, 210], PALETTE[2]["bgr"])

    def test_all_colors_and_png_save(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        for i in range(len(PALETTE)):
            engine.select_color(i)
            engine.draw((30 + i * 40, 80))
        with tempfile.TemporaryDirectory() as folder:
            a, b = engine.save(folder), engine.save(folder)
            self.assertNotEqual(a, b)
            loaded = cv2.imread(str(a))
            np.testing.assert_array_equal(loaded, engine.canvas)
        for i, item in enumerate(PALETTE):
            np.testing.assert_array_equal(engine.canvas[80, 30 + i * 40], item["bgr"])

    def test_overlapping_stroke_pixels_do_not_change_on_lift_or_clear_undo(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        for i in range(len(PALETTE)):
            engine.select_color(i)
            engine.draw((100+i*4, 100), smooth=False)
            engine.draw((108+i*4, 105), smooth=False)
        color, alpha = engine.canvas.copy(), engine.alpha.copy()
        engine.lift()
        np.testing.assert_array_equal(color, engine.canvas)
        np.testing.assert_array_equal(alpha, engine.alpha)
        engine.clear()
        engine.undo()
        np.testing.assert_array_equal(color, engine.canvas)
        np.testing.assert_array_equal(alpha, engine.alpha)

    def test_filter_reduces_stationary_jitter_and_reset(self):
        smoother = PointSmoother(0.35)
        raw = [(100 + (-1)**i * 8, 120 + (-1)**i * 6) for i in range(120)]
        filtered = [smoother.update(point) for point in raw]
        self.assertLess(np.std(np.array(filtered)[20:, 0]), np.std(np.array(raw)[20:, 0]) * 0.35)
        smoother.reset()
        self.assertEqual(smoother.update((250, 280)), (250, 280))

    def test_failed_save_keeps_drawing_and_reports_error(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((50, 50))
        before = engine.canvas.copy()
        with tempfile.TemporaryDirectory() as directory:
            with patch("painter_core.cv2.imwrite", return_value=False):
                with self.assertRaises(OSError):
                    engine.save(directory)
            with patch("painter_core.cv2.imwrite", side_effect=cv2.error("disk error")):
                with self.assertRaises(OSError):
                    engine.save(directory)
        np.testing.assert_array_equal(before, engine.canvas)

    def test_tracking_jump_breaks_line(self):
        engine = PaintEngine(600, 400)  # jumps must be detected before smoothing
        engine.set_enabled(True)
        engine.draw((30, 80))
        engine.draw((450, 80))
        self.assertFalse(np.any(engine.canvas[80, 200]))
        self.assertEqual(len(engine.history), 2)

    def test_history_is_bounded(self):
        engine = PaintEngine(400, 300, history_limit=3)
        engine.set_enabled(True)
        for i in range(5):
            engine.lift()
            engine.draw((50 + i * 30, 50))
        self.assertEqual(len(engine.history), 3)

    def test_dwell_fires_once_until_pointer_leaves(self):
        dwell = DwellControl(0.7)
        self.assertIsNone(dwell.update("undo", 1))
        self.assertIsNone(dwell.update("undo", 1.3))
        self.assertEqual(dwell.update("undo", 1.8), "undo")
        self.assertIsNone(dwell.update("undo", 3))
        dwell.update(None, 3.1)
        self.assertIsNone(dwell.update("undo", 3.2))
        self.assertEqual(dwell.update("undo", 4), "undo")

    def test_redo_restores_stroke_and_clear_with_alpha(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80))
        drawn = engine.snapshot()
        self.assertTrue(engine.undo())
        self.assertFalse(np.any(engine.alpha))
        self.assertTrue(engine.redo())
        np.testing.assert_array_equal(drawn[0], engine.canvas)
        np.testing.assert_array_equal(drawn[1], engine.alpha)
        engine.clear()
        engine.undo()
        engine.redo()
        self.assertFalse(np.any(engine.alpha))
        engine.undo()
        np.testing.assert_array_equal(drawn[1], engine.alpha)

    def test_new_drawing_discards_redo_but_tool_change_preserves_it(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80))
        engine.undo()
        engine.select_color(2)
        engine.set_tool("eraser")
        self.assertEqual(len(engine.redo_history), 1)
        engine.set_tool("pen")
        engine.draw((160, 80))
        self.assertFalse(engine.redo())
        self.assertFalse(np.any(engine.alpha[80, 80]))

    def test_eraser_removes_pixels_and_transparency_and_is_undoable(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80), smooth=False)
        engine.draw((200, 80), smooth=False)
        original = engine.snapshot()
        engine.set_tool("eraser")
        engine.draw((140, 80))
        self.assertFalse(np.any(engine.canvas[80, 140]))
        self.assertEqual(engine.alpha[80, 140], 0)
        np.testing.assert_array_equal(engine.canvas[80, 80], PALETTE[0]["bgr"])
        erased = engine.snapshot()
        engine.undo()
        np.testing.assert_array_equal(engine.canvas, original[0])
        np.testing.assert_array_equal(engine.alpha, original[1])
        engine.redo()
        np.testing.assert_array_equal(engine.alpha, erased[1])

    def test_transparent_png_and_edge_colors(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.select_color(2)
        engine.draw((80, 80))
        expected = engine.export(transparent=True)
        self.assertEqual(expected.shape, (300, 400, 4))
        np.testing.assert_array_equal(expected[80, 80], (255, 0, 0, 255))
        self.assertEqual(expected[0, 0, 3], 0)
        edges = (expected[..., 3] > 0) & (expected[..., 3] < 255)
        self.assertTrue(np.any(edges))
        self.assertTrue(np.all(expected[..., 0][edges] == 255))
        reconstructed = np.rint(expected[..., :3].astype(float) * expected[..., 3, None] / 255).astype(np.uint8)
        self.assertLessEqual(np.max(np.abs(reconstructed.astype(int) - engine.canvas.astype(int))), 1)
        with tempfile.TemporaryDirectory() as directory:
            filename = engine.save(directory, transparent=True)
            np.testing.assert_array_equal(cv2.imread(str(filename), cv2.IMREAD_UNCHANGED), expected)

    def test_mouse_fast_drag_does_not_break_line(self):
        engine = PaintEngine(600, 300)
        engine.set_enabled(True)
        engine.draw((40, 80), smooth=False)
        engine.draw((500, 80), smooth=False)
        self.assertEqual(len(engine.history), 1)
        np.testing.assert_array_equal(engine.canvas[80, 300], PALETTE[0]["bgr"])

    def test_empty_eraser_does_not_consume_history(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.set_tool("eraser")
        engine.draw((80, 80))
        self.assertEqual(len(engine.history), 0)

    def test_antialiased_preview_and_erase_reveals_camera(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80))
        frame = np.full((300, 400, 3), 160, np.uint8)
        preview = engine.composite(frame.copy())
        np.testing.assert_array_equal(preview[80, 80], PALETTE[0]["bgr"])
        np.testing.assert_array_equal(preview[0, 0], frame[0, 0])
        engine.set_tool("eraser")
        engine.draw((80, 80))
        preview = engine.composite(frame.copy())
        np.testing.assert_array_equal(preview[80, 80], frame[80, 80])

    def test_gesture_lifting_and_thumb_does_not_block_draw(self):
        up = dict(index=True, middle=False, ring=False, pinky=False)
        self.assertEqual(classify_gesture(up, True), "Draw")
        self.assertEqual(classify_gesture(up, False), "Draw")
        self.assertEqual(classify_gesture(dict(index=True, middle=True, ring=False, pinky=False), False), "Select")
        self.assertEqual(classify_gesture(dict.fromkeys(up, True), True), "Idle")
        self.assertEqual(classify_gesture(dict.fromkeys(up, False), False), "Idle")

    def test_hit_testing_and_ui_artifact(self):
        self.assertEqual(hit_test(150, 20), "group")
        self.assertEqual(hit_test(150, 65), "finish")
        self.assertEqual(hit_test(40, 690), "quit")
        self.assertEqual(hit_test(280, 60), "start")
        self.assertEqual(hit_test(720, 60), "save")
        self.assertEqual(hit_test(860, 60), "redo")
        self.assertEqual(hit_test(970, 60), "transparent")
        self.assertEqual(hit_test(40, 630), "eraser")
        self.assertEqual(hit_test(400, 20), "tool:line")
        self.assertEqual(hit_test(480, 20), "tool:rectangle")
        self.assertEqual(hit_test(580, 20), "tool:ellipse")
        self.assertEqual(hit_test(700, 20), "smooth")
        self.assertEqual(hit_test(800, 20), "background")
        self.assertEqual(hit_test(40, 110), "color:0")
        self.assertIsNone(hit_test(-5, 110))
        self.assertIsNone(hit_test(200, 120))
        engine = PaintEngine(FRAME_W, FRAME_H)
        frame = np.full((FRAME_H, FRAME_W, 3), 85, np.uint8)
        render_controls(frame, engine, 30, "Idle", "准备就绪")
        output = Path(__file__).resolve().parents[1] / "test-output/ui_preview.png"
        output.parent.mkdir(exist_ok=True)
        self.assertTrue(cv2.imwrite(str(output), frame))


if __name__ == "__main__":
    unittest.main()
