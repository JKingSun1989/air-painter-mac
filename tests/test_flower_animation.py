import unittest

import numpy as np

from flower_animation import FlowerAnimation


class FlowerAnimationTests(unittest.TestCase):
    def setUp(self):
        self.scene = FlowerAnimation()

    def test_deterministic_random_access_and_reverse(self):
        frames = {p: self.scene.render(p, 400, 320) for p in (0, .25, .5, .75, 1)}
        for p in (1, .75, .5, .25, 0, 1, 0, .5):
            np.testing.assert_array_equal(frames[p], self.scene.render(p, 400, 320))
        self.assertEqual(frames[0].shape, (320, 400, 3))
        self.assertTrue(all(not np.array_equal(frames[a], frames[b]) for a, b in ((0, .25), (.25, .5), (.5, .75), (.75, 1))))

    def test_layers_are_separate_and_cached_frames_cannot_be_corrupted(self):
        bg, bud = self.scene.render_layers(0, 400, 320)
        bg2, bloom = self.scene.render_layers(1, 400, 320)
        np.testing.assert_array_equal(bg, bg2)
        self.assertFalse(bg.flags.writeable)
        self.assertEqual(bud.shape, (320, 400, 4))
        self.assertFalse(np.array_equal(bud, bloom))
        expected = self.scene.render(1, 400, 320)
        changed = self.scene.render(1, 400, 320)
        changed.fill(0)
        np.testing.assert_array_equal(expected, self.scene.render(1, 400, 320))

    def test_petals_unfold_in_different_directions(self):
        _, bud = self.scene.render_layers(0, 400, 320)
        _, bloom = self.scene.render_layers(1, 400, 320)
        pink = lambda image: (image[..., 2].astype(int) > image[..., 1].astype(int)+30) & (image[..., 3] > 100)
        by, bx = np.nonzero(pink(bud))
        fy, fx = np.nonzero(pink(bloom))
        self.assertGreater(fx.max()-fx.min(), 3*(bx.max()-bx.min()))
        self.assertLess(by.max(), 320*.55)
        self.assertGreater(np.count_nonzero(pink(bloom)[round(320*.5):]), 100)

    def test_nearby_progress_changes_are_small(self):
        a = self.scene.render(.5, 400, 320).astype(float)
        near = self.scene.render(.501, 400, 320).astype(float)
        far = self.scene.render(.75, 400, 320).astype(float)
        self.assertLess(np.abs(a-near).mean(), 1)
        self.assertGreater(np.abs(a-far).mean(), np.abs(a-near).mean()*5)

    def test_dimensions_and_progress_validation(self):
        np.testing.assert_array_equal(self.scene.render(-1, 400, 320), self.scene.render(0, 400, 320))
        np.testing.assert_array_equal(self.scene.render(2, 400, 320), self.scene.render(1, 400, 320))
        for args in ((0, 0, 320), (0, 400, -1), (float("nan"), 400, 320)):
            with self.assertRaises(ValueError):
                self.scene.render(*args)


if __name__ == "__main__":
    unittest.main()
