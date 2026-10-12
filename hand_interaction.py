"""Local DRAW / IDLE / DRAG state machine over existing MediaPipe points."""
import numpy as np
from dataclasses import dataclass

from hand_utils import classify_gesture, fingers_up, thumb_extended, dist

PINCH_CLOSE = .28
PINCH_OPEN = .46
PINCH_DEBOUNCE = .10


@dataclass(frozen=True)
class PinchState:
    closed: bool
    closing: bool = False
    opening: bool = False
    just_closed: bool = False
    just_opened: bool = False
    pending_since: float | None = None


def advance_pinch(ratio, closed, pending_since, now,
                  close=PINCH_CLOSE, open_=PINCH_OPEN, debounce=PINCH_DEBOUNCE):
    """Shared hysteresis/debounce used by object dragging and time scrubbing."""
    closing, opening = not closed and ratio <= close, closed and ratio >= open_
    changed = False
    if closing or opening:
        if pending_since is None:
            pending_since = now
        if now - pending_since >= debounce:
            closed = not closed
            pending_since = None
            changed = True
    else:
        pending_since = None
    return PinchState(closed, closing, opening, changed and closing,
                      changed and opening, pending_since)


def pinch_measurement(points):
    """Pixel-space 4--8 distance normalised by stable palm bones, not fingers."""
    scale = max(dist(points[0], points[9]), dist(points[5], points[17]))
    if scale < 12:
        return None, None
    ratio = dist(points[4], points[8]) / scale
    cursor = tuple((np.asarray(points[4], dtype=float) + points[8]) / 2)
    return ratio, cursor


class HandInteraction:
    CLOSE = PINCH_CLOSE
    OPEN = PINCH_OPEN
    DEBOUNCE = PINCH_DEBOUNCE
    LOSS_TIMEOUT = 0.65
    MAX_JUMP = 150

    def __init__(self, engine, bounds):
        self.engine = engine
        self.bounds = bounds
        self.engine.drag_bounds = bounds
        self.state = "IDLE"
        self.pinched = False
        self.pending_since = None
        self.last_seen = None
        self.last_cursor = None
        self.missing = False
        self.block_draw = False
        self.require_open = False
        self.close_guard = False

    def reset(self, commit=True):
        self.engine.end_drag()
        if commit:
            self.engine.lift()
        self.state = "IDLE"
        # A control action during a pinch must not cause re-grabbing or drawing
        # on the following frame. Require an open, non-drawing gesture first.
        self.block_draw = self.block_draw or self.pinched or self.pending_since is not None
        self.require_open = self.require_open or self.pinched
        self.pending_since = None

    def _release(self):
        self.engine.end_drag()
        self.state = "IDLE"
        self.pinched = False
        self.close_guard = False
        self.pending_since = None
        self.block_draw = True

    def update(self, points, now):
        if points is None:
            self.engine.lift()
            self.pending_since = None
            self.missing = True
            if self.state == "DRAG":
                if self.last_seen is not None and now - self.last_seen >= self.LOSS_TIMEOUT:
                    self._release()
                    self.require_open = True
            else:
                self.state = "IDLE"
            return self.state, None, False

        expired = self.last_seen is not None and now - self.last_seen >= self.LOSS_TIMEOUT
        resumed = self.missing or expired
        if expired and self.state == "DRAG":
            self._release()
            self.require_open = True
        self.last_seen = now
        self.missing = False
        ratio, cursor = pinch_measurement(points)
        gesture = classify_gesture(fingers_up(points), thumb_extended(points))
        if ratio is None or not self.engine.enabled:
            self.reset()
            return self.state, None, gesture == "Select" and ratio is not None and not self.block_draw

        if resumed:
            self.pending_since = None
        if self.require_open:
            self.engine.lift()
            if ratio >= self.OPEN:
                if self.pending_since is None:
                    self.pending_since = now
                if now - self.pending_since >= self.DEBOUNCE:
                    self.require_open = self.pinched = False
                    self.pending_since = None
            else:
                self.pending_since = None
            return "IDLE", None, False
        pinch = advance_pinch(ratio, self.pinched, self.pending_since, now,
                              self.CLOSE, self.OPEN, self.DEBOUNCE)
        closing, opening = pinch.closing, pinch.opening
        self.pending_since = pinch.pending_since
        if closing:
            self.close_guard = True
        if closing or opening:
            self.engine.lift()  # suppress ink even during the close debounce
        if pinch.just_closed:
            self.pinched = True
            self.block_draw = True
            if not expired and self._inside(cursor) and self.engine.begin_drag(cursor):
                self.state = "DRAG"
                self.last_cursor = cursor
        elif pinch.just_opened:
            self._release()

        if self.state == "DRAG":
            jumped = self.last_cursor is not None and np.linalg.norm(np.subtract(cursor, self.last_cursor)) > self.MAX_JUMP
            if resumed or jumped:
                self.engine.reanchor_drag(cursor)
            elif not opening:
                self.engine.move_drag(cursor)
            self.last_cursor = cursor
            return self.state, tuple(int(round(value)) for value in cursor), False

        self.last_cursor = cursor
        if self.pinched or closing:
            self.state = "IDLE"
            return self.state, None, False
        if self.close_guard:
            if ratio >= self.OPEN:
                self.close_guard = False
            self.engine.lift()
            self.state = "IDLE"
            return self.state, None, False
        # Releasing a pinch often leaves an extended index. Require a deliberate
        # pen-up gesture before drawing again, rather than leave a release tail.
        if self.block_draw:
            if gesture != "Draw" and ratio >= self.OPEN:
                self.block_draw = False
            self.engine.lift()
            self.state = "IDLE"
            return self.state, None, False
        if gesture == "Draw" and self._inside(points[8]):
            self.state = "DRAW"
            return self.state, self.engine.draw(points[8]), False
        self.engine.lift()
        self.state = "IDLE"
        return self.state, None, gesture == "Select"

    def _inside(self, point):
        left, top, right, bottom = self.bounds
        return left < point[0] < right and top < point[1] < bottom
