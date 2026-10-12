"""A reversible flower: every layer is a pure function of progress and size."""
from functools import lru_cache
import math

import cv2
import numpy as np


def ease(value):
    value = float(np.clip(value, 0, 1))
    return value * value * (3 - 2 * value)


@lru_cache(maxsize=3)
def background(width, height):
    y, x = np.mgrid[:height, :width].astype(np.float32)
    t = (y / max(1, height - 1))[..., None]
    top = np.array((216, 233, 231), dtype=np.float32)
    bottom = np.array((153, 188, 166), dtype=np.float32)
    light = np.exp(-(((x-width*.52)/(width*.38))**2 + ((y-height*.30)/(height*.60))**2))[..., None]
    image = np.clip(top * (1-t) + bottom * t + light * 13, 0, 255).astype(np.uint8)
    haze = np.zeros_like(image)
    for i in range(12):
        cx = int(width * (.08 + .84 * ((i * .61803398875) % 1)))
        cy = int(height * (.12 + .76 * ((i * .41421356237) % 1)))
        radius = max(3, round(min(width, height) * (.014 + (i % 3) * .009)))
        cv2.circle(haze, (cx, cy), radius, (15, 19, 17), -1, cv2.LINE_AA)
    haze = cv2.GaussianBlur(haze, (0, 0), max(1, min(width, height) * .012))
    image = cv2.add(image, haze)
    image.flags.writeable = False
    return image


