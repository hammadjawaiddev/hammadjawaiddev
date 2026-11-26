#!/usr/bin/env python3
"""Offline-only: turn the user's photo into a clean, ASCII-ready grayscale portrait.

    pip install opencv-python-headless numpy Pillow
    python scripts/prep_portrait.py

Input chain:
  assets/source-photo.jpg  -> the photo the user supplied
  assets/portrait-ink.png  -> pen-and-ink rendition of that photo (background
                              already removed, lines kept sharp)
  assets/portrait-prepped.png -> square, tone-stretched, ridge-darkened
                                 grayscale used by render_cards.py

This mirrors Avi Vashishta's scripts/prep_photo.py: bilateral smoothing keeps
skin clean, a 2-92 percentile tone stretch puts the face near white, and a
difference-of-Gaussians ridge term darkens the thin eyelid / nose / lip lines
that plain luminance averaging washes out at ASCII resolution. The result is
committed, so the daily GitHub Action only needs Pillow — no cv2, no model
downloads, and the portrait never drifts from day to day.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "portrait-ink.png"
DST = ROOT / "assets" / "portrait-prepped.png"

# Face box measured with a Haar cascade on the 896x1200 ink rendition:
# (396, 252, 270, 270) -> centre (531, 387). A 460px square keeps hair, ears,
# chin and the top of the lapels while leaving the empty white margins out.
CENTER = (531, 390)
SIDE = 460
LINE_WEIGHT = 0.6


def main() -> None:
    rgb = Image.open(SRC).convert("RGB")
    cx, cy = CENTER
    x0, y0 = int(cx - SIDE / 2), int(cy - SIDE / 2)
    canvas = Image.new("RGB", (SIDE, SIDE), "white")
    canvas.paste(rgb.crop((x0, y0, x0 + SIDE, y0 + SIDE)), (0, 0))

    gray = cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2GRAY)
    smooth = gray
    for _ in range(3):
        smooth = cv2.bilateralFilter(smooth, 9, 40, 9)

    lo, hi = np.percentile(smooth, [2, 92])
    tone = np.clip((smooth.astype(np.float32) - lo) / (hi - lo), 0, 1)

    fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
    coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
    lines = np.clip((coarse - fine) / 40.0, 0, 1)
    out = np.clip(tone - LINE_WEIGHT * lines, 0, 1) * 255

    Image.fromarray(out.astype(np.uint8), "L").save(DST, optimize=True)
    print(f"wrote {DST.relative_to(ROOT)} ({SIDE}x{SIDE})")


if __name__ == "__main__":
    main()
