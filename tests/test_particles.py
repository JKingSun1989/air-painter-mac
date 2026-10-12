import random
import unittest

import numpy as np

from particles import Particles


class ParticleTests(unittest.TestCase):
    def test_capacity_is_strict_and_sparks_expire_by_elapsed_time(self):
        particles = Particles(max_particles=3, rng=random.Random(1))
        self.assertEqual(particles.spawn((100, 100), (0, 0, 255)), 2)
        self.assertEqual(particles.spawn((100, 100), (0, 0, 255)), 1)
        self.assertEqual(particles.spawn((100, 100), (0, 0, 255)), 0)
        particles.update(.8)
        self.assertFalse(particles.items)

    def test_stationary_emission_is_not_tied_to_frame_rate(self):
        totals = []
        for fps in (15, 30, 60):
            particles = Particles(rng=random.Random(2))
            emitted = 0
            for _ in range(fps):
                particles.update(1/fps)
                emitted += particles.follow((100, 100), (0, 200, 0), 1/fps)
            totals.append(emitted)
        self.assertLessEqual(max(totals) - min(totals), 2)

    def test_lifts_and_tracking_jumps_do_not_create_particle_bridges(self):
        particles = Particles(rng=random.Random(3))
        particles.follow((50, 100), (255, 0, 0), .06)
        particles.follow(None, (255, 0, 0), .06)
        before = len(particles.items)
        embers_before = len(particles.embers)
        particles.follow((140, 100), (255, 0, 0), .06)
        self.assertTrue(all(abs(p["pos"][0] - 140) <= 5 for p in particles.items[before:]))
        self.assertTrue(all(abs(p["pos"][0] - 140) <= 3 for p in particles.embers[embers_before:]))
        before = len(particles.items)
        embers_before = len(particles.embers)
        particles.follow((500, 100), (255, 0, 0), .06)
        self.assertTrue(all(abs(p["pos"][0] - 500) <= 5 for p in particles.items[before:]))
        self.assertTrue(all(abs(p["pos"][0] - 500) <= 3 for p in particles.embers[embers_before:]))

    def test_sparks_move_and_fade_without_touching_other_layers(self):
        particles = Particles(rng=random.Random(4))
        particles.spawn((100, 100), (0, 0, 255), count=6)
        positions = [p["pos"] for p in particles.items]
        fresh = particles.draw(np.zeros((240, 320, 3), np.uint8))
        particles.update(.2)
        aged = particles.draw(np.zeros_like(fresh))
        self.assertNotEqual(positions, [p["pos"] for p in particles.items])
        self.assertGreater(fresh.sum(), aged.sum())
        self.assertGreater(aged.sum(), 0)
        particles.clear()
        clean = np.zeros_like(fresh)
        np.testing.assert_array_equal(particles.draw(clean), clean)
        self.assertIsNone(particles.previous)

    def test_render_is_clipped_to_drawing_area(self):
        particles = Particles(rng=random.Random(5))
        particles.spawn((120, 101), (0, 0, 255), count=20)
        particles.spawn_embers((120, 101), count=10)
        frame = np.full((240, 320, 3), 55, np.uint8)
        before = frame.copy()
        particles.draw(frame, bounds=(121, 101, 320, 210))
        np.testing.assert_array_equal(frame[:, :121], before[:, :121])
        np.testing.assert_array_equal(frame[:101], before[:101])
        np.testing.assert_array_equal(frame[210:], before[210:])
        self.assertTrue(np.any(frame != before))

    def test_sparks_and_embers_share_capacity_and_clear_together(self):
        particles = Particles(max_particles=4, rng=random.Random(6))
        particles.spawn((100, 100), (255, 0, 0), count=2)
        self.assertEqual(particles.spawn_embers((100, 100), count=10), 2)
        self.assertEqual(particles.spawn((100, 100), (255, 0, 0)), 0)
        self.assertEqual(particles.spawn_embers((100, 100)), 0)
        self.assertEqual(len(particles.items) + len(particles.embers), 4)
        particles.update(1)
        self.assertFalse(particles.items or particles.embers)
        particles.follow((100, 100), (0, 200, 0), .06)
        particles.clear()
        self.assertFalse(particles.items or particles.embers)
        self.assertEqual(particles.ember_credit, 0)

    def test_embers_have_warm_trails_and_fall_before_expiring(self):
        particles = Particles(rng=random.Random(7))
        particles.spawn_embers((160, 120), count=1)
        original = dict(particles.embers[0])
        frame = particles.draw(np.zeros((300, 400, 3), np.uint8))
        self.assertGreater(np.count_nonzero(np.any(frame, axis=2)), 10)
        self.assertGreater(frame[..., 2].sum(), frame[..., 1].sum())
        self.assertGreater(frame[..., 1].sum(), frame[..., 0].sum())
        particles.update(.2)
        ember = particles.embers[0]
        self.assertGreater(ember["velocity"][1], original["velocity"][1])
        self.assertGreater(ember["pos"][1], original["pos"][1] + original["velocity"][1] * .2)
        faded = particles.draw(np.zeros_like(frame))
        self.assertGreater(frame.sum(), faded.sum())
        particles.update(1)
        self.assertFalse(particles.embers)


if __name__ == "__main__":
    unittest.main()