def blend_patch(layer, mask, color, left, top):
    """Premultiplied source-over, matching the painter's existing alpha layers."""
    h, w = mask.shape
    target = layer[top:top+h, left:left+w]
    coverage = mask.astype(np.uint16)
    inverse = 255 - coverage
    foreground = (color.astype(np.uint16) * coverage[..., None] + 127) // 255
    target[..., :3] = np.minimum(255, foreground +
        (target[..., :3].astype(np.uint16) * inverse[..., None] + 127) // 255).astype(np.uint8)
    target[..., 3] = np.minimum(255, coverage +
        (target[..., 3].astype(np.uint16) * inverse + 127) // 255).astype(np.uint8)


def petal(layer, root, angle, length, half_width, base_color, tip_color, curve=0):
    """An individual hinged petal with a shaded almond outline, not a scaled sprite."""
    direction = np.array((math.cos(angle), math.sin(angle)))
    normal = np.array((-direction[1], direction[0]))
    u = np.linspace(0, 1, 35)
    center = np.asarray(root) + u[:, None] * length * direction + (np.sin(np.pi*u) * curve)[:, None] * normal
    width = np.sin(np.pi*u) ** .72 * half_width
    polygon = np.vstack((center + width[:, None] * normal, (center - width[:, None] * normal)[::-1]))
    height, image_width = layer.shape[:2]
    left, top = max(0, math.floor(polygon[:, 0].min())-2), max(0, math.floor(polygon[:, 1].min())-2)
    right, bottom = min(image_width, math.ceil(polygon[:, 0].max())+3), min(height, math.ceil(polygon[:, 1].max())+3)
    if left >= right or top >= bottom:
        return
    local = np.rint(polygon - (left, top)).astype(np.int32)
    mask = np.zeros((bottom-top, right-left), np.uint8)
    cv2.fillPoly(mask, [local], 255, cv2.LINE_AA)
    y, x = np.mgrid[top:bottom, left:right].astype(np.float32)
    dx, dy = x - root[0], y - root[1]
    distance = np.clip((dx*direction[0] + dy*direction[1]) / max(1, length), 0, 1)
    sideways = np.abs(dx*normal[0] + dy*normal[1]) / max(1, half_width)
    tint = np.clip(distance * .85 + np.exp(-sideways**2 * 4) * .13, 0, 1)[..., None]
    color = np.clip(np.asarray(base_color) * (1-tint) + np.asarray(tip_color) * tint, 0, 255).astype(np.uint8)
    blend_patch(layer, mask, color, left, top)


class FlowerAnimation:
    def render_layers(self, progress, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("动画尺寸必须为正数")
        progress = float(progress)
        if not math.isfinite(progress):
            raise ValueError("动画进度必须是有限数值")
        progress = float(np.clip(progress, 0, 1))
        bg = background(width, height)
        flower = np.zeros((height, width, 4), np.uint8)
        scale = min(width / 700, height / 470)
        cx, cy = width * .5, height * .39
        # Stem and leaves occupy a separate foreground layer from the garden.
        u = np.linspace(0, 1, 45)
        stem = np.stack((cx - np.sin(u*np.pi*.8) * 17 * scale,
                         cy + 34*scale + u * (height*.94 - cy - 34*scale)), axis=1)
        stem = np.rint(stem).astype(np.int32)
        cv2.polylines(flower, [stem], False, (55, 119, 63, 255), max(2, round(8*scale)), cv2.LINE_AA)
        cv2.polylines(flower, [stem + (2, 0)], False, (83, 149, 91, 255), max(1, round(3*scale)), cv2.LINE_AA)
        for root, angle, length, breadth, bend in (
            ((cx-10*scale, cy+150*scale), -2.65, 128, 24, -8),
            ((cx-16*scale, cy+110*scale), -.44, 109, 21, 7),
        ):
            petal(flower, root, angle, length*scale, breadth*scale,
                  (41, 96, 46), (108, 172, 108), bend*scale)
            end = np.asarray(root) + np.array((math.cos(angle), math.sin(angle))) * length * scale * .82
            cv2.line(flower, tuple(np.rint(root).astype(int)), tuple(np.rint(end).astype(int)),
                     (68, 131, 69, 255), max(1, round(scale)), cv2.LINE_AA)
        rows = ((12, 143, 34, 0, 1, .10), (10, 111, 31, .06, .94, .27), (8, 79, 26, .15, .85, .48))
        for row, (count, target_length, target_width, start, duration, phase) in enumerate(rows):
            opening = ease((progress-start)/duration)
            for i in range(count):
                theta = -math.pi/2 + 2*math.pi*i/count + phase
                turn = (theta + math.pi/2 + math.pi) % (2*math.pi) - math.pi
                angle = -math.pi/2 + turn*opening
                variation = 1 + .035*math.sin(i*2.4 + row)
                length = (70 - row*8 + (target_length - 70 + row*8)*opening) * variation * scale
                breadth = (11-row + (target_width-11+row)*opening) * scale
                root = (cx + math.cos(theta) * (5 + 6*opening)*scale,
                        cy + 34*(1-opening)*scale + math.sin(theta)*5*opening*scale)
                base = (68+row*8, 37+row*7, 157+row*15)
                tip = (161+row*13, 154+row*11, 245)
                petal(flower, root, angle, length, breadth, base, tip,
                      math.sin(theta*2) * 5*opening*scale)
        # The protective calyx opens independently, exposing the petal bases.
        opening = ease(progress)
        for i in range(5):
            angle = -math.pi/2 + (i-2) * (.15 + .42*opening)
            petal(flower, (cx + (i-2)*3*scale, cy+39*scale), angle,
                  (42-18*opening)*scale, (5+2*opening)*scale,
                  (43, 105, 48), (91, 152, 88))
        center_visibility = ease((progress-.46)/.54)
        if center_visibility > 0:
            center = (round(cx), round(cy))
            radius = max(1, round((3 + 16*center_visibility)*scale))
            mask = np.zeros((height, width), np.uint8)
            cv2.circle(mask, center, radius, round(255*center_visibility), -1, cv2.LINE_AA)
            left, top = max(0, center[0]-radius-2), max(0, center[1]-radius-2)
            right, bottom = min(width, center[0]+radius+3), min(height, center[1]+radius+3)
            color = np.full((bottom-top, right-left, 3), (52, 173, 226), np.uint8)
            blend_patch(flower, mask[top:bottom, left:right], color, left, top)
            pollen = np.zeros((bottom-top, right-left), np.uint8)
            for i in range(30):
                angle = i * 2.39996323
                r = math.sqrt((i+.5)/30) * radius * .86
                point = (round(cx+math.cos(angle)*r), round(cy+math.sin(angle)*r))
                # Pollen is sampled from progress; no particles accumulate.
                cv2.circle(pollen, (point[0]-left, point[1]-top), max(1, round(scale)),
                           round(255*center_visibility), -1, cv2.LINE_AA)
            pollen_color = np.full((bottom-top, right-left, 3), (99, 215, 254), np.uint8)
            blend_patch(flower, pollen, pollen_color, left, top)
        return bg, flower

    @lru_cache(maxsize=4)
    def _frame(self, progress, width, height):
        bg, flower = self.render_layers(progress, width, height)
        inverse = (255-flower[..., 3]).astype(np.uint16)[..., None]
        frame = np.minimum(255, flower[..., :3].astype(np.uint16) +
                           (bg.astype(np.uint16) * inverse + 127)//255).astype(np.uint8)
        frame.flags.writeable = False
        return frame

    def render(self, progress, width, height):
        # Memoisation is keyed only by the requested state, never by frame order.
        # Return an owned image so callers cannot corrupt cached animation states.
        return self._frame(float(progress), int(width), int(height)).copy()
