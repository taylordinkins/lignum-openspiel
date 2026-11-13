"""Phase 2 unit 1: derived constants (R-001, R-003, R-005, R-011, R-075, ACTIONS 1.5, 3, 7).

Planned API (lignum/constants.py), plain module-level ints, derived from the spec/data:
    NUM_DISTINCT_ACTIONS = 440, MAX_CHANCE_OUTCOMES = 103
    MIN_PLAYERS = 2, MAX_PLAYERS = 4
    NUM_AREAS = 6, NUM_KINDS = 3, NUM_PIECES = 6, NUM_ZONES = 6, NUM_CRAFTWORK_TYPES = 5
    NUM_TASKS = 19, NUM_TASK_SLOTS = 48, NUM_PLACEMENT_CARDS = 19, NUM_WINTER_CARDS = 8,
    NUM_BUILDINGS = 10, NUM_PW_CARDS = 10
    CLEARING_LOC = 23, MAX_LOANS = 2, LOAN_AMOUNT = 4, STARTING_MONEY = 5
    KIND_FIREWOOD, KIND_SOFTWOOD, KIND_HARDWOOD = 0, 1, 2
    ZONE_SALE, ZONE_DRYING_1, ZONE_DRYING_2, ZONE_DRYING_3, ZONE_SAWING,
        ZONE_FIREWOOD_STORAGE = 0..5
    piece_index(kind: int, milled: bool) -> int   # 2*kind + milled
"""

import re
from pathlib import Path

import yaml


class _Lazy:
    """Import the module on first attribute use, so a missing module fails the (pending) test
    instead of breaking collection."""

    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        import importlib

        return getattr(importlib.import_module(self._name), attr)


C = _Lazy("lignum.constants")
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "components"


def _y(name: str) -> dict:
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def test_R075_action_space_sizes():
    """ACTIONS 1.2/7: 440 decision IDs and 103 chance outcomes."""
    assert C.NUM_DISTINCT_ACTIONS == 440
    assert C.MAX_CHANCE_OUTCOMES == 103


def test_R075_action_space_sizes_match_actions_doc():
    """ACTIONS 7: the constants equal the totals table in docs/ACTIONS.md (no drift)."""
    text = (ROOT / "docs" / "ACTIONS.md").read_text(encoding="utf-8")
    dec = re.search(r"Decision IDs \| \*\*(\d+)\*\*", text)
    ch = re.search(r"Chance outcomes \| \*\*(\d+)\*\*", text)
    assert dec and ch
    assert int(dec.group(1)) == C.NUM_DISTINCT_ACTIONS
    assert int(ch.group(1)) == C.MAX_CHANCE_OUTCOMES


def test_R003_player_counts():
    """R-003: 2, 3 and 4 players are supported."""
    assert (C.MIN_PLAYERS, C.MAX_PLAYERS) == (2, 4)


def test_R005_card_counts_derive_from_data():
    """R-005: card-count constants equal the yaml counts (derived, not invented)."""
    cards = _y("cards.yaml")
    assert C.NUM_TASKS == len(cards["tasks"]) == 19
    assert C.NUM_TASK_SLOTS == sum(len(t["requirements"]) for t in cards["tasks"]) == 48
    assert C.NUM_PLACEMENT_CARDS == len(cards["placement"]) == 19
    assert C.NUM_WINTER_CARDS == len(cards["winter"]) == 8
    assert C.NUM_BUILDINGS == len(_y("buildings.yaml")["buildings"]) == 10
    assert C.NUM_PW_CARDS == len(_y("planned_work.yaml")["planned_work"]) == 10


def test_R006_craftwork_types_count_includes_joker():
    """R-006 / ACTIONS 1.5: craftwork types x in 0..4 (board, shingle, stake, reed, joker)."""
    assert C.NUM_CRAFTWORK_TYPES == len(_y("setup.yaml")["supply"]["craftwork_by_type"]) == 5


def test_R011_loan_constants():
    """R-011/R-075: at most 2 loans per seat, $4 each; R-018/R-008: start with $5."""
    assert (C.MAX_LOANS, C.LOAN_AMOUNT, C.STARTING_MONEY) == (2, 4, 5)
    loans = _y("setup.yaml")["loans"]
    assert (loans["max_per_seat"], loans["amount_each"]) == (C.MAX_LOANS, C.LOAN_AMOUNT)


def test_R004_board_index_ranges():
    """ACTIONS 1.5: 6 areas, 3 kinds, 6 pieces, 6 zones, clearing is location 23."""
    assert (C.NUM_AREAS, C.NUM_KINDS, C.NUM_PIECES, C.NUM_ZONES) == (6, 3, 6, 6)
    assert C.CLEARING_LOC == 23


def test_R007_kind_and_zone_codes():
    """ACTIONS 1.5: kind 0 firewood, 1 softwood, 2 hardwood; zones 0 sale .. 5 firewood storage."""
    assert (C.KIND_FIREWOOD, C.KIND_SOFTWOOD, C.KIND_HARDWOOD) == (0, 1, 2)
    assert [
        C.ZONE_SALE,
        C.ZONE_DRYING_1,
        C.ZONE_DRYING_2,
        C.ZONE_DRYING_3,
        C.ZONE_SAWING,
        C.ZONE_FIREWOOD_STORAGE,
    ] == [0, 1, 2, 3, 4, 5]


def test_R007_piece_index_is_two_k_plus_milled():
    """ACTIONS 1.5: piece p = 2k + m (m=1 milled log): 0 FW disk, 1 FW log, ... 5 HW log."""
    assert [(C.piece_index(k, m)) for k in range(3) for m in (False, True)] == [0, 1, 2, 3, 4, 5]
    assert C.piece_index(C.KIND_HARDWOOD, False) == 4
    assert C.piece_index(C.KIND_SOFTWOOD, True) == 3
