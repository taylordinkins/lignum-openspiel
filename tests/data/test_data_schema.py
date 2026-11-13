"""Schema and stated-value conformance of the component data (R-005, R-054, R-055, R-058, R-059,
R-066..R-117).
"""

import pytest

KINDS = {"firewood", "softwood", "hardwood"}
SEASONS = {"spring", "summer", "fall", "winter"}


def test_R055_task_records_have_exactly_the_known_fields(cards):
    """R-055: each task has id, reward, requirements; each requirement has kind, milled, drying."""
    for t in cards["tasks"]:
        assert set(t) == {"id", "reward", "requirements"}, t["id"]
        assert isinstance(t["reward"], int) and t["reward"] > 0
        assert 1 <= len(t["requirements"]) <= 4
        for r in t["requirements"]:
            assert set(r) == {"kind", "milled", "drying"}, (t["id"], r)
            assert r["kind"] in KINDS
            assert isinstance(r["milled"], bool)
            assert r["drying"] in (0, 1, 2)


def test_R037_placement_records_have_valid_areas_woods_and_food_areas(cards):
    """R-037/R-039: areas 1..6 with unmilled wood kinds; food_areas = two distinct areas 1..6."""
    for p in cards["placement"]:
        assert set(p) == {"id", "areas", "food_areas"}, p["id"]
        assert p["areas"], p["id"]
        for area, woods in p["areas"].items():
            assert area in range(1, 7), (p["id"], area)
            assert woods and all(w in KINDS for w in woods), (p["id"], area)
        fa = p["food_areas"]
        assert len(fa) == 2 and len(set(fa)) == 2, p["id"]
        assert all(a in range(1, 7) for a in fa), p["id"]


def test_R027_winter_records_have_year_and_two_halves(cards):
    """R-027: each winter card has a year (1/2) and two halves with int food and heating."""
    for w in cards["winter"]:
        assert set(w) == {"id", "year", "halves"}, w["id"]
        assert w["year"] in (1, 2)
        assert w["id"].startswith(f"winter_{w['year']}_")
        assert set(w["halves"]) == {"top", "bottom"}
        for half in w["halves"].values():
            assert set(half) == {"food", "heating"}
            assert isinstance(half["food"], int) and half["food"] > 0
            assert isinstance(half["heating"], int) and half["heating"] > 0


def test_R117_winter_halves_never_tie_on_food_plus_heating(cards):
    """R-117: the easier half has a strictly lower food+heating sum; no card ties."""
    for w in cards["winter"]:
        sums = [h["food"] + h["heating"] for h in w["halves"].values()]
        assert sums[0] != sums[1], w["id"]


def test_R117_easier_halves_match_the_spec_worked_list(cards):
    """R-117: spec lists the easier half per card: Y1 5/7, 6/3, 5/5, 5/4; Y2 7/7, 10/7, 8/6, 6/8."""
    easier = {}
    for w in cards["winter"]:
        h = min(w["halves"].values(), key=lambda h: h["food"] + h["heating"])
        easier[w["id"]] = (h["food"], h["heating"])
    assert easier == {
        "winter_1_1": (5, 7), "winter_1_2": (6, 3), "winter_1_3": (5, 5), "winter_1_4": (5, 4),
        "winter_2_1": (7, 7), "winter_2_2": (10, 7), "winter_2_3": (8, 6), "winter_2_4": (6, 8),
    }  # fmt: skip


def test_R088_R090_R099_planned_work_records(planned_work):
    """R-088: PW records have id, name, seasons (subset of the four, in the allowed set), params."""
    for p in planned_work:
        assert set(p) == {"id", "name", "seasons", "params"}, p["id"]
        assert p["seasons"] and set(p["seasons"]) <= SEASONS
        assert len(set(p["seasons"])) == len(p["seasons"])
        assert isinstance(p["params"], dict) and p["params"]


def test_R088_planned_work_winter_availability(planned_work):
    """R-088: 'Not all PW may be planned for winter'; Sawing, Heating Supply and Overtime list
    winter (spec 4.x/R-097).
    """
    winter = {p["id"] for p in planned_work if "winter" in p["seasons"]}
    assert winter == {"pw_sawing", "pw_heating_supply", "pw_overtime"}


def test_R090_to_R099_planned_work_params_match_spec_numbers(planned_work):
    """R-090 Trade $2; R-091 Craftwork 5/8/11; R-092 2 disks; R-093 2 food; R-094 6 logs; R-095 2
    tokens; R-097 1 hardwood; R-098 3 pieces; R-099 +2 woodcutters.
    """
    params = {p["id"]: p["params"] for p in planned_work}
    assert params["pw_trade"] == {"price_per_equipment": 2}
    assert params["pw_craftwork"] == {"set_prices": {2: 5, 3: 8, 4: 11}}
    assert params["pw_sawing"] == {"disks_per_saw": 2}
    assert params["pw_food_supply"] == {"food_per_river_piece": 2}
    assert params["pw_heating_supply"] == {"logs_per_firewood_disk": 6}
    assert params["pw_hut_construction"] == {"tokens_needed": 2}
    assert params["pw_drying"] == {"first_area_capacity_multiplier": 2}
    assert params["pw_overtime"] == {"hardwood_disks": 1}
    assert params["pw_log_driving"] == {"max_pieces": 3}
    assert params["pw_cutting"]["extra_woodcutters"] == 2


