"""Single-hand reversible time control from thumb/index opening, without IO."""
from dataclasses import dataclass
import math

import numpy as np

from hand_interaction import (HandInteraction, PinchState, advance_pinch,
                              pinch_measurement, PINCH_CLOSE, PINCH_OPEN,
                              PINCH_DEBOUNCE)
from painter_core import PointSmoother


@dataclass(frozen=True)
class TimeControlState:
    progress: float
    dragging: bool
    state: str
    cursor: tuple | None = None


class GestureTimeController:
    LOSS_TIMEOUT = HandInteraction.LOSS_TIMEOUT
    # PINCH_OPEN is the release threshold, not a fully open hand. Map the
    # complete thumb/index spread (relative to the palm) to the whole animation.
    FULL_OPEN = 1.15
    RATIO_DEADBAND = .01

    def __init__(self, smoothing=.45, progress=0):
        self.smoother = PointSmoother(smoothing)
        self.progress = self._clamp(progress)
        self.dragging = False
        self.state = "INACTIVE"
        self.pinched = False
        self.pending_since = None
        self.require_open = False
        self.last_seen = None
        self.last_cursor = None
        self.missing = False
        self.last_ratio = None
        self.endpoint_since = None
        self.endpoint = None

    @staticmethod
    def _clamp(value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("时间进度必须是有限数值")
        return float(np.clip(value, 0, 1))

    def release(self, require_open=False):
        self.dragging = False
        self.pinched = False
        self.pending_since = None
        self.last_ratio = None
        self.endpoint_since = self.endpoint = None
        self.smoother.reset()
        self.require_open = bool(require_open)
        self.state = "TIME_IDLE"

    def enter(self, require_open=False):
        self.release(require_open)
        self.last_seen = self.last_cursor = None
        self.missing = False

    def reset(self):
        self.progress = 0.0
        self.release()

    def _seed(self):
        self.smoother.reset()
        self.smoother.update((self.progress, 0))

    def _result(self, cursor=None):
        return TimeControlState(self.progress, self.dragging, self.state, cursor)

    @property
    def status(self):
        return self._result(self.last_cursor if self.dragging else None)

    def update(self, landmarks, pinch_state, interaction_mode, frame_time):
        """Start with a debounced pinch; opening controls the complete timeline.

        pinch_state accepts the painter's shared PinchState, a debounced bool,
        or None to use its normalised hysteresis classifier. Opening does not
        end control at the pinch-release threshold: the flower continues to
        unfold until the fingers are fully spread. Closing reverses the flower.
        """
        now = float(frame_time)
        if not math.isfinite(now):
            raise ValueError("帧时间必须是有限数值")
        if interaction_mode != "TIME":
            self.release()
            self.state = "INACTIVE"
            self.last_seen = self.last_cursor = None
            return self._result()
        if landmarks is None:
            self.pending_since = None
            self.endpoint_since = self.endpoint = None
            self.missing = True
            if self.dragging and self.last_seen is not None and now - self.last_seen >= self.LOSS_TIMEOUT:
                self.release(require_open=True)
            self.state = "TIME_LOST" if self.dragging else "TIME_IDLE"
            return self._result()
        points = np.asarray(landmarks, dtype=float)
        if points.shape != (21, 2) or not np.all(np.isfinite(points)):
            return self.update(None, pinch_state, interaction_mode, now)
        ratio, cursor = pinch_measurement(points)
        if ratio is None:
            return self.update(None, pinch_state, interaction_mode, now)
        expired = self.last_seen is not None and now - self.last_seen >= self.LOSS_TIMEOUT
        resumed = self.missing or expired
        if expired and self.dragging:
            self.release(require_open=True)
        self.last_seen, self.last_cursor = now, cursor
        self.missing = False
        if resumed:
            self.pending_since = None
        if self.require_open:
            if ratio >= PINCH_OPEN:
                if self.pending_since is None:
                    self.pending_since = now
                if now - self.pending_since >= PINCH_DEBOUNCE:
                    self.require_open = False
                    self.pending_since = None
            else:
                self.pending_since = None
            self.state = "TIME_IDLE"
            return self._result(cursor)
        if pinch_state is None:
            pinch = advance_pinch(ratio, self.pinched, self.pending_since, now)
        elif isinstance(pinch_state, bool):
            pinch = PinchState(pinch_state, just_closed=pinch_state and not self.pinched,
                               just_opened=not pinch_state and self.pinched)
        elif isinstance(pinch_state, PinchState):
            pinch = pinch_state
        else:
            raise TypeError("捏合状态需要 PinchState、bool 或 None")
        self.pending_since, self.pinched = pinch.pending_since, pinch.closed
        if not self.dragging and pinch.closed:
            self.dragging = True
            self.progress = 0.0
            self._seed()
            self.last_ratio = ratio
        if self.dragging:
            if resumed:
                # The first recovered frame holds the current flower; subsequent
                # changes converge smoothly to the newly measured opening.
                self._seed()
                self.last_ratio = ratio
                self.endpoint_since = self.endpoint = None
            else:
                target = self._clamp((ratio-PINCH_CLOSE)/(self.FULL_OPEN-PINCH_CLOSE))
                if self.last_ratio is None or abs(ratio-self.last_ratio) > self.RATIO_DEADBAND:
                    self.smoother.update((target, 0))
                    self.progress = self._clamp(self.smoother.point[0])
                    self.last_ratio = ratio
                # Settle stable endpoints exactly despite smoothing. Short
                # threshold noise cannot snap a half-open flower to an endpoint.
                endpoint = target if target in (0.0, 1.0) else None
                if endpoint != self.endpoint:
                    self.endpoint, self.endpoint_since = endpoint, now if endpoint is not None else None
                if endpoint is not None and now-self.endpoint_since >= PINCH_DEBOUNCE:
                    self.progress = endpoint
                    self._seed()
            self.state = "TIME_OPEN"
        else:
            self.state = "TIME_IDLE"
        return self._result(cursor)
