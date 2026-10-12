import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from painter_core import PaintEngine, SHAPE_TOOLS
from preferences import DEFAULTS, load_preferences, save_preferences, validate_preferences


class ShapeTests(unittest.TestCase):
    def test_shapes_preview_commit_undo_redo(self):
        for tool in SHAPE_TOOLS:
            with self.subTest(tool=tool):
                engine = PaintEngine(400, 300)
                engine.set_enabled(True)
                engine.set_tool(tool)
                engine.draw((40, 40), smooth=False)
                engine.draw((240, 200), smooth=False)
                self.assertFalse(np.any(engine.alpha))
                self.assertEqual(len(engine.history), 0)
                background = np.full((300, 400, 3), 160, np.uint8)
                preview = engine.composite(background.copy())
                self.assertTrue(np.any(preview != background))
                engine.lift()
                self.assertTrue(np.any(engine.alpha))
                self.assertEqual(len(engine.history), 1)
                committed = engine.snapshot()
                if tool == "line":
                    self.assertGreater(engine.alpha[120, 140], 0)
                else:
                    self.assertEqual(engine.alpha[120, 140], 0)
                engine.undo()
                self.assertFalse(np.any(engine.alpha))
                engine.redo()
                np.testing.assert_array_equal(engine.canvas, committed[0])
                np.testing.assert_array_equal(engine.alpha, committed[1])

    def test_moving_rectangle_preview_does_not_leave_old_edges(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.set_tool("rectangle")
        engine.draw((40, 40), smooth=False)
        engine.draw((120, 120), smooth=False)
        engine.draw((240, 220), smooth=False)
        preview = engine.composite(np.full((300, 400, 3), 160, np.uint8))
        np.testing.assert_array_equal(preview[120, 80], (160, 160, 160))
        engine.lift()
        self.assertEqual(engine.alpha[120, 80], 0)

    def test_cancelled_shape_preserves_redo(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80))
        original = engine.snapshot()
        engine.undo()
        engine.set_tool("line")
        engine.draw((40, 40), smooth=False)
        engine.draw((240, 200), smooth=False)
        engine.cancel_preview()
        self.assertFalse(np.any(engine.alpha))
        self.assertTrue(engine.redo())
        np.testing.assert_array_equal(engine.alpha, original[1])

    def test_click_without_drag_does_not_create_shape(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.set_tool("ellipse")
        engine.draw((80, 80), smooth=False)
        engine.lift()
        self.assertFalse(np.any(engine.alpha))
        self.assertEqual(len(engine.history), 0)

    def test_color_change_keeps_shape_tool(self):
        engine = PaintEngine(400, 300)
        engine.set_tool("rectangle")
        engine.select_color(2)
        self.assertEqual(engine.tool, "rectangle")

    def test_white_export_keeps_transparency_and_edge_colors(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.draw((80, 80))
        transparent = engine.export(True)
        engine.export_background = "white"
        white = engine.export()
        np.testing.assert_array_equal(white[0, 0], (255, 255, 255))
        np.testing.assert_array_equal(white[80, 80], (0, 0, 255))
        edges = (engine.alpha > 0) & (engine.alpha < 255)
        self.assertTrue(np.all(white[..., 2][edges] == 255))
        np.testing.assert_array_equal(engine.export(True), transparent)
        with tempfile.TemporaryDirectory() as directory:
            filename = engine.save(directory)
            np.testing.assert_array_equal(cv2.imread(str(filename)), white)

    def test_save_commits_pending_shape(self):
        engine = PaintEngine(400, 300)
        engine.set_enabled(True)
        engine.set_tool("line")
        engine.draw((40, 40), smooth=False)
        engine.draw((240, 200), smooth=False)
        with tempfile.TemporaryDirectory() as directory:
            filename = engine.save(directory, transparent=True)
            image = cv2.imread(str(filename), cv2.IMREAD_UNCHANGED)
            self.assertGreater(image[120, 140, 3], 0)
        self.assertEqual(len(engine.history), 1)


class PreferenceTests(unittest.TestCase):
    def test_roundtrip_and_unknown_fields_are_not_saved(self):
        values = dict(DEFAULTS, thickness=16, smoothing=0.2, color_idx=2, tool="ellipse",
                      input_mode="mouse", show_skeleton=False, export_background="white", extra="ignored")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_preferences(values, path)
            expected = {key: values[key] for key in DEFAULTS}
            self.assertEqual(load_preferences(path), expected)
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertFalse(list(Path(directory).glob("*.tmp")))

    def test_missing_corrupt_or_nonobject_settings_use_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            self.assertEqual(load_preferences(path), DEFAULTS)
            for text in ("not JSON", "[]", "null", '"value"'):
                path.write_text(text)
                self.assertEqual(load_preferences(path), DEFAULTS)

    def test_invalid_types_and_values_use_defaults(self):
        bad = dict(thickness=True, smoothing=float("nan"), color_idx=-1,
                   tool="unknown", input_mode="invalid", show_skeleton="false", export_background="red")
        self.assertEqual(validate_preferences(bad), DEFAULTS)
        self.assertEqual(validate_preferences({"smoothing": 10 ** 1000}), DEFAULTS)
        self.assertEqual(validate_preferences({"smoothing": float("inf")}), DEFAULTS)

    def test_failed_atomic_save_keeps_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_preferences(DEFAULTS, path)
            with patch.object(Path, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    save_preferences(dict(DEFAULTS, thickness=20), path)
            self.assertEqual(load_preferences(path), DEFAULTS)
            self.assertFalse(list(Path(directory).glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
