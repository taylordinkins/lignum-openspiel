"""Derive the official-theme sprites that ludex.dev does not ship (PLAN.md §5.6, D11, D21).

Crops buildings from the user's photo, wood disks from the Sawmill board, a pawn from the cutting
token (recoloured to the seat colours in web/.../seatColors.ts), and maps a few ids onto existing
icons. Everything lands under ``third_party/art/`` and is registered in ``manifest.json`` with a
``source`` field; ``tools.fetch_assets`` preserves such entries.

    uv run python -m tools.prep_art [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "third_party" / "art"
PHOTO = "third_party/rules/photos/buildings.jpg"
SAWMILL = "third_party/art/boards/sawmill.webp"
TOKEN = "third_party/art/tokens/cutting-token-front.webp"

Box = tuple[int, int, int, int]


def table(f: Callable[[int], int]) -> list[int]:
    """A 256-entry lookup table for Image.point (typed alternative to a lambda)."""
    return [f(v) for v in range(256)]


# Tile boxes (x0, y0, x1, y1) in the 1024x683 photo, margins already trimmed.
BUILDING_BOXES: dict[str, Box] = {
    "field": (43, 163, 224, 340),
    "drying_area_upgrade": (237, 160, 417, 338),
    "small_storage_area": (430, 163, 610, 340),
    "small_joinery": (623, 165, 803, 342),
    "waterchannel": (815, 168, 992, 345),
    "inn": (32, 353, 213, 537),
    "storeroom": (227, 351, 413, 536),
    "office": (426, 352, 608, 537),
    "marketstand": (622, 354, 803, 538),
    "small_workshop": (817, 357, 999, 541),
}
BUILDING_SIZE = 192
# Wood disks on the Sawmill sale helper (region g).
LOG_BOXES: dict[str, Box] = {
    "hardwood": (1231, 552, 1304, 597),
    "softwood": (1230, 712, 1306, 758),
    "firewood": (1230, 879, 1308, 924),
}
LOG_DARK = {"hardwood": 110, "softwood": 110, "firewood": 150}  # outline luminance cut-off
# Centres (x, y, 1600x1597 px) of the white a-k section badges printed on the Sawmill board.
BADGES = [
    (70, 168), (640, 192), (992, 170), (72, 465), (527, 937), (657, 545),
    (1232, 515), (72, 751), (72, 1055), (626, 1152), (866, 1150),
]  # fmt: skip
BADGE_R = 29
PAWN_BOX: Box = (36, 26, 124, 148)
# Hue (0-255) of the blue pawn, and the seat hues: red, blue, green, gold (seatColors.ts).
BASE_HUE = 152
SEAT_HUES = (4, 152, 103, 30)
CRAFT = ("board", "joker", "reed", "shingle", "stake")
WOODS = ("firewood", "softwood", "hardwood")
ALIASES: dict[str, tuple[str, str]] = {  # id -> (category, existing file)
    **{f"craftwork-{k}": ("craftwork", f"tokens/icon-{k}.webp") for k in CRAFT},
    "craftwork-back": ("craftwork", "tokens/icon-hut.webp"),
    "foreman": ("tokens", "tokens/pawn-0.webp"),  # the seat pawn; the UI uses pawn-<seat>
    # icon-hardwood.webp is clipped in the source sheet, so its disk reuses the log crop.
    **{f"piece-{k}-disk": ("tokens", f"tokens/icon-{k}.webp") for k in ("firewood", "softwood")},
    "piece-hardwood-disk": ("tokens", "tokens/piece-hardwood-log.webp"),
}


def cut_out(img: Image.Image, dark: int) -> Image.Image:
    """Make the region outside the dark outline transparent (flood fill from the border)."""
    rgb = img.convert("RGB")
    if "A" in img.getbands():
        rgb = Image.composite(rgb, Image.new("RGB", rgb.size, (255, 255, 255)), img.getchannel("A"))
    w, h = rgb.size
    mask = ImageOps.expand(
        rgb.convert("L").point(table(lambda v: 0 if v < dark else 128)), 1, fill=128
    )
    ImageDraw.floodfill(mask, (0, 0), 255, thresh=0)
    outside = mask.crop((1, 1, w + 1, h + 1)).point(table(lambda v: 255 if v == 255 else 0))
    alpha = (
        ImageChops.invert(outside)
        .filter(ImageFilter.MinFilter(3))
        .filter(ImageFilter.GaussianBlur(0.6))
    )
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def remove_badges(img: Image.Image) -> Image.Image:
    """Fill each badge disc by diffusing the surrounding pixels inward (blurry, fine at ~300 px)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32).copy()
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    for cx, cy in BADGES:
        x0, x1, y0, y1 = cx - BADGE_R - 4, cx + BADGE_R + 5, cy - BADGE_R - 4, cy + BADGE_R + 5
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        patch = a[y0:y1, x0:x1]
        mask = ((xx[y0:y1, x0:x1] - cx) ** 2 + (yy[y0:y1, x0:x1] - cy) ** 2) <= BADGE_R**2
        patch[mask] = patch[~mask].mean(axis=0)
        for _ in range(600):
            p = np.pad(patch, ((1, 1), (1, 1), (0, 0)), mode="edge")
            avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
            patch[mask] = avg[mask]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def building(photo: Image.Image, box: Box) -> Image.Image:
    tile = photo.crop(box).resize((BUILDING_SIZE, BUILDING_SIZE), Image.Resampling.LANCZOS)
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *(s - 1 for s in tile.size)), 10, fill=255)
    tile = tile.convert("RGBA")
    tile.putalpha(mask)
    return tile


