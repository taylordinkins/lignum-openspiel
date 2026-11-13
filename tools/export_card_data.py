"""Export the card data the web card viewer shows (data/components/*.yaml -> cardData.json).

The yaml files stay the only place card values live; the web app imports the generated JSON.
``tests/tools/test_card_data.py`` fails when the committed JSON is stale.

Usage: ``uv run python -m tools.export_card_data``
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "src" / "games" / "lignum" / "cardData.json"


def build() -> dict[str, object]:
    comp = ROOT / "data" / "components"
    cards = yaml.safe_load((comp / "cards.yaml").read_text())
    return {
        "tasks": cards["tasks"],
        "placement": cards["placement"],
        "winter": cards["winter"],
        "planned_work": yaml.safe_load((comp / "planned_work.yaml").read_text())["planned_work"],
        "buildings": yaml.safe_load((comp / "buildings.yaml").read_text())["buildings"],
    }


def render() -> str:
    return json.dumps(build(), indent=1) + "\n"


def main() -> None:
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
