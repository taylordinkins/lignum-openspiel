"""Counts, ids and setup totals of the component data (R-005, R-006, R-011, R-013, R-017,
R-021..R-024).
"""

import re


def test_R005_task_cards_are_19_with_48_requirement_slots(cards):
    """R-005: 19 task cards; ACTIONS.md task slot s in 0..47 (48 slots, 1-4 per card)."""
    tasks = cards["tasks"]
    assert len(tasks) == 19
    assert sum(len(t["requirements"]) for t in tasks) == 48
    assert {len(t["requirements"]) for t in tasks} <= {1, 2, 3, 4}


def test_R005_placement_cards_are_19(cards):
    """R-005: 19 placement cards."""
    assert len(cards["placement"]) == 19


def test_R005_winter_cards_are_8_four_per_year(cards):
    """R-005: 8 winter cards, 4 per year."""
    winter = cards["winter"]
    assert len(winter) == 8
    assert sorted(w["year"] for w in winter) == [1] * 4 + [2] * 4


def test_R005_planned_work_cards_are_the_named_10(planned_work):
    """R-005: 10 PW cards, one each of the ten named kinds."""
    assert {p["name"] for p in planned_work} == {
        "Trade", "Craftwork", "Sawing", "Food Supply", "Heating Supply",
        "Hut Construction", "Drying", "Overtime", "Log Driving", "Cutting",
    }  # fmt: skip
    assert len(planned_work) == 10


def test_R005_buildings_are_the_named_10(buildings):
    """R-005: 10 buildings, one each of the ten named kinds."""
    assert {b["name"] for b in buildings} == {
        "Waterchannel", "Marketstand", "Storeroom", "Small Workshop", "Drying Area Upgrade",
        "Small Joinery", "Inn", "Field", "Small Storage Area", "Office",
    }  # fmt: skip
    assert len(buildings) == 10


def test_R005_ids_are_unique_within_each_file(cards, planned_work, buildings, path_data):
    """R-005: every card/building/location id is unique (ids are the cross-file keys)."""
    groups = [
        [t["id"] for t in cards["tasks"]],
        [p["id"] for p in cards["placement"]],
        [w["id"] for w in cards["winter"]],
        [p["id"] for p in planned_work],
        [b["id"] for b in buildings],
    ]
    for side in path_data["sides"].values():
        groups.append([loc["id"] for loc in side["locations"]])
    for ids in groups:
        assert len(ids) == len(set(ids))


def test_R005_card_ids_follow_documented_patterns(cards, planned_work):
    """SCENARIOS.md: ids are task_01..task_19, placement_01..placement_19, winter_Y_N, pw_*."""
    assert [t["id"] for t in cards["tasks"]] == [f"task_{i:02d}" for i in range(1, 20)]
    assert [p["id"] for p in cards["placement"]] == [f"placement_{i:02d}" for i in range(1, 20)]
    assert sorted(w["id"] for w in cards["winter"]) == [
        f"winter_{y}_{n}" for y in (1, 2) for n in range(1, 5)
    ]
    assert all(re.fullmatch(r"pw_[a-z_]+", p["id"]) for p in planned_work)


def test_R004_R023_path_sides_have_20_and_22_locations_with_13_token_spots(path_data):
    """R-004/R-023: base side 20 locations, joinery side 22, 13 token spots on each side."""
    sides = path_data["sides"]
    assert set(sides) == {"base", "joinery"}
    assert len(sides["base"]["locations"]) == 20
    assert len(sides["joinery"]["locations"]) == 22
    assert path_data["token_spot_count"] == 13
    for side in sides.values():
        assert sum(1 for loc in side["locations"] if loc["kind"] == "token_spot") == 13


def test_R032_locations_are_numbered_consecutively_in_path_order(path_data):
    """R-032: printed numbers 1..N in path order; ids are '<side>_<number>'."""
    for name, side in path_data["sides"].items():
        locs = side["locations"]
        assert [loc["number"] for loc in locs] == list(range(1, len(locs) + 1))
        assert [loc["id"] for loc in locs] == [f"{name}_{loc['number']}" for loc in locs]


def test_R021_R022_location_capacities(path_data):
    """R-021/R-022: token spots 1; Bearers, Woodcutters, Sawyers, Tasks, PW, Market 4; Fodder 2;
    Buildings 2; Joiner 1.
    """
    expected = {
        "token_spot": 1, "bearers": 4, "woodcutters": 4, "sawyers": 4, "tasks": 4,
        "planned_work": 4, "market": 4, "fodder": 2, "buildings": 2, "joiner": 1,
    }  # fmt: skip
    for side in path_data["sides"].values():
        for loc in side["locations"]:
            assert loc["capacity"] == expected[loc["kind"]], loc


def test_R002_location_kinds_per_side(path_data):
    """R-002: both sides share the seven acquisition kinds; Joiner and Buildings exist on the
    joinery side only.
    """

    def kinds(side):
        locs = path_data["sides"][side]["locations"]
        return sorted(loc["kind"] for loc in locs if loc["kind"] != "token_spot")

    common = ["bearers", "fodder", "market", "planned_work", "sawyers", "tasks", "woodcutters"]
    assert kinds("base") == common
    assert kinds("joinery") == sorted([*common, "buildings", "joiner"])


