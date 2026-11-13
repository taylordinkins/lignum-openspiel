"""Generic placeholder theme (PLAN.md §5.6, D11, D21): coverage, files and determinism."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.make_generic_theme import BUILDINGS, OFFICIAL, ROOT, write

GENERIC = ROOT / "assets" / "generic"
needs_official = pytest.mark.skipif(not OFFICIAL.exists(), reason="official art not present")


def _assets(path: Path) -> list[dict[str, Any]]:

    assets: list[dict[str, Any]] = json.loads(path.read_text())["assets"]
    return assets


def test_ids_unique_and_files_exist() -> None:
    assets = _assets(GENERIC / "manifest.json")
    ids = [a["id"] for a in assets]
    assert len(ids) == len(set(ids))
    for a in assets:
        assert (GENERIC / a["file"]).is_file(), a["id"]
        assert a["width"] > 0 and a["height"] > 0 and a["alt"]


@needs_official
def test_covers_every_official_id_with_same_category_and_shape() -> None:
    generic = {a["id"]: a for a in _assets(GENERIC / "manifest.json")}
    for o in _assets(OFFICIAL):
        g = generic[o["id"]]
        assert g["category"] == o["category"], o["id"]
        if o.get("width"):
            assert (g["width"], g["height"]) == (o["width"], o["height"]), o["id"]


def test_extra_ids_present() -> None:
    ids = {a["id"] for a in _assets(GENERIC / "manifest.json")}
    wanted = {"board-joinery", "player-extension", "foreman", "craftwork-back"}
    wanted |= {f"pawn-{n}" for n in range(4)}
    wanted |= {
        f"piece-{w}-{kind}"
        for w in ("firewood", "softwood", "hardwood")
        for kind in ("disk", "log")
    }
    wanted |= {f"building-{b['id']}" for b in yaml.safe_load(BUILDINGS.read_text())["buildings"]}
    assert wanted <= ids


@needs_official
def test_regeneration_is_byte_identical(tmp_path: Path) -> None:
    write(tmp_path)
    for p in sorted(tmp_path.rglob("*")):
        if p.is_file():
            assert p.read_bytes() == (GENERIC / p.relative_to(tmp_path)).read_bytes(), p
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()} == {
        p.relative_to(GENERIC) for p in GENERIC.rglob("*") if p.is_file()
    }


def test_sawmill_pad_prints_data_driven_prices_and_drying_bonuses() -> None:
    """Sale prices and drying "+" modifiers on the generic sawmill come from setup.yaml (R-058)."""
    setup = yaml.safe_load((ROOT / "data" / "components" / "setup.yaml").read_text())
    svg = (GENERIC / "boards" / "sawmill.svg").read_text()
    for p in setup["wood_prices"].values():
        un = "-" if p["unmilled"] is None else f"${p['unmilled']}"
        assert f">${p['milled']}<" in svg
        assert f">{un}<" in svg
    for n in (1, 2, 3):
        bonus = setup["drying_bonuses"][f"drying_{n}"]
        assert (f">+{bonus}<" in svg) == (bonus > 0)


def test_craftwork_tiles_are_pink_unlike_equipment_icons() -> None:
    for k in ("board", "shingle", "stake", "reed", "joker", "back"):
        assert "#f8d3dc" in (GENERIC / "craftwork" / f"craftwork-{k}.svg").read_text(), k
