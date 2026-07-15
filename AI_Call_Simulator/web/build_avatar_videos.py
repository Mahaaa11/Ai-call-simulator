#!/usr/bin/env python3
"""Build looping prospect avatar videos (idle + speaking) from static PNGs."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent / "assets"
SOURCES = {
    "female": ASSETS / "prospect-female-calm.png",
    "male": ASSETS / "prospect-male-calm.png",
}


def crop_9_16(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    target = 9 / 16
    current = w / h
    if current > target:
        new_w = int(h * target)
        x0 = (w - new_w) // 2
        return img[:, x0 : x0 + new_w]
    new_h = int(w / target)
    y0 = max(0, (h - new_h) // 3)
    return img[y0 : y0 + new_h, :]


def render_loop(
    source: Path,
    output: Path,
    *,
    mode: str = "idle",
    frames: int = 72,
    fps: int = 24,
    width: int = 720,
) -> None:
    img = cv2.imread(str(source))
    if img is None:
        raise FileNotFoundError(source)
    cropped = crop_9_16(img)
    ch, cw = cropped.shape[:2]
    height = int(width * 16 / 9)
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open video writer for {output}")

    for i in range(frames):
        t = i / frames
        if mode == "speaking":
            scale = 1.02 + 0.035 * math.sin(t * math.pi * 2)
            scale += 0.012 * math.sin(t * math.pi * 10)
            dx = int(6 * math.sin(t * math.pi * 6))
            dy = int(4 * math.cos(t * math.pi * 5))
        else:
            scale = 1.0 + 0.028 * math.sin(t * math.pi * 2)
            dx = int(3 * math.sin(t * math.pi * 2))
            dy = int(2 * math.cos(t * math.pi * 2))

        crop_w = int(cw / scale)
        crop_h = int(ch / scale)
        x0 = max(0, min(cw - crop_w, (cw - crop_w) // 2 + dx))
        y0 = max(0, min(ch - crop_h, (ch - crop_h) // 3 + dy))
        patch = cropped[y0 : y0 + crop_h, x0 : x0 + crop_w]
        frame = cv2.resize(patch, (width, height), interpolation=cv2.INTER_LINEAR)
        writer.write(frame)

    writer.release()
    print(f"Wrote {output} ({mode}, {frames} frames @ {fps}fps)")


def main() -> None:
    for gender, src in SOURCES.items():
        if not src.exists():
            print(f"Skip missing {src}")
            continue
        for mode in ("idle", "speaking"):
            out = ASSETS / f"prospect-{gender}-{mode}.mp4"
            render_loop(src, out, mode=mode)


if __name__ == "__main__":
    main()