def pawn_base(token: Image.Image) -> Image.Image:
    """Key the tan disc (and the transparent corners) out of the pawn by colour distance."""
    rgba = token.convert("RGBA")
    tan = rgba.getpixel((20, 78))
    assert isinstance(tan, tuple)
    rgb = rgba.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, tan[:3]))
    r, g, b = diff.split()
    dist = ImageChops.add(ImageChops.add(r, g), b)
    alpha = dist.point(table(lambda v: 255 if v > 70 else 0))
    alpha = ImageChops.multiply(
        alpha, rgba.getchannel("A").point(table(lambda v: 255 if v > 200 else 0))
    )
    alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    out = rgb.convert("RGBA")
    out.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.5)))
    out = out.crop(PAWN_BOX)
    return out.crop(out.getchannel("A").point(table(lambda v: 255 if v > 40 else 0)).getbbox())


def recolour(img: Image.Image, hue: int) -> Image.Image:
    delta = (hue - BASE_HUE) % 256
    h, s, v = img.convert("RGB").convert("HSV").split()
    h = h.point(table(lambda x: (x + delta) % 256))
    out = Image.merge("HSV", (h, s, v)).convert("RGB").convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


# Hired-worker meeples: the official red mill-worker meeple recoloured (hue, saturation %, value %).
MEEPLE = "tokens/icon-mill-worker.webp"
MEEPLE_HUE = 1
WORKER_TINTS = {
    "bearer": (85, 100, 100),
    "woodcutter": (17, 75, 62),
    "sawyer": (0, 0, 135),
    "joiner": (36, 100, 108),
}  # fmt: skip


def tint(img: Image.Image, hue: int, sat: int, val: int) -> Image.Image:
    h, s, v = img.convert("RGB").convert("HSV").split()
    h = h.point(table(lambda x: (x - MEEPLE_HUE + hue) % 256))
    s = s.point(table(lambda x: min(255, x * sat // 100)))
    v = v.point(table(lambda x: min(255, x * val // 100)))
    out = Image.merge("HSV", (h, s, v)).convert("RGB").convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


def encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=92, method=6)
    return buf.getvalue()


def entry(
    asset_id: str, category: str, alt: str, file: str, source: str, data: bytes
) -> dict[str, Any]:
    size = Image.open(io.BytesIO(data)).size
    return {
        "id": asset_id, "category": category, "alt": alt, "file": file, "source": source,
        "width": size[0], "height": size[1],
        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
    }  # fmt: skip


def prep(out_dir: Path = ART, dry_run: bool = False) -> list[str]:
    photo = ImageOps.exif_transpose(Image.open(ROOT / PHOTO)).convert("RGB")
    sawmill = Image.open(ROOT / SAWMILL).convert("RGB")
    token = Image.open(ROOT / TOKEN)
    new: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}

    def add(
        asset_id: str, category: str, alt: str, file: str, source: str, img: Image.Image
    ) -> None:
        data = encode(img)
        files[file] = data
        new.append(entry(asset_id, category, alt, file, source, data))

    for name, box in BUILDING_BOXES.items():
        title = name.replace("_", " ").capitalize()
        add(
            f"building-{name}",
            "buildings",
            title,
            f"buildings/building-{name}.webp",
            PHOTO,
            building(photo, box),
        )
    for name, box in LOG_BOXES.items():
        file = f"tokens/piece-{name}-log.webp"
        img = cut_out(sawmill.crop(box), LOG_DARK[name])
        add(f"piece-{name}-log", "tokens", f"{name.capitalize()} log", file, SAWMILL, img)
    add(
        "sawmill-plain",
        "boards",
        "Sawmill board without section letters",
        "boards/sawmill-plain.webp",
        SAWMILL,
        remove_badges(sawmill),
    )
    base = pawn_base(token)
    for n, hue in enumerate(SEAT_HUES):
        add(
            f"pawn-{n}",
            "tokens",
            f"Seat P{n} pawn",
            f"tokens/pawn-{n}.webp",
            TOKEN,
            recolour(base, hue),
        )
    meeple = Image.open(ART / MEEPLE).convert("RGBA")
    for kind, (hue, sat, val) in WORKER_TINTS.items():
        add(
            f"worker-{kind}",
            "tokens",
            f"{kind.capitalize()} meeple",
            f"tokens/worker-{kind}.webp",
            MEEPLE,
            tint(meeple, hue, sat, val),
        )
    for n, hue in enumerate(SEAT_HUES):
        add(
            f"mill-worker-{n}",
            "tokens",
            f"Seat P{n} mill worker",
            f"tokens/mill-worker-{n}.webp",
            MEEPLE,
            tint(meeple, hue, 100, 100),
        )
    for asset_id, (category, file) in ALIASES.items():
        data = files[file] if file in files else (out_dir / file).read_bytes()
        alt = asset_id.replace("-", " ").capitalize()
        new.append(entry(asset_id, category, alt, file, file, data))

    log = [f"{a['id']}: {a['file']} {a['width']}x{a['height']}" for a in new]
    if dry_run:
        return log
    for file, data in files.items():
        target = out_dir / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest_path = out_dir / "manifest.json"
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    ids = {a["id"] for a in new}
    assets = [a for a in manifest["assets"] if a["id"] not in ids] + new
    manifest["assets"] = sorted(assets, key=lambda a: (a["file"], a["id"]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive extra official-theme sprites.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)
    for line in prep(dry_run=args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
