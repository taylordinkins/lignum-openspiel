"""Cross-file conformance: ids named in the docs exist in the data; ACTIONS.md ranges match data
sizes.
"""

import re


def _all_ids(cards, planned_work, buildings, path_data):
    ids = {t["id"] for t in cards["tasks"]}
    ids |= {p["id"] for p in cards["placement"]}
    ids |= {w["id"] for w in cards["winter"]}
    ids |= {p["id"] for p in planned_work}
    ids |= {b["id"] for b in buildings}
    for side in path_data["sides"].values():
        ids |= {loc["id"] for loc in side["locations"]}
    return ids


def test_R005_card_and_location_ids_in_docs_exist_in_data(
    cards, planned_work, buildings, path_data, spec_text, actions_text, scenarios_text
):
    """R-005: every task_NN, placement_NN, winter_Y_N, pw_*, base_N, joinery_N id cited in the docs
    exists.
    """
    known = _all_ids(cards, planned_work, buildings, path_data)
    pat = re.compile(
        r"\b(task_\d+|placement_\d+|winter_\d_\d+|pw_[a-z]+(?:_[a-z]+)*|(?:base|joinery)_\d+)\b"
    )
    for name, text in (
        ("SPEC", spec_text),
        ("ACTIONS", actions_text),
        ("SCENARIOS", scenarios_text),
    ):
        for ref in pat.findall(text):
            assert ref in known, f"{name} cites unknown id {ref}"


def test_R005_building_ids_named_in_scenarios_exist(buildings, scenarios_text):
    """SCENARIOS.md: buildings are `waterchannel`..`office`; both endpoints and the data order
    agree.
    """
    ids = [b["id"] for b in buildings]
    assert "buildings `waterchannel`..`office`" in scenarios_text
    assert ids[0] == "waterchannel" and ids[-1] == "office"


def test_R005_actions_catalogue_ranges_match_data_sizes(
    cards, planned_work, buildings, decision_table, chance_table
):
    """ACTIONS 3: TAKE_TASK 19 ids, CHOOSE_BUILDING 10, PLAN_WORK 3 per PW card, PLACE_TASK 3
    sources per slot.
    """
    size = {name: hi - lo + 1 for lo, hi, name, _ in decision_table}
    slots = sum(len(t["requirements"]) for t in cards["tasks"])
    assert size["TAKE_TASK"] == len(cards["tasks"]) == 19
    assert size["CHOOSE_BUILDING"] == len(buildings) == 10
    assert size["PLAN_WORK"] == 3 * len(planned_work) == 30
    assert size["PLACE_TASK"] == 3 * slots == 144


def test_R005_actions_chance_ranges_match_data_sizes(cards, planned_work, buildings, chance_table):
    """ACTIONS 2: TASK_DRAW 19, PW_DRAW 10, PLACEMENT_DRAW 19, BUILDING_DRAW 10, WINTER 2 outcomes
    per year-card (8).
    """
    size = {name: hi - lo + 1 for lo, hi, name, _ in chance_table}
    assert size["TASK_DRAW"] == len(cards["tasks"])
    assert size["PW_DRAW"] == len(planned_work)
    assert size["PLACEMENT_DRAW"] == len(cards["placement"])
    assert size["BUILDING_DRAW"] == len(buildings)
    assert size["WINTER"] == 8  # 4 cards x 2 halves per year
    assert size["CRAFT_DRAW"] == 5  # board, shingle, stake, reed, joker


def test_R013_areas3_chance_range_covers_all_three_subset_ranks(chance_table):
    """ACTIONS 2 / R-013: AREAS3 ranks cover at most C(6,3) = 20 subsets (ids 0..19)."""
    area = next(r for r in chance_table if r[2] == "AREAS3")
    assert area[:2] == (0, 19)


def test_R005_actions_piece_and_param_domains_match_data(setup, cards, actions_text):
    """ACTIONS 1: 6 cutting areas, 3 wood kinds, 5 craftwork types in setup.yaml order, 3 drying
    bonus tiers.
    """
    assert setup["cutting_areas"] == 6
    assert list(setup["supply"]["craftwork_by_type"]) == [
        "board",
        "shingle",
        "stake",
        "reed",
        "joker",
    ]
    assert "task slot *s* | 0..47" in actions_text
    assert "19 cards, 48 slots" in actions_text
    assert sum(len(t["requirements"]) for t in cards["tasks"]) - 1 == 47