def test_R024_forest_clearing_has_four_single_slots(path_data):
    """R-024: forest clearing slots A-D, one seat each."""
    fc = path_data["forest_clearing"]
    assert fc["slots"] == ["A", "B", "C", "D"]
    assert fc["capacity_per_slot"] == 1


def test_R003_by_players_present_for_2_3_4(setup):
    """R-003: exactly 2, 3 and 4 players supported."""
    assert set(setup["by_players"]) == {2, 3, 4}


def test_R013_by_players_values_match_the_spec_table(setup):
    """R-013: setup quantities by player count (4 / 3 / 2 players)."""
    expected = {
        "bearers_on_path": (10, 8, 6),
        "woodcutters_on_path": (16, 12, 8),
        "fodder_on_path": (2, 2, 1),
        "sawyers_price_0": (4, 3, 2),
        "sawyers_price_1": (1, 1, 1),
        "placement_cards_per_round": (3, 2, 1),
        "cutting_areas_with_3_firewood": (4, 3, 2),
        "cutting_areas_with_2_firewood": (2, 3, 4),
        "task_cards_laid_out": (4, 3, 2),
        "pw_cards_laid_out": (6, 5, 4),
        "buildings_drawn": (8, 7, 6),
    }
    by = setup["by_players"]
    for key, (v4, v3, v2) in expected.items():
        assert (by[4][key], by[3][key], by[2][key]) == (v4, v3, v2), key


def test_R013_by_players_have_identical_key_sets(setup):
    """R-013: the same quantities are tabulated for every player count."""
    keysets = [set(v) for v in setup["by_players"].values()]
    assert keysets[0] == keysets[1] == keysets[2]


def test_R013_areas_split_sums_to_six_and_tasks_equal_players(setup):
    """R-013/R-014: 3-firewood + 2-firewood areas = 6; task cards = players; PW = players + 2."""
    for n, row in setup["by_players"].items():
        assert row["cutting_areas_with_3_firewood"] + row["cutting_areas_with_2_firewood"] == 6
        assert row["task_cards_laid_out"] == n
        assert row["pw_cards_laid_out"] == n + 2
        assert row["cutting_areas_with_3_firewood"] == n  # R-013 note: equals players


def test_R013_R017_path_tokens_are_10_equipment_plus_3_craftwork(setup):
    """R-013/R-017: 10 equipment tokens (X-markers included at 2p) + 3 craftwork = 13 spots; 2p mix
    has 2 X.
    """
    assert setup["path_craftwork_tokens"] == 3
    for n, row in setup["by_players"].items():
        assert sum(row["path_equipment_tokens"].values()) == 10, n
    assert setup["by_players"][2]["path_equipment_tokens"] == {
        "wagon": 1, "raft": 2, "saw": 1, "sledge": 1, "dollar": 1, "food": 2, "x_marker": 2,
    }  # fmt: skip
    for n in (3, 4):
        assert setup["by_players"][n]["path_equipment_tokens"] == {
            "wagon": 2, "raft": 2, "saw": 2, "sledge": 1, "dollar": 1, "food": 2,
        }  # fmt: skip


def test_R006_R007_R009_supply_totals(setup):
    """R-006/R-007/R-009: component pools in the general supply."""
    s = setup["supply"]
    assert s["woodcutters"] == 16
    assert s["bearers"] == 10
    assert s["sawyers"] == 5
    assert s["mill_workers"] == 4
    assert s["joiners"] == 6
    assert s["buildings_total"] == 10
    assert s["fodder"] == 8
    assert s["craftwork_by_type"] == {"board": 4, "shingle": 4, "stake": 4, "reed": 4, "joker": 2}
    assert sum(s["craftwork_by_type"].values()) == 18  # R-014: the 18 craftwork tokens
    assert s["max_saws_per_seat"] == 4  # R-041


def test_R011_R075_loans_four_cards_max_two_per_seat(setup):
    """R-011/R-075: 4 loan cards, max 2 per seat, $4 each, '4/7' and '16' sides."""
    loans = setup["loans"]
    assert loans["cards"] == 4
    assert loans["max_per_seat"] == 2
    assert loans["amount_each"] == 4
    assert loans["sides"] == ["4/7", "16"]


def test_R077_loan_repayment_7_then_16(setup):
    """R-077: repayment $7 for one loan, $16 for two."""
    assert setup["loans"]["repayment"] == {1: 7, 2: 16}


def test_R008_R018_per_seat_components_and_starting_holdings(setup):
    """R-008/R-018: six PW tokens, six cutting tokens, one foreman, $5, foreman on 0, mill worker,
    no loans.
    """
    ps = setup["per_seat"]
    assert ps["planned_work_tokens"] == 6
    assert ps["cutting_area_tokens"] == 6
    assert ps["foremen"] == 1
    assert setup["starting_holdings"] == {
        "money": 5, "foreman_location": 0, "mill_workers": 1, "loans": 0,
    }  # fmt: skip


def test_R010_player_board_extension(setup):
    """R-010: three joiner spaces, three joinery slots, two building spaces."""
    assert setup["player_board_extension"] == {
        "joiner_spaces": 3, "joinery_wood_slots": 3, "building_spaces": 2,
    }  # fmt: skip


def test_R004_R015_six_cutting_areas_with_3_or_2_firewood(setup):
    """R-004/R-015: six cutting areas; 3-firewood and 2-firewood area contents."""
    assert setup["cutting_areas"] == 6
    assert setup["cutting_area_firewood"] == {"with_3": 3, "with_2": 2}
