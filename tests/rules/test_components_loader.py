"""Phase 2 unit 1: component loader tests (R-004..R-011, R-013, R-075).

Planned API under test (lignum/components.py), stated so the implementer can follow it:

    load_components(data_dir: Path | str | None = None) -> Components
        data_dir None -> <repo>/data/components. Missing dir or missing file -> FileNotFoundError.
    Components (frozen dataclass), fields, each a tuple of frozen dataclasses unless noted:
        tasks:        Task(id, reward, requirements: tuple[Requirement(kind, milled, drying)])
        placement:    PlacementCard(id, areas: Mapping[int, tuple[str, ...]],
                      food_areas: tuple[int, ...])
        winter:       WinterCard(id, year, halves: Mapping[str, Half(food, heating)])  # top/bottom
        planned_work: PlannedWork(id, name, seasons: tuple[str, ...], params: Mapping)
        buildings:    Building(id, name, params: Mapping)
        path:         Path(sides: Mapping[str, tuple[Location(id, number, kind, name, capacity)]],
                           token_spot_count: int,
                           forest_clearing: ForestClearing(slots, capacity_per_slot))
        setup:        Setup(by_players: Mapping[int, PlayerCountSetup],  # attrs = yaml keys
                            starting_holdings: Holdings(money, foreman_location,
                                                        mill_workers, loans),
                            loans: LoanSetup(cards, max_per_seat, amount_each, sides, repayment),
                            supply: Supply(craftwork_by_type: Mapping[str, int], ...),
                            path_craftwork_tokens: int, ...)  # every setup.yaml top-level key
    Attribute names equal the YAML keys. Order of every sequence equals the YAML order (ACTIONS 1.5
    indexes tasks, buildings and PW cards by that order). No card value is hard-coded in code.
    Components compare by value (dataclass eq).
"""

import dataclasses
import shutil
from pathlib import Path

import pytest
import yaml


class _Lazy:
    """Import the module on first attribute use, so a missing module fails the (pending) test
    instead of breaking collection."""

    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        import importlib

        return getattr(importlib.import_module(self._name), attr)


def load_components(*args):
    return _Lazy("lignum.components").load_components(*args)


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "components"


def _y(name: str) -> dict:
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def comp():
    return load_components()


def test_R005_counts_match_card_totals(comp):
    """R-005: 19 task, 19 placement, 8 winter, 10 PW, 10 building cards are loaded."""
    assert len(comp.tasks) == 19
    assert len(comp.placement) == 19
    assert len(comp.winter) == 8
    assert len(comp.planned_work) == 10
    assert len(comp.buildings) == 10


def test_R005_task_slots_total_48_in_card_order(comp):
    """R-005 / ACTIONS 1.5: 48 requirement slots flat over tasks in yaml order, 1-4 per card."""
    assert sum(len(t.requirements) for t in comp.tasks) == 48
    assert all(1 <= len(t.requirements) <= 4 for t in comp.tasks)
    assert [t.id for t in comp.tasks] == [f"task_{i:02d}" for i in range(1, 20)]


def test_R005_task_values_equal_yaml(comp):
    """R-005: task rewards and requirement fields come from cards.yaml unchanged."""
    raw = _y("cards.yaml")["tasks"]
    for t, r in zip(comp.tasks, raw, strict=True):
        assert (t.id, t.reward) == (r["id"], r["reward"])
        assert [(q.kind, q.milled, q.drying) for q in t.requirements] == [
            (q["kind"], q["milled"], q["drying"]) for q in r["requirements"]
        ]


def test_R005_winter_cards_four_per_year_with_both_halves(comp):
    """R-005: 4 winter cards per year, each with a top and bottom half carrying food and heating."""
    assert sorted(w.year for w in comp.winter) == [1] * 4 + [2] * 4
    raw = {w["id"]: w for w in _y("cards.yaml")["winter"]}
    for w in comp.winter:
        assert set(w.halves) == {"top", "bottom"}
        for h in ("top", "bottom"):
            assert w.halves[h].food == raw[w.id]["halves"][h]["food"]
            assert w.halves[h].heating == raw[w.id]["halves"][h]["heating"]


def test_R005_placement_cards_keep_order_and_food_areas(comp):
    """R-005/R-037: placement cards in yaml order (PLACEMENT_DRAW index), areas and food areas."""
    raw = _y("cards.yaml")["placement"]
    assert [p.id for p in comp.placement] == [r["id"] for r in raw]
    for p, r in zip(comp.placement, raw, strict=True):
        assert tuple(p.food_areas) == tuple(r["food_areas"])
        assert {a: tuple(w) for a, w in p.areas.items()} == {
            a: tuple(w) for a, w in r["areas"].items()
        }


