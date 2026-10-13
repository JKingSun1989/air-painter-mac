"""Cached Unicode text masks, blended into OpenCV BGR frames locally."""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
)


@lru_cache(maxsize=16)
def font(size):
    for path in FONT_PATHS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("找不到可用的中文字体，请确认系统已安装中文字体。")


@lru_cache(maxsize=512)
def text_mask(value, size):
    face = font(size)
    left, top, right, bottom = face.getbbox(value, anchor="ls")
    width, height = max(1, right - left), max(1, bottom - top)
    image = Image.new("L", (width, height))
    ImageDraw.Draw(image).text((-left, -top), value, font=face, fill=255, anchor="ls")
    mask = np.asarray(image).copy()
    mask.flags.writeable = False
    return mask, (left, top, right, bottom)


def text_bounds(value, scale=.48):
    return text_mask(str(value), max(12, round(scale * 34)))[1]


def draw_text(frame, value, xy, scale=.48, color=(230, 230, 230), max_width=None):
    """Baseline-compatible placement with clipping and readable truncation."""
    value = str(value)
    size = max(12, round(scale * 34))
    mask, bounds = text_mask(value, size)
    if max_width is not None:
        while mask.shape[1] > max_width and size > 12:
            size -= 1
            mask, bounds = text_mask(value, size)
        if mask.shape[1] > max_width:
            end = len(value)
            while end > 0:
                end -= 1
                mask, bounds = text_mask(value[:end] + "…", size)
                if mask.shape[1] <= max_width:
                    break
    x, y = int(xy[0]) + bounds[0], int(xy[1]) + bounds[1]
    height, width = mask.shape
    frame_h, frame_w = frame.shape[:2]
    left, top, right, bottom = max(0, x), max(0, y), min(frame_w, x + width), min(frame_h, y + height)
    if left >= right or top >= bottom:
        return
    coverage = mask[top-y:bottom-y, left-x:right-x].astype(np.uint16)[..., None]
    target = frame[top:bottom, left:right]
    target[:] = ((target.astype(np.uint16) * (255 - coverage) +
                  np.array(color, dtype=np.uint16) * coverage + 127) // 255).astype(np.uint8)
