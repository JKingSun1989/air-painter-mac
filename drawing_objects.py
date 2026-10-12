"""Immutable cropped raster objects; positions change without resampling pixels.

Point-to-segment projection adapted from medhanshcodezz/air-canvas
(MIT, Copyright (c) 2026 Medhansh Mittal). See third_party/air-canvas-LICENSE.
"""
from dataclasses import dataclass, replace

import cv2
import numpy as np


def segment_distances(points, a, b):
    """air-canvas's clamped projection, including zero-length segments."""
    points = np.asarray(points, dtype=np.float64)
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    span = b - a
    denominator = float(np.dot(span, span))
    if denominator <= 0:
        return np.linalg.norm(points - a, axis=1)
    t = np.clip(((points - a) @ span) / denominator, 0.0, 1.0)
    return np.linalg.norm(points - (a + t[:, None] * span), axis=1)


@dataclass(frozen=True, eq=False)
class DrawingObject:
    id: int
    x: int
    y: int
    color: np.ndarray
    alpha: np.ndarray
    contours: tuple

    @classmethod
    def from_layer(cls, object_id, color, alpha, origin=(0, 0)):
        pixels = cv2.findNonZero(alpha)
        if pixels is None:
            return None
        x, y, w, h = cv2.boundingRect(pixels)
        color, alpha = color[y:y+h, x:x+w].copy(), alpha[y:y+h, x:x+w].copy()
        contours, _ = cv2.findContours(alpha, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        color.flags.writeable = alpha.flags.writeable = False
        outlines = tuple(contour.reshape(-1, 2) for contour in contours)
        for contour in outlines:
            contour.flags.writeable = False
        return cls(object_id, origin[0] + x, origin[1] + y, color, alpha, outlines)

    @property
    def bounds(self):
        h, w = self.alpha.shape
        return self.x, self.y, self.x + w, self.y + h

    def moved(self, x, y):
        return replace(self, x=int(x), y=int(y))

    def hit(self, point, tolerance=18):
        x, y = np.asarray(point, dtype=float) - (self.x, self.y)
        h, w = self.alpha.shape
        if x < -tolerance or y < -tolerance or x > w + tolerance or y > h + tolerance:
            return False
        if 0 <= x < w and 0 <= y < h and self.alpha[int(y), int(x)] > 0:
            return True
        # Distance to visible stroke boundaries, including erased holes. An
        # empty circle's centre is not a hit just because it is in its box.
        probe = np.array([[x, y]])
        for outline in self.contours:
            if len(outline) == 1:
                if np.linalg.norm(probe[0] - outline[0]) <= tolerance:
                    return True
            else:
                for a, b in zip(outline, np.roll(outline, -1, axis=0)):
                    if segment_distances(probe, a, b)[0] <= tolerance:
                        return True
        return False


def paste_layer(canvas, alpha, obj):
    """Premultiplied source-over; integer translations preserve edge pixels."""
    h, w = canvas.shape[:2]
    x1, y1, x2, y2 = obj.bounds
    left, top, right, bottom = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if left >= right or top >= bottom:
        return
    source = np.s_[top-y1:bottom-y1, left-x1:right-x1]
    target = np.s_[top:bottom, left:right]
    inverse = (255 - obj.alpha[source]).astype(np.uint16)
    canvas[target] = np.minimum(255, obj.color[source].astype(np.uint16) +
        (canvas[target].astype(np.uint16) * inverse[..., None] + 127) // 255).astype(np.uint8)
    alpha[target] = np.minimum(255, obj.alpha[source].astype(np.uint16) +
        (alpha[target].astype(np.uint16) * inverse + 127) // 255).astype(np.uint8)