def test_R005_planned_work_and_buildings_in_yaml_order(comp):
    """R-005 / ACTIONS 1.5: building b and PW card c are indexed by yaml order."""
    assert [b.id for b in comp.buildings] == [b["id"] for b in _y("buildings.yaml")["buildings"]]
    pw = _y("planned_work.yaml")["planned_work"]
    assert [p.id for p in comp.planned_work] == [p["id"] for p in pw]
    assert [tuple(p.seasons) for p in comp.planned_work] == [tuple(p["seasons"]) for p in pw]
    assert dict(comp.planned_work[1].params) == pw[1]["params"]


def test_R004_path_sides_20_and_22_locations_13_token_spots(comp):
    """R-004/R-023: base side 20 locations, joinery side 22, 13 token spots, clearing slots A-D."""
    assert set(comp.path.sides) == {"base", "joinery"}
    assert len(comp.path.sides["base"]) == 20
    assert len(comp.path.sides["joinery"]) == 22
    assert comp.path.token_spot_count == 13
    for side in comp.path.sides.values():
        assert sum(1 for loc in side if loc.kind == "token_spot") == 13
    assert list(comp.path.forest_clearing.slots) == ["A", "B", "C", "D"]


def test_R004_path_locations_numbered_1_to_n_in_order(comp):
    """R-032 / ACTIONS 1.5: locations carry their printed number, 1..N in path order."""
    for side, n in (("base", 20), ("joinery", 22)):
        assert [loc.number for loc in comp.path.sides[side]] == list(range(1, n + 1))


def test_R013_setup_quantities_by_player_count(comp):
    """R-013: bearers 10/8/6, woodcutters 16/12/8, 3-firewood areas 4/3/2, placement 3/2/1."""
    s = comp.setup.by_players
    assert set(s) == {2, 3, 4}
    assert [s[n].bearers_on_path for n in (4, 3, 2)] == [10, 8, 6]
    assert [s[n].woodcutters_on_path for n in (4, 3, 2)] == [16, 12, 8]
    assert [s[n].cutting_areas_with_3_firewood for n in (4, 3, 2)] == [4, 3, 2]
    assert [s[n].placement_cards_per_round for n in (4, 3, 2)] == [3, 2, 1]
    assert [s[n].buildings_drawn for n in (4, 3, 2)] == [8, 7, 6]


def test_R011_R075_loan_data(comp):
    """R-011/R-075: 4 loan cards, max 2 per seat, $4 each; start $5 and no loans (R-008)."""
    assert comp.setup.loans.cards == 4
    assert comp.setup.loans.max_per_seat == 2
    assert comp.setup.loans.amount_each == 4
    assert comp.setup.starting_holdings.money == 5
    assert comp.setup.starting_holdings.loans == 0


def test_R006_craftwork_pile_is_18_tokens_by_type(comp):
    """R-006: craftwork pile 4 board, 4 shingle, 4 stake, 4 reed, 2 joker = 18 (type x order)."""
    cw = comp.setup.supply.craftwork_by_type
    assert list(cw) == ["board", "shingle", "stake", "reed", "joker"]
    assert list(cw.values()) == [4, 4, 4, 4, 2]
    assert sum(cw.values()) == 18


def test_R005_components_are_frozen(comp):
    """R-005: loaded components are immutable: attribute assignment raises FrozenInstanceError."""
    for obj in (comp, comp.tasks[0], comp.buildings[0], comp.planned_work[0], comp.path):
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.id = "x"  # type: ignore[attr-defined]
    assert isinstance(comp.tasks, tuple)
    assert isinstance(comp.buildings, tuple)


def test_R005_no_hardcoded_card_values(tmp_path):
    """R-005 / CLAUDE.md: card values live only in yaml: editing a copy changes the loaded value."""
    dst = tmp_path / "components"
    shutil.copytree(DATA, dst)
    p = dst / "cards.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["tasks"][0]["reward"] = 99
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert load_components(dst).tasks[0].reward == 99
    assert load_components().tasks[0].reward != 99


def test_R005_missing_data_dir_raises(tmp_path):
    """R-005: a data dir without the yaml files is an error, not an empty game."""
    with pytest.raises(FileNotFoundError):
        load_components(tmp_path / "nope")
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        load_components(tmp_path / "empty")


def test_R005_accepts_str_and_path_data_dir():
    """R-005: data_dir may be given as str or Path and yields equal components."""
    assert load_components(str(DATA)) == load_components(DATA) == load_components()
