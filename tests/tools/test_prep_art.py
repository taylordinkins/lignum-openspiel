"""Official theme completeness (PLAN.md §5.6): it must define every id the generic theme does."""

import json
from pathlib import Path
from typing import Any

import pytest

from tools import prep_art as pa

OFFICIAL = pa.ART / "manifest.json"
GENERIC = pa.ROOT / "assets" / "generic" / "manifest.json"
needs_art = pytest.mark.skipif(not OFFICIAL.exists(), reason="official art not present")


def _assets(path: Path) -> dict[str, dict[str, Any]]:
    return {a["id"]: a for a in json.loads(path.read_text())["assets"]}


@needs_art
def test_official_defines_every_generic_id_with_a_file() -> None:
    official = _assets(OFFICIAL)
    missing = sorted(set(_assets(GENERIC)) - set(official))
    assert missing == []
    for asset_id, a in official.items():
        assert (pa.ART / a["file"]).is_file(), asset_id


@needs_art
def test_prep_art_entries_are_marked_with_a_source() -> None:
    official = _assets(OFFICIAL)
    ids = [f"building-{b}" for b in pa.BUILDING_BOXES] + [f"pawn-{n}" for n in range(4)]
    ids += [f"piece-{k}-log" for k in pa.LOG_BOXES] + list(pa.ALIASES)
    for asset_id in ids:
        assert "source" in official[asset_id], asset_id
        assert "url" not in official[asset_id], asset_id
