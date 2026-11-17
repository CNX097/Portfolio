"""Cut long webtoon strips into panels at blank (white/black) gutters."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

MIN_GUTTER = 12
MIN_PIECE = 80


def _gutter_rows(gray: np.ndarray) -> np.ndarray:
    std = gray.std(axis=1)
    mean = gray.mean(axis=1)
    return (std < 4) & ((mean > 240) | (mean < 15))


def _cuts_at_gutters(blank: np.ndarray) -> list[int]:
    cuts, start = [], None
    for y, b in enumerate(list(blank) + [False]):
        if b and start is None:
            start = y
        elif not b and start is not None:
            if y - start >= MIN_GUTTER:
                cuts.append((start + y) // 2)
            start = None
    return cuts


def _force_cuts(gray: np.ndarray, top: int, bottom: int, width: int) -> list[int]:
    """Cut a too-tall piece near every 2*width, at the calmest row nearby."""
    cuts, y, step = [], top, 2 * width
    window = max(width // 4, 1)
    std = gray.std(axis=1)
    while bottom - y > 3 * width:
        target = y + step
        lo, hi = max(y + MIN_PIECE, target - window), min(bottom - MIN_PIECE, target + window)
        cut = lo + int(np.argmin(std[lo:hi])) if hi > lo else target
        cuts.append(cut)
        y = cut
    return cuts


def split_image(path: Path, out_dir: Path, start_id: int) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        img = Image.open(path).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        from .sources import SourceError

        raise SourceError(
            f"Định dạng ảnh không hỗ trợ: {Path(path).name}. Hãy dùng PNG, JPG hoặc WEBP."
        ) from e
    w, h = img.size
    if h <= 1.5 * w:
        bounds = [(0, h)]
    else:
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        edges = [0] + _cuts_at_gutters(_gutter_rows(gray)) + [h]
        bounds = []
        for top, bottom in zip(edges, edges[1:]):
            inner = [top] + _force_cuts(gray, top, bottom, w) + [bottom]
            bounds += list(zip(inner, inner[1:]))
        bounds = [(a, b) for a, b in bounds if b - a >= MIN_PIECE] or [(0, h)]
    paths = []
    for i, (a, b) in enumerate(bounds):
        piece = img.crop((0, a, w, b))
        if len(bounds) > 1:
            piece = _trim_blank(piece)
        p = out_dir / f"{start_id + i:03d}.png"
        piece.save(p)
        paths.append(p)
    return paths


def _trim_blank(piece: Image.Image) -> Image.Image:
    gray = np.asarray(piece.convert("L"), dtype=np.float32)
    keep = np.where(~_gutter_rows(gray))[0]
    if len(keep) == 0:
        return piece
    return piece.crop((0, int(keep[0]), piece.width, int(keep[-1]) + 1))
