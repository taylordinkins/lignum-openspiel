"""Rectify the board photos in third_party/rules/photos/ into third_party/art/ (PLAN.md §5.6, D21).

ludex.dev has no image of the Joinery board side or the player-board extension, so they are cut
from the user's photos: each is perspective-warped to a flat rectangle using the corners in
``tools/photo_corners.json`` and registered in ``third_party/art/manifest.json`` with a ``source``
field (the photo path) instead of ``url``. ``tools.fetch_assets`` preserves such entries.

    uv run python -m tools.prep_photos [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CORNERS = Path(__file__).resolve().parent / "photo_corners.json"
ART = ROOT / "third_party" / "art"

Point = tuple[float, float]


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a x = b by Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def perspective_coeffs(dst: list[Point], src: list[Point]) -> list[float]:
    """Coefficients for Image.transform(PERSPECTIVE): output (x, y) -> input pixel."""
    a: list[list[float]] = []
    b: list[float] = []
    for (x, y), (u, v) in zip(dst, src, strict=True):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    return solve(a, b)


def output_size(corners: list[Point], width: int, height: int | None = None) -> tuple[int, int]:
    """Output (width, height); height from the mean edge-length ratio unless given."""
    if height is not None:
        return width, height
    tl, tr, br, bl = corners
    horiz = (math.dist(tl, tr) + math.dist(bl, br)) / 2
    vert = (math.dist(tl, bl) + math.dist(tr, br)) / 2
    return width, round(width * vert / horiz)


def rectify(img: Image.Image, corners: list[Point], size: tuple[int, int]) -> Image.Image:
    w, h = size
    dst: list[Point] = [(0, 0), (w, 0), (w, h), (0, h)]
    coeffs = perspective_coeffs(dst, corners)
    return img.convert("RGB").transform(
        size, Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC
    )


def remove_glare(
    img: Image.Image,
    center: tuple[float, float],
    sigma: tuple[float, float],
    gain: float,
    saturation: float = 1.0,
) -> Image.Image:
    """Darken (and re-saturate) a smooth elliptical gaussian bump of flash glare."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bump = np.exp(-(((xx - center[0]) / sigma[0]) ** 2 + ((yy - center[1]) / sigma[1]) ** 2) / 2)
    a *= (1 - (1 - gain) * bump)[..., None]
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if saturation != 1.0:
        boosted = np.asarray(ImageEnhance.Color(out).enhance(saturation), dtype=np.float32)
        base = np.asarray(out, dtype=np.float32)
        out = Image.fromarray(
            np.clip(base + (boosted - base) * bump[..., None], 0, 255).astype(np.uint8)
        )
    return out


def fill_edge(
    img: Image.Image,
    edge: tuple[float, float],
    slope: float,
    inner: tuple[float, float],
    inner_slope: float,
    y_max: int,
    feather: int = 3,
) -> Image.Image:
    """Cover table showing past the board's slanted right edge.

    Pixels right of the line ``x = edge[0] + slope * (y - edge[1])`` (rows below ``y_max`` are
    untouched) are rebuilt by ping-pong tiling the board strip between the line
    ``x = inner[0] + inner_slope * (y - inner[1])`` and the edge, so only real board texture shows.
    """
    a = np.asarray(img.convert("RGB")).copy()
    h, w = a.shape[:2]
    for y in range(min(y_max, h)):
        x_edge = round(edge[0] + slope * (y - edge[1]))
        x_in = round(inner[0] + inner_slope * (y - inner[1]))
        x0 = max(x_edge - feather, 0)
        width = x_edge - x_in
        if width < 2 or x0 >= w:
            continue
        for x in range(x0, w):
            k = (x - x_edge) % (2 * width)
            src = x_edge - 1 - k if k < width else x_in + (k - width)
            a[y, x] = a[y, src]
    return Image.fromarray(a)


def apply_fixes(img: Image.Image, fixes: dict[str, Any]) -> Image.Image:
    """Optional post-rectify touch-ups listed under a corner-file entry's ``fixes``."""
    g = fixes.get("glare")
    if g:
        img = remove_glare(
            img, tuple(g["center"]), tuple(g["sigma"]), g["gain"], g.get("saturation", 1.0)
        )
    e = fixes.get("edge_fill")
    if e:
        img = fill_edge(
            img,
            tuple(e["edge"]),
            e["slope"],
            tuple(e["inner"]),
            e["inner_slope"],
            e["y_max"],
            e.get("feather", 3),
        )
    return img


def encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=90, method=6)
    return buf.getvalue()


def prep(out_dir: Path = ART, corners_path: Path = CORNERS, dry_run: bool = False) -> list[str]:
    spec = cast(dict[str, Any], json.loads(corners_path.read_text(encoding="utf-8")))
    manifest_path = out_dir / "manifest.json"
    try:
        manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    assets = [a for a in manifest.get("assets", []) if a["id"] not in spec or "url" in a]
    log: list[str] = []
    for asset_id, item in spec.items():
        if asset_id.startswith("_"):
            continue
        corners = [(float(x), float(y)) for x, y in item["corners"]]
        size = output_size(corners, item["width"], item.get("height"))
        log.append(f"{asset_id}: {item['photo']} -> {item['file']} {size[0]}x{size[1]}")
        if dry_run:
            continue
        photo = ImageOps.exif_transpose(Image.open(ROOT / item["photo"]))
        data = encode(apply_fixes(rectify(photo, corners, size), item.get("fixes", {})))
        target = out_dir / item["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        assets = [a for a in assets if a["id"] != asset_id]
        assets.append(
            {
                "id": asset_id,
                "category": item["category"],
                "alt": item["alt"],
                "file": item["file"],
                "source": item["photo"],
                "width": size[0],
                "height": size[1],
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    if not dry_run:
        manifest["assets"] = sorted(assets, key=lambda a: a["file"])
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rectify board photos into third_party/art/.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)
    for line in prep(dry_run=args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
