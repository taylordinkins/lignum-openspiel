"""Tests for tools/prep_photos.py: corner file, perspective warp, manifest entries, fetch_assets."""

import json
from pathlib import Path

import pytest
from PIL import Image

from tools import fetch_assets as fa
from tools import prep_photos as pp

IDS = ("board-joinery", "player-extension")

# third_party/ (photos, official art) is local-only and absent from CI and fresh clones.
needs_photos = pytest.mark.skipif(
    not (pp.ROOT / "third_party" / "rules" / "photos").is_dir(), reason="photos not present"
)
needs_art = pytest.mark.skipif(
    not (pp.ART / "manifest.json").exists(), reason="official art not present"
)


@needs_photos
def test_corner_file_is_valid() -> None:
    spec = json.loads(pp.CORNERS.read_text(encoding="utf-8"))
    for asset_id in IDS:
        item = spec[asset_id]
        assert (pp.ROOT / item["photo"]).is_file()
        assert item["category"] == "boards"
        assert item["file"].endswith(".webp")
        assert item["width"] > 0
        assert len(item["corners"]) == 4
        for x, y in item["corners"]:
            assert x >= 0 and y >= 0
        (tl, tr, br, bl) = item["corners"]
        assert tl[0] < tr[0] and bl[0] < br[0] and tl[1] < bl[1] and tr[1] < br[1]


def test_warp_maps_quadrilateral_to_rectangle() -> None:
    src = Image.new("RGB", (100, 100), (255, 0, 0))
    # A tilted quadrilateral filled with blue; everything outside stays red.
    quad = [(20, 10), (80, 20), (85, 70), (15, 60)]
    from PIL import ImageDraw

    ImageDraw.Draw(src).polygon(quad, fill=(0, 0, 255))
    out = pp.rectify(src, quad, (60, 50))
    assert out.size == (60, 50)
    for xy in [(1, 1), (58, 1), (58, 48), (1, 48), (30, 25)]:
        r, _, b = out.getpixel(xy)  # type: ignore[misc]
        assert b > 200 and r < 60, xy


def test_output_size_from_geometry() -> None:
    assert pp.output_size([(0, 0), (200, 0), (200, 100), (0, 100)], 400) == (400, 200)
    assert pp.output_size([(0, 0), (200, 0), (200, 100), (0, 100)], 400, 50) == (400, 50)


def make_art(tmp_path: Path) -> Path:
    photo = tmp_path / "photo.png"
    Image.new("RGB", (40, 30), (10, 120, 10)).save(photo)
    spec = {
        "board-joinery": {
            "photo": str(photo),
            "category": "boards",
            "file": "boards/board_joinery.webp",
            "alt": "Joinery",
            "width": 20,
            "corners": [[0, 0], [40, 0], [40, 30], [0, 30]],
        }
    }
    path = tmp_path / "corners.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_manifest_entry_shape_and_fetch_preserves(tmp_path: Path) -> None:
    out = tmp_path / "art"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
    pp.prep(out, make_art(tmp_path))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    (entry,) = manifest["assets"]
    assert set(entry) == {
        "id", "category", "alt", "file", "source", "width", "height", "sha256", "bytes",
    }  # fmt: skip
    assert "url" not in entry
    assert (entry["width"], entry["height"]) == (20, 15)
    data = (out / entry["file"]).read_bytes()
    assert entry["bytes"] == len(data) and entry["sha256"] == fa.sha256(data)

    fa.fetch_assets(
        out, fetch=lambda u: (u.encode(), "image/webp"), html="", pause=0, log=lambda _: None
    )
    after = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert entry in after["assets"]


@needs_art
def test_real_manifest_has_joinery_entries() -> None:
    manifest = json.loads((pp.ART / "manifest.json").read_text(encoding="utf-8"))
    by_id = {a["id"]: a for a in manifest["assets"]}
    for asset_id in IDS:
        assert by_id[asset_id]["category"] == "boards"
        assert "source" in by_id[asset_id]


def test_glare_removal_darkens_bump_only() -> None:
    img = Image.new("RGB", (100, 80), (200, 200, 200))
    out = pp.remove_glare(img, (50, 40), (10, 10), 0.5)
    assert out.size == img.size
    assert out.getpixel((50, 40))[0] < 110  # type: ignore[index]
    assert out.getpixel((0, 0)) == (200, 200, 200)


def test_edge_fill_replaces_table_and_keeps_size() -> None:
    img = Image.new("RGB", (100, 20), (0, 160, 0))
    for y in range(20):
        for x in range(80, 100):
            img.putpixel((x, y), (90, 40, 30))  # "table"
    out = pp.fill_edge(img, (80, 0), 0.0, (60, 0), 0.0, 20, feather=0)
    assert out.size == img.size
    assert all(out.getpixel((x, y)) == (0, 160, 0) for y in range(20) for x in range(100))


@needs_art
def test_board_joinery_fixes_keep_manifest_size() -> None:
    spec = json.loads(pp.CORNERS.read_text(encoding="utf-8"))["board-joinery"]
    assert {"glare", "edge_fill"} <= set(spec["fixes"])
    manifest = json.loads((pp.ART / "manifest.json").read_text(encoding="utf-8"))
    entry = next(a for a in manifest["assets"] if a["id"] == "board-joinery")
    with Image.open(pp.ART / spec["file"]) as im:
        assert im.size == (entry["width"], entry["height"]) == (1600, 1061)