def test_R106_to_R116_building_records_and_params(buildings):
    """R-106..R-116: buildings have id, name, params; named numeric params match the spec."""
    for b in buildings:
        assert set(b) == {"id", "name", "params"}, b["id"]
        assert b["params"]
    params = {b["id"]: b["params"] for b in buildings}
    assert params["waterchannel"] == {"immediate_pieces_per_transport_phase": 1}  # R-107
    assert params["marketstand"] == {"food_sale_price": 1}  # R-108
    assert params["storeroom"] == {"winter_food_reduction": 1}  # R-109
    assert params["small_workshop"] == {"reed_as_shingle_max": 1}  # R-111
    assert params["drying_area_upgrade"] == {"drying_area_capacity": 2}  # R-110
    assert params["small_joinery"] == {"joinery_bonus": 4}  # R-112
    assert params["inn"] == {"planned_work_cost": 0}  # R-113
    assert params["small_storage_area"] == {"capacity": 1}  # R-114
    assert params["field"] == {"fodder_cost": 0}  # R-115
    assert params["office"] == {"money_per_task_card": 1}  # R-116


def test_R058_wood_prices(setup):
    """R-058: milled HW 5 (unmilled unsellable), SW 4 unmilled/2 milled, FW 3 unmilled/1 milled."""
    assert setup["wood_prices"] == {
        "hardwood": {"milled": 5, "unmilled": None},
        "softwood": {"milled": 2, "unmilled": 4},
        "firewood": {"milled": 1, "unmilled": 3},
    }


def test_R059_drying_bonuses_and_capacity(setup):
    """R-059: bonus +0/+0/+1/+2 for sale, drying 1..3; drying area holds 1 unmilled disk or 2
    milled logs; 3 areas.
    """
    assert setup["drying_bonuses"] == {"sale_area": 0, "drying_1": 0, "drying_2": 1, "drying_3": 2}
    assert setup["drying_area_capacity"] == {"disks": 1, "logs": 2}
    assert setup["sawmill"]["drying_areas"] == 3


def test_R054_sawing_yield(setup):
    """R-054: hardwood 1, softwood 3, firewood 4 logs per milled disk."""
    assert setup["sawing_yield"] == {"hardwood": 1, "softwood": 3, "firewood": 4}


def test_R025_sawyer_prices(setup):
    """R-025: first sawyer free, the extra sawyer $1."""
    assert setup["sawyer_prices"] == {"first": 0, "extra": 1}


def test_R041_R048_R088_R104_location_prices(setup):
    """R-041/R-048/R-088/R-104: $1 for bearer, fodder, woodcutter, task, PW token, saw, food,
    cutting-token move.
    """
    assert setup["location_prices"] == {
        "bearer": 1, "fodder": 1, "woodcutter": 1, "task": 1, "planned_work_per_token": 1,
        "market_saw": 1, "market_food": 1, "cutting_area_move": 1,
    }  # fmt: skip


def test_R105_craftwork_set_prices(setup):
    """R-105: sets of 2/3/4 identical tokens pay $2/$4/$6."""
    assert setup["craftwork_set_prices"] == {2: 2, 3: 4, 4: 6}


def test_R066_R067_R071_R072_winter_numbers(setup):
    """R-066 first woodcutting 2 FW, further 1; R-067 sledge 2 pieces + up to 3 food; R-071/72
    shortfall $3.
    """
    assert setup["winter"] == {
        "woodcutting_first": 2,
        "woodcutting_each_further": 1,
        "sledge_base_pieces": 2,
        "sledge_max_food": 3,
        "shortfall_per_unit": 3,
    }


def test_R041_R052_fodder_slots(setup):
    """R-041/R-052: fodder storage slots valued 3 and 2 (value-3 slot filled first)."""
    assert setup["sawmill"]["fodder_slot_values"] == [3, 2]
    assert setup["sawmill"]["hut_effect_slots"] == 3  # R-008


def test_R079_R082_joiner_numbers(setup):
    """R-079 $1 income per joiner; R-071 1 extra food per joiner; R-082 +3 joinery bonus."""
    assert setup["joiner"] == {"income_per_round": 1, "food_per_winter": 1}
    assert setup["joinery_bonus"] == 3


@pytest.mark.parametrize("fixture", ["cards", "path_data", "setup", "buildings", "planned_work"])
def test_R005_no_unexpected_null_values(request, fixture):
    """No file contains null values other than the documented unmilled-hardwood price (R-058)."""
    data = request.getfixturevalue(fixture)

    def walk(obj, where):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k is not None, where
                if v is None:
                    assert where.endswith("wood_prices.hardwood") and k == "unmilled", (
                        f"{where}.{k}"
                    )
                else:
                    walk(v, f"{where}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                assert v is not None, f"{where}[{i}]"
                walk(v, f"{where}[{i}]")

    walk(data, fixture)


def test_R005_top_level_keys_of_each_file(cards, path_data, setup):
    """No unknown top-level keys in the component files."""
    assert set(cards) == {"tasks", "placement", "winter"}
    assert set(path_data) == {"sides", "forest_clearing", "token_spot_count"}
    assert set(setup) == {
        "by_players", "path_craftwork_tokens", "sawyer_prices", "cutting_areas",
        "cutting_area_firewood", "starting_holdings", "per_seat", "supply", "sawmill",
        "wood_prices", "drying_bonuses", "player_board_extension", "sawmill_pads",
        "player_board_extensions", "loans", "joinery_setup", "location_prices",
        "craftwork_set_prices", "sawing_yield", "drying_area_capacity", "joiner",
        "joinery_bonus", "winter",
    }  # fmt: skip
