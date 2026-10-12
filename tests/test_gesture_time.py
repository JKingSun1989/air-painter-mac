import unittest

import numpy as np

from gesture_time import GestureTimeController
from hand_interaction import PinchState, PINCH_CLOSE
from test_drag import hand


class GestureTimeTests(unittest.TestCase):
    def setUp(self):
        self.controller = GestureTimeController(smoothing=1)
        self.now = 0.0

    def frame(self, ratio=.2, delta=.06, mode="TIME", missing=False, x=300, y=260):
        self.now += delta
        return self.controller.update(None if missing else hand((x, y), ratio), None, mode, self.now)

    def ratio(self, progress):
        return PINCH_CLOSE + progress*(self.controller.FULL_OPEN-PINCH_CLOSE)

    def grab(self):
        for _ in range(3):
            result = self.frame()
        self.assertTrue(result.dragging)
        self.assertEqual(result.progress, 0)

    def test_pinch_to_full_open_finishes_the_animation(self):
        self.grab()
        for progress in (.25, .5, .75, 1):
            self.assertAlmostEqual(self.frame(self.ratio(progress)).progress, progress)
        self.assertTrue(self.controller.dragging)

    def test_opening_beyond_pinch_release_continues_playback(self):
        self.grab()
        for _ in range(4):
            result = self.frame(.65)
        self.assertFalse(self.controller.pinched)
        self.assertTrue(result.dragging)
        self.assertGreater(self.frame(1.0).progress, result.progress)

    def test_closing_reverses_to_the_bud(self):
        self.grab()
        for progress in (1, .75, .5, .25, 0):
            self.assertAlmostEqual(self.frame(self.ratio(progress)).progress, progress)

    def test_translation_or_hand_scale_does_not_control_time(self):
        self.grab()
        progress = self.frame(.7).progress
        for x, y, scale in ((200, 300, 40), (650, 180, 220), (450, 400, 100)):
            self.now += .06
            result = self.controller.update(hand((x, y), .7, scale=scale), None, "TIME", self.now)
            self.assertAlmostEqual(result.progress, progress)

    def test_stationary_and_small_ratio_noise_hold_state(self):
        self.controller.smoother.alpha = .35
        self.grab()
        progress = self.frame(.7).progress
        for ratio in (.7, .705, .695, .7)*5:
            self.assertEqual(self.frame(ratio).progress, progress)

    def test_open_hand_before_pinch_does_not_start_playback(self):
        for _ in range(5):
            self.assertEqual(self.frame(1.4).progress, 0)
            self.assertFalse(self.controller.dragging)
        self.grab()

    def test_progress_clamps_and_smoothed_endpoints_finish_exactly(self):
        self.controller.smoother.alpha = .35
        self.grab()
        for _ in range(4):
            result = self.frame(1.5)
            self.assertTrue(0 <= result.progress <= 1)
        self.assertEqual(result.progress, 1)
        for _ in range(4):
            result = self.frame(.05)
        self.assertEqual(result.progress, 0)

    def test_close_debounce_and_open_threshold_jitter_do_not_restart(self):
        for ratio in (.26, .35, .25, .32, .27, .4):
            self.assertFalse(self.frame(ratio).dragging)
        self.grab()
        for ratio in (.3, .44, .47, .4, .48, .32):
            self.assertTrue(self.frame(ratio).dragging)
        self.assertGreater(self.controller.progress, 0)

    def test_short_loss_freezes_and_recovers_without_a_jump(self):
        self.grab()
        progress = self.frame(.7).progress
        self.assertEqual(self.frame(missing=True).state, "TIME_LOST")
        self.frame(missing=True)
        self.assertEqual(self.frame(.9).progress, progress)
        self.assertGreater(self.frame(.95).progress, progress)

    def test_long_loss_releases_and_requires_open_then_pinch(self):
        self.grab()
        progress = self.frame(.7).progress
        self.assertFalse(self.frame(missing=True, delta=.7).dragging)
        for _ in range(5):
            result = self.frame(.2)
            self.assertFalse(result.dragging)
            self.assertEqual(result.progress, progress)
        for _ in range(3):
            self.frame(1.2)
        self.grab()

    def test_stalled_frame_releases_safely(self):
        self.grab()
        progress = self.frame(.7).progress
        result = self.frame(1.5, delta=.8)
        self.assertFalse(result.dragging)
        self.assertEqual(result.progress, progress)

    def test_inactive_mode_cannot_change_time(self):
        self.grab()
        progress = self.frame(.7).progress
        for mode in ("DRAW", "IDLE", "DRAG"):
            result = self.frame(1.4, mode=mode)
            self.assertEqual(result.state, "INACTIVE")
            self.assertFalse(result.dragging)
            self.assertEqual(result.progress, progress)

    def test_reset_returns_to_bud_and_waits_for_pinch(self):
        self.grab()
        self.frame(.7)
        self.controller.reset()
        for _ in range(4):
            result = self.frame(1.3)
            self.assertEqual(result.progress, 0)
            self.assertFalse(result.dragging)
        self.grab()
        self.assertAlmostEqual(self.frame(self.ratio(.5)).progress, .5)

    def test_supplied_pinch_state_is_reusable(self):
        controller = self.controller
        self.assertTrue(controller.update(hand((300, 260), .2), True, "TIME", 1).dragging)
        progress = controller.update(hand((300, 260), .7), PinchState(False), "TIME", 1.06).progress
        self.assertGreater(progress, 0)
        self.assertTrue(controller.update(hand((300, 260), 1.3), False, "TIME", 1.12).dragging)
        self.assertEqual(controller.progress, 1)

    def test_invalid_landmarks_are_treated_as_loss(self):
        self.grab()
        progress = self.frame(.7).progress
        for data in ([], np.zeros((3, 2)), np.full((21, 2), np.nan), np.zeros((21, 2))):
            self.now += .06
            result = self.controller.update(data, None, "TIME", self.now)
            self.assertEqual(result.progress, progress)
        with self.assertRaises(ValueError):
            GestureTimeController(progress=float("nan"))

    def test_enter_while_pinched_can_start_the_opening_gesture(self):
        self.controller.enter()
        self.grab()
        self.assertEqual(self.frame(1.3).progress, 1)


if __name__ == "__main__":
    unittest.main()
