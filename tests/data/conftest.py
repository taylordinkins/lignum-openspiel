"""Fixtures for the data-conformance tests (Phase 1 unit 12).

These tests read ``data/components/*.yaml`` and ``docs/*.md`` only; no engine code is imported.
Doc-table parsing lives here so the test modules stay about rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "data" / "components"
DOCS = ROOT / "docs"


def _yaml(name: str) -> dict:
    with open(COMPONENTS / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="session")
def cards() -> dict:
    return _yaml("cards.yaml")


@pytest.fixture(scope="session")
def path_data() -> dict:
    return _yaml("path.yaml")


@pytest.fixture(scope="session")
def setup() -> dict:
    return _yaml("setup.yaml")


@pytest.fixture(scope="session")
def buildings() -> list[dict]:
    return _yaml("buildings.yaml")["buildings"]


@pytest.fixture(scope="session")
def planned_work() -> list[dict]:
    return _yaml("planned_work.yaml")["planned_work"]


@pytest.fixture(scope="session")
def spec_text() -> str:
    return (DOCS / "RULES_SPEC.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def actions_text() -> str:
    return (DOCS / "ACTIONS.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def scenarios_text() -> str:
    return (DOCS / "SCENARIOS.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- ACTIONS.md parsing


def section(text: str, heading_prefix: str) -> str:
    """Body of the ``## <heading_prefix>...`` section of a markdown document."""
    m = re.search(rf"^## {re.escape(heading_prefix)}.*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"section {heading_prefix!r} not found"
    return m.group(1)


def table_rows(body: str) -> list[list[str]]:
    """Rows (cells) of the first markdown table in body, header and separator dropped."""
    rows: list[list[str]] = []
    started = False
    for line in body.splitlines():
        if line.startswith("|"):
            started = True
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif started:
            break
    return rows[2:]


def parse_id_range(cell: str) -> tuple[int, int]:
    nums = [int(n) for n in re.findall(r"\d+", cell)]
    assert nums, cell
    return nums[0], nums[-1]


def parse_id_table(body: str) -> list[tuple[int, int, str, str]]:
    """(first_id, last_id, NAME, rules cell) per row of a decision/chance ID table."""
    out = []
    for cells in table_rows(body):
        lo, hi = parse_id_range(cells[0])
        name = re.search(r"`([A-Z_0-9]+)", cells[1])
        assert name, cells
        out.append((lo, hi, name.group(1), cells[-1]))
    return out


def expand_rule_ids(text: str) -> set[str]:
    """All R-nnn ids in text, expanding ``R-a..R-b`` and ``R-a through R-b`` ranges."""
    ids: set[str] = set()
    for a, b in re.findall(r"R-(\d+)\s*(?:\.\.|through|–)\s*R?-?(\d+)", text):
        ids.update(f"R-{n:03d}" for n in range(int(a), int(b) + 1))
    ids.update(f"R-{int(n):03d}" for n in re.findall(r"R-(\d+)", text))
    return ids


@pytest.fixture(scope="session")
def rule_ids():
    return expand_rule_ids


@pytest.fixture(scope="session")
def decision_table(actions_text: str) -> list[tuple[int, int, str, str]]:
    return parse_id_table(section(actions_text, "3. Decision IDs"))


@pytest.fixture(scope="session")
def chance_table(actions_text: str) -> list[tuple[int, int, str, str]]:
    return parse_id_table(section(actions_text, "2. Chance outcomes"))


@pytest.fixture(scope="session")
def mapping_rows(actions_text: str) -> list[tuple[str, str]]:
    """(rule cell, action cell) rows of the section 6 rule-to-action table."""
    body = section(actions_text, "6. Rule to action mapping")
    return [(c[0], c[1]) for c in table_rows(body)]


@pytest.fixture(scope="session")
def no_action_text(actions_text: str) -> str:
    body = section(actions_text, "6. Rule to action mapping")
    m = re.search(r"Rules with \*\*no action\*\*[^\n]*\n(.*?)(?=\n\n|\Z)", body, re.S)
    assert m, "'Rules with no action' paragraph not found"
    return m.group(1)
