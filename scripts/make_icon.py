"""Draw the B3 Clips icon (yellow 9:16 frame with a play triangle) and save assets/clipper.ico."""
import struct
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> np.ndarray:
    s = 4 * size  # draw big, then shrink for smooth edges
    img = np.zeros((s, s, 4), np.uint8)
    # dark rounded square background
    r = int(s * 0.22)
    bg = (23, 19, 17, 255)
    cv2.rectangle(img, (r, 0), (s - r, s), bg, -1)
    cv2.rectangle(img, (0, r), (s, s - r), bg, -1)
    for cx, cy in ((r, r), (s - r, r), (r, s - r), (s - r, s - r)):
        cv2.circle(img, (cx, cy), r, bg, -1, cv2.LINE_AA)
    # yellow vertical clip frame
    yel = (0, 230, 255, 255)
    w, h = int(s * 0.42), int(s * 0.70)
    x0, y0 = (s - w) // 2, (s - h) // 2
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), yel, -1, cv2.LINE_AA)
    # dark play triangle
    tri = np.array([[x0 + w * 0.36, y0 + h * 0.36], [x0 + w * 0.36, y0 + h * 0.64], [x0 + w * 0.72, y0 + h * 0.5]], np.int32)
    cv2.fillPoly(img, [tri], bg, cv2.LINE_AA)
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


def write_ico(path: Path, sizes=(256, 64, 48, 32, 16)):
    pngs = [cv2.imencode(".png", draw(sz))[1].tobytes() for sz in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for sz, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", sz % 256, sz % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(header + entries + b"".join(pngs))


if __name__ == "__main__":
    write_ico(ROOT / "assets" / "clipper.ico")
    cv2.imwrite(str(ROOT / "assets" / "clipper.png"), draw(256))
    print("wrote assets/clipper.ico")
