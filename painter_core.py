"""Stroke transactions and floating-point EMA, adapted from the upstream painter."""
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import SMOOTHING_ALPHA, PALETTE, SAVE_DIR
from drawing_objects import DrawingObject, paste_layer

SHAPE_TOOLS = ("line", "rectangle", "ellipse")
TOOLS = ("pen", "eraser", *SHAPE_TOOLS)


class PointSmoother:
    def __init__(self, alpha=SMOOTHING_ALPHA):
        if not 0 < alpha <= 1:
            raise ValueError("Smoothing alpha must be in (0, 1]")
        self.alpha = alpha
        self.point = None

    def reset(self):
        self.point = None

    def update(self, point):
        # Keep fractional coordinates; rounding every frame causes sticky trajectories.
        value = np.asarray(point, dtype=float)
        self.point = value if self.point is None else self.alpha * value + (1 - self.alpha) * self.point
        return tuple(np.rint(self.point).astype(int))


class PaintEngine:
    def __init__(self, width, height, alpha=SMOOTHING_ALPHA, history_limit=30):
        self.canvas = np.zeros((height, width, 3), np.uint8)
        self.alpha = np.zeros((height, width), np.uint8)
        self.enabled = False
        self.tool = "pen"
        self.export_background = "black"
        self.shape_start = self.shape_end = None
        self.color_idx = 0
        self.thickness = 8
        self.history = deque(maxlen=history_limit)
        self.redo_history = deque(maxlen=history_limit)
        self.previous = None
        self.smoother = PointSmoother(alpha)
        self.objects = []
        self.group_mode = False
        self._group_id = None
        self._group_strokes = 0
        self._next_id = 1
        self._stroke_color = self._stroke_alpha = None
        self._stroke_id = None
        self.dragged_id = None
        self._drag_before = None
        self._drag_offset = None
        self._drag_limits = None
        self._drag_smoother = PointSmoother(alpha)
        self.drag_bounds = (0, 0, width, height)

    @property
    def color(self):
        return PALETTE[self.color_idx]["bgr"]

    def lift(self):
        if self.shape_start is not None and self.shape_end is not None:
            if np.linalg.norm(np.subtract(self.shape_end, self.shape_start)) >= 3:
                self.checkpoint()
                self._begin_layer()
                self.render_shape(self._stroke_color, self._stroke_alpha)
        self._commit_layer()
        self.shape_start = self.shape_end = None
        self.previous = None
        self.smoother.reset()

    def _begin_layer(self):
        self._stroke_color = np.zeros_like(self.canvas)
        self._stroke_alpha = np.zeros_like(self.alpha)
        grouped = next((obj for obj in self.objects if obj.id == self._group_id), None)
        if self.group_mode and grouped is not None:
            paste_layer(self._stroke_color, self._stroke_alpha, grouped)
            self._stroke_id = grouped.id
        else:
            self._stroke_id = self._next_id
            self._next_id += 1
            if self.group_mode:
                self._group_id = self._stroke_id

    def _layers(self):
        layers = list(self.objects)
        if self._stroke_alpha is not None:
            obj = DrawingObject.from_layer(self._stroke_id, self._stroke_color, self._stroke_alpha)
            if obj is not None:
                index = next((i for i, item in enumerate(layers) if item.id == obj.id), len(layers))
                if index == len(layers):
                    layers.append(obj)
                else:
                    layers[index] = obj
        return layers

    def _commit_layer(self):
        if self._stroke_alpha is not None:
            self.objects = self._layers()
            if self.group_mode and any(obj.id == self._stroke_id for obj in self.objects):
                self._group_strokes += 1
            self._stroke_color = self._stroke_alpha = self._stroke_id = None
            self.recompose()

    def recompose(self):
        self.canvas.fill(0)
        self.alpha.fill(0)
        for obj in self.objects:
            paste_layer(self.canvas, self.alpha, obj)

    def finish_object(self):
        self.lift()
        object_id = self._group_id if self.group_mode else self.objects[-1].id if self.objects else None
        completed = next((obj for obj in self.objects if obj.id == object_id), None)
        self._group_id = None
        self._group_strokes = 0
        return completed

    @property
    def group_strokes(self):
        pending = self._stroke_alpha is not None and self._stroke_id == self._group_id and np.any(self._stroke_alpha)
        return self._group_strokes + int(pending)

    @property
    def active_group(self):
        return next((obj for obj in self.objects if obj.id == self._group_id), None)

    def set_group_mode(self, enabled):
        self.finish_object()
        self.group_mode = bool(enabled)

    def begin_drag(self, point):
        if not self.enabled or self.dragged_id is not None:
            return False
        self.finish_object()
        obj = next((obj for obj in reversed(self.objects) if obj.hit(point)), None)
        if obj is None:
            return False
        self._drag_before = self.snapshot()
        self.dragged_id = obj.id
        self._drag_smoother.alpha = self.smoother.alpha
        self._drag_smoother.reset()
        anchor = self._drag_smoother.update(point)
        self._drag_offset = np.array((obj.x, obj.y), dtype=float) - anchor
        left, top, right, bottom = self.drag_bounds
        h, w = obj.alpha.shape
        # Allow an existing brush edge crossing the toolbar boundary to stay
        # exactly where it is at grab time, including oversized grouped objects.
        self._drag_limits = (min(left, obj.x), min(top, obj.y),
                             max(right - w, obj.x), max(bottom - h, obj.y))
        return True

    def reanchor_drag(self, point):
        obj = next((obj for obj in self.objects if obj.id == self.dragged_id), None)
        if obj is not None:
            self._drag_smoother.reset()
            anchor = self._drag_smoother.update(point)
            self._drag_offset = np.array((obj.x, obj.y), dtype=float) - anchor

    def move_drag(self, point):
        if self.dragged_id is None:
            return
        point = np.array(self._drag_smoother.update(point)) + self._drag_offset
        for i, obj in enumerate(self.objects):
            if obj.id == self.dragged_id:
                left, top, right, bottom = self._drag_limits
                x = round(float(np.clip(point[0], left, right)))
                y = round(float(np.clip(point[1], top, bottom)))
                if (obj.x, obj.y) != (x, y):
                    self.objects[i] = obj.moved(x, y)
                    self.recompose()
                break

    def end_drag(self):
        if self.dragged_id is not None:
            before = self._drag_before[2]
            original = next(obj for obj in before if obj.id == self.dragged_id)
            current = next(obj for obj in self.objects if obj.id == self.dragged_id)
            if (original.x, original.y) != (current.x, current.y):
                self.history.append(self._drag_before)
                self.redo_history.clear()
        self.dragged_id = self._drag_before = self._drag_offset = None
        self._drag_limits = None
        self._drag_smoother.reset()

    def set_enabled(self, enabled):
        self.end_drag()
        self.lift()
        self.enabled = bool(enabled)

    def select_color(self, index):
        if not 0 <= index < len(PALETTE):
            raise ValueError("Invalid palette index")
        self.end_drag()
        self.lift()
        self.color_idx = index
        if self.tool == "eraser":
            self.tool = "pen"

    def set_tool(self, tool):
        if tool not in TOOLS:
            raise ValueError("Invalid drawing tool")
        self.end_drag()
        self.lift()
        self.tool = tool

    def set_smoothing(self, value):
        if not 0 < value <= 1:
            raise ValueError("Smoothing alpha must be in (0, 1]")
        self.end_drag()
        self.lift()
        self.smoother.alpha = value

    def render_shape(self, canvas, alpha):
        start, end = self.shape_start, self.shape_end
        if start is None or end is None:
            return
        for image, color in ((canvas, self.color), (alpha, 255)):
            if self.tool == "line":
                cv2.line(image, start, end, color, self.thickness, cv2.LINE_AA)
            elif self.tool == "rectangle":
                cv2.rectangle(image, start, end, color, self.thickness, cv2.LINE_AA)
            elif self.tool == "ellipse":
                center = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                axes = (max(1, abs(start[0] - end[0]) // 2), max(1, abs(start[1] - end[1]) // 2))
                cv2.ellipse(image, center, axes, 0, 0, 360, color, self.thickness, cv2.LINE_AA)

    def cancel_preview(self):
        self._commit_layer()
        self.shape_start = self.shape_end = None
        self.previous = None
        self.smoother.reset()

    @property
    def brush_width(self):
        return max(18, self.thickness * 3) if self.tool == "eraser" else self.thickness

    def snapshot(self):
        return self.canvas.copy(), self.alpha.copy(), tuple(self._layers())

    def restore(self, snapshot):
        self.canvas[:], self.alpha[:] = snapshot[:2]
        self.objects = list(snapshot[2])
        self._stroke_color = self._stroke_alpha = self._stroke_id = None
        self._group_id = None
        self._group_strokes = 0

    def checkpoint(self):
        self.history.append(self.snapshot())
        self.redo_history.clear()

    def draw(self, raw_point, smooth=True):
        if self.dragged_id is not None:
            return None
        if not self.enabled:
            self.lift()
            return None
        # Break a stroke on tracking jumps rather than drawing a stray bridge.
        if smooth and self.previous is not None and np.linalg.norm(np.subtract(raw_point, self.previous)) > 150:
            if self.tool in SHAPE_TOOLS:
                self.cancel_preview()
            self.lift()
        point = self.smoother.update(raw_point) if smooth else tuple(map(int, raw_point))
        if self.tool in SHAPE_TOOLS:
            if self.shape_start is None:
                self.shape_start = point
            self.shape_end = point
            self.previous = point
            return point
        if self.tool == "eraser" and not np.any(self.alpha):
            self.lift()
            return point
        color = (0, 0, 0) if self.tool == "eraser" else self.color
        coverage = 0 if self.tool == "eraser" else 255
        width = self.brush_width
        if self.previous is None:
            self.checkpoint()
            if self.tool != "eraser":
                self._begin_layer()
        if self.tool == "eraser":
            self._erase(point, width)
        else:
            for image, value in ((self._stroke_color, color), (self._stroke_alpha, coverage)):
                if self.previous is None:
                    cv2.circle(image, point, max(1, width // 2), value, -1, cv2.LINE_AA)
                else:
                    cv2.line(image, self.previous, point, value, width, cv2.LINE_AA)
            self._refresh_stroke(point, width)
        self.previous = point
        return point

    def _refresh_stroke(self, point, width):
        """Use the same layer composition before/after lift, in a small region.

        Drawing straight onto the flat canvas and then recomposing objects used
        two different antialiasing paths, changing overlap pixels at lift/TIME.
        """
        previous = self.previous if self.previous is not None else point
        margin = width + 3
        height, image_width = self.alpha.shape
        left, top = max(0, min(point[0], previous[0])-margin), max(0, min(point[1], previous[1])-margin)
        right, bottom = min(image_width, max(point[0], previous[0])+margin+1), min(height, max(point[1], previous[1])+margin+1)
        if left >= right or top >= bottom:
            return
        canvas, alpha = self.canvas[top:bottom, left:right], self.alpha[top:bottom, left:right]
        canvas.fill(0)
        alpha.fill(0)
        pending = DrawingObject(self._stroke_id, -left, -top, self._stroke_color, self._stroke_alpha, ())
        replaced = False
        for obj in self.objects:
            if obj.id == self._stroke_id:
                paste_layer(canvas, alpha, pending)
                replaced = True
            else:
                paste_layer(canvas, alpha, obj.moved(obj.x-left, obj.y-top))
        if not replaced:
            paste_layer(canvas, alpha, pending)

    def _erase(self, point, width):
        layers = []
        for obj in self.objects:
            color, alpha = obj.color.copy(), obj.alpha.copy()
            local = (point[0] - obj.x, point[1] - obj.y)
            previous = None if self.previous is None else (self.previous[0] - obj.x, self.previous[1] - obj.y)
            for image, value in ((color, (0, 0, 0)), (alpha, 0)):
                if previous is None:
                    cv2.circle(image, local, max(1, width // 2), value, -1, cv2.LINE_AA)
                else:
                    cv2.line(image, previous, local, value, width, cv2.LINE_AA)
            if np.array_equal(alpha, obj.alpha):
                layers.append(obj)
            else:
                erased = DrawingObject.from_layer(obj.id, color, alpha, (obj.x, obj.y))
                if erased is not None:
                    layers.append(erased)
        self.objects = layers
        self.recompose()

    def clear(self):
        self.end_drag()
        self.finish_object()
        if np.any(self.alpha):
            self.checkpoint()
            self.canvas.fill(0)
            self.alpha.fill(0)
            self.objects.clear()

    def undo(self):
        self.end_drag()
        self.finish_object()
        if self.history:
            self.redo_history.append(self.snapshot())
            self.restore(self.history.pop())
            return True
        return False

    def redo(self):
        self.end_drag()
        self.finish_object()
        if self.redo_history:
            self.history.append(self.snapshot())
            self.restore(self.redo_history.pop())
            return True
        return False

    def composite(self, frame):
        # Premultiplied color + coverage gives smooth edges over the live preview.
        canvas, alpha = self.canvas, self.alpha
        if self.shape_start is not None:
            canvas, alpha = self.snapshot()[:2]
            self.render_shape(canvas, alpha)
        inverse_alpha = (255 - alpha).astype(np.uint16)[..., None]
        frame[:] = np.minimum(255, canvas.astype(np.uint16) +
                              (frame.astype(np.uint16) * inverse_alpha + 127) // 255).astype(np.uint8)
        return frame

    def export(self, transparent=False):
        if not transparent:
            if self.export_background == "black":
                return self.canvas.copy()
            inverse_alpha = (255 - self.alpha).astype(np.uint16)[..., None]
            return np.minimum(255, self.canvas.astype(np.uint16) + inverse_alpha).astype(np.uint8)
        # PNG stores straight (not premultiplied) color; unpremultiply edge pixels.
        color = np.zeros_like(self.canvas)
        covered = self.alpha > 0
        color[covered] = np.minimum(255, np.rint(self.canvas[covered].astype(float) *
                                    255 / self.alpha[covered, None])).astype(np.uint8)
        return np.dstack((color, self.alpha))

    def save(self, directory=SAVE_DIR, transparent=False):
        self.end_drag()
        self.lift()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        prefix = "painting_transparent_" if transparent else "painting_white_" if self.export_background == "white" else "painting_"
        filename = directory / (prefix + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png")
        # Export only the drawing, on black, without camera frames or interface chrome.
        try:
            success = cv2.imwrite(str(filename), self.export(transparent))
        except cv2.error as exc:
            raise OSError(f"无法保存图片：{filename}：{exc}") from exc
        if not success:
            raise OSError(f"无法保存图片：{filename}")
        return filename
