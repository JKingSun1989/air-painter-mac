"""Preview-only sparks, adapted from the upstream painter's particle system."""

import random
import math
import cv2
import numpy as np


class Particles:
    def __init__(self, max_particles: int = 180, rng=None):
        self.items = []
        self.embers = []
        self.max_particles = max_particles
        self.rng = rng or random.Random()
        self.previous = None
        self.emission_credit = 0.0
        self.ember_credit = 0.0

    def spawn(self, pos, color, count=2):
        count = min(count, max(0, self.max_particles - len(self.items) - len(self.embers)))
        for _ in range(count):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(18, 52)
            lifetime = self.rng.uniform(.40, .75)
            self.items.append({
                "pos": (pos[0] + self.rng.uniform(-5, 5), pos[1] + self.rng.uniform(-5, 5)),
                "velocity": (math.cos(angle) * speed, math.sin(angle) * speed - 10),
                "color": tuple(color),
                "life": lifetime,
                "max_life": lifetime,
                "radius": self.rng.randint(2, 4),
                "sparkle": self.rng.random() < .3,
            })
        return count

    def spawn_embers(self, pos, count=1):
        count = min(count, max(0, self.max_particles - len(self.items) - len(self.embers)))
        for _ in range(count):
            angle = self.rng.uniform(-math.pi - .3, .3)
            speed = self.rng.uniform(65, 145)
            lifetime = self.rng.uniform(.50, .85)
            self.embers.append({
                "pos": (pos[0] + self.rng.uniform(-3, 3), pos[1] + self.rng.uniform(-3, 3)),
                "velocity": (math.cos(angle) * speed, math.sin(angle) * speed - 15),
                "gravity": self.rng.uniform(110, 180),
                "life": lifetime,
                "max_life": lifetime,
                "radius": self.rng.randint(1, 2),
                "trail": self.rng.uniform(5, 11),
            })
        return count

    def reset_emitter(self):
        self.previous = None
        self.emission_credit = 0.0
        self.ember_credit = 0.0

    def clear(self):
        self.items.clear()
        self.embers.clear()
        self.reset_emitter()

    def follow(self, point, color, dt):
        if point is None:
            self.reset_emitter()
            return 0
        point = np.asarray(point, dtype=float)
        previous = self.previous
        # Never sprinkle a bridge across separate strokes or tracking jumps.
        if previous is None or np.linalg.norm(point - previous) > 150:
            previous = point
        self.emission_credit += max(0, min(dt, .1)) * 90
        timed = int(self.emission_credit)
        self.emission_credit -= timed
        distance = float(np.linalg.norm(point - previous))
        count = min(14, max(timed, math.ceil(distance / 10)))
        if self.previous is None:
            count = max(2, count)
        emitted = 0
        for i in range(count):
            position = previous + (point - previous) * ((i + 1) / count)
            emitted += self.spawn(position, color, count=1)
        self.ember_credit += max(0, min(dt, .1)) * 65
        timed_embers = int(self.ember_credit)
        self.ember_credit -= timed_embers
        count_embers = min(8, max(timed_embers, math.floor(distance / 14)))
        for i in range(count_embers):
            position = previous + (point - previous) * ((i + 1) / count_embers)
            emitted += self.spawn_embers(position)
        self.previous = point
        return emitted

    def update(self, dt):
        dt = max(0, dt)
        alive = []
        for p in self.items:
            p["life"] -= dt
            if p["life"] > 0:
                vx, vy = p["velocity"]
                x, y = p["pos"]
                p["pos"] = (x + vx * dt, y + vy * dt)
                p["velocity"] = (vx, vy + 20 * dt)
                alive.append(p)
        self.items = alive
        alive_embers = []
        for ember in self.embers:
            ember["life"] -= dt
            if ember["life"] > 0:
                vx, vy = ember["velocity"]
                x, y = ember["pos"]
                gravity = ember["gravity"]
                ember["pos"] = (x + vx * dt, y + vy * dt + .5 * gravity * dt * dt)
                ember["velocity"] = (vx, vy + gravity * dt)
                alive_embers.append(ember)
        self.embers = alive_embers

    def draw(self, frame, bounds=None):
        height, width = frame.shape[:2]
        left, top, right, bottom = bounds or (0, 0, width, height)
        left, top, right, bottom = max(0, left), max(0, top), min(width, right), min(height, bottom)
        for p in self.items:
            fade = (p["life"] / p["max_life"]) ** 2
            radius = max(1, round(p["radius"] * (.5 + .5 * fade)))
            reach = radius * 3 + 3
            x, y = (round(value) for value in p["pos"])
            x1, y1, x2, y2 = max(left, x - reach), max(top, y - reach), min(right, x + reach + 1), min(bottom, y + reach + 1)
            if x1 >= x2 or y1 >= y2:
                continue
            # Blend only the tiny spark region, rather than copy the entire
            # 1100x720 frame for every particle as the original effect did.
            patch = np.zeros((reach * 2 + 1, reach * 2 + 1, 3), np.uint8)
            center = (reach, reach)
            hue = np.asarray(p["color"], dtype=float)
            glow = tuple(int(value) for value in hue * .25 * fade)
            cv2.circle(patch, center, radius * 3, glow, -1, cv2.LINE_AA)
            patch = cv2.GaussianBlur(patch, (5, 5), 0)
            core = tuple(int(value) for value in (hue * .65 + 255 * .35) * fade)
            cv2.circle(patch, center, radius, core, -1, cv2.LINE_AA)
            if p["sparkle"]:
                bright = (round(240 * fade),) * 3
                cv2.line(patch, (reach-radius-2, reach), (reach+radius+2, reach), bright, 1, cv2.LINE_AA)
                cv2.line(patch, (reach, reach-radius-2), (reach, reach+radius+2), bright, 1, cv2.LINE_AA)
            source = patch[y1-(y-reach):y2-(y-reach), x1-(x-reach):x2-(x-reach)]
            target = frame[y1:y2, x1:x2]
            cv2.add(target, source, dst=target)
        for ember in self.embers:
            remaining = ember["life"] / ember["max_life"]
            fade = remaining ** 1.4
            radius = ember["radius"]
            reach = 15
            x, y = (round(value) for value in ember["pos"])
            x1, y1, x2, y2 = max(left, x-reach), max(top, y-reach), min(right, x+reach+1), min(bottom, y+reach+1)
            if x1 >= x2 or y1 >= y2:
                continue
            patch = np.zeros((31, 31, 3), np.uint8)
            center = np.array((reach, reach))
            velocity = np.asarray(ember["velocity"], dtype=float)
            direction = velocity / max(1, float(np.linalg.norm(velocity)))
            tail = center - direction * ember["trail"] * (.4 + .6 * remaining)
            # Warm gold cools to orange-red, independent of the pen colour.
            hue = np.array((35 * remaining, 70 + 150 * remaining, 255))
            glow = tuple(int(value) for value in hue * .2 * fade)
            cv2.circle(patch, tuple(center), radius * 3, glow, -1, cv2.LINE_AA)
            patch = cv2.GaussianBlur(patch, (5, 5), 0)
            for step in range(4):
                a, b = step / 4, (step + 1) / 4
                start = tuple(np.rint(tail + (center - tail) * a).astype(int))
                end = tuple(np.rint(tail + (center - tail) * b).astype(int))
                color = tuple(int(value) for value in hue * fade * (.2 + .8 * b))
                cv2.line(patch, start, end, color, 1, cv2.LINE_AA)
            core = tuple(int(value) for value in hue * fade)
            cv2.circle(patch, tuple(center), radius, core, -1, cv2.LINE_AA)
            source = patch[y1-(y-reach):y2-(y-reach), x1-(x-reach):x2-(x-reach)]
            target = frame[y1:y2, x1:x2]
            cv2.add(target, source, dst=target)
        return frame

    def update_and_draw(self, frame, dt=1/30, bounds=None):
        self.update(dt)
        return self.draw(frame, bounds)
