"""Wood-flow funnel in the ledger (tools/ledger.py, tools/wood_flow.py)."""

import io
import json
import random

import pytest

from lignum import actions as A
from tools.ledger import WOOD_KEYS, Ledger
from tools.replay import Replay, load_game
from tools.tournament import _bot, bot_rng, run_tournament
from tools.wood_flow import aggregate, main

PHASE_W2 = 7


def _play(seats: list[str], seed: int, check_every_step: bool = True):
    """Play one game with the given bots; returns (ledger, history)."""
    game = load_game(Replay(game="lignum", params={"players": len(seats), "joinery": True}))
    rng = random.Random(seed)
    state = game.new_initial_state()
    ledger = Ledger(state)
    history: list[int] = []
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            action = rng.choices(actions, weights=probs)[0]
        else:
            bot = _bot(seats[state.current_player()])
            action = bot.choose(state.clone(), bot_rng(seed, len(history)))
        ledger.apply(action)
        history.append(action)
        if check_every_step:
            assert all(c == (0, 0) for c in ledger.wood_conservation()), len(history)
    return ledger, history


def _total(flow: dict, key: str) -> int:
    return sum(row[key] for row in flow["rounds"].values())


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("seats", [["heuristic-v2"] * 2, ["random"] * 3])
def test_conservation_holds_after_every_action_and_diff_is_complete(seats, seed) -> None:
    ledger, _ = _play(seats, seed)
    for flow in ledger.wood_flow():
        assert _total(flow, "unexplained") == 0
        assert _total(flow, "unexplained_hw") == 0
        for row in flow["rounds"].values():
            assert set(row) == {k + s for k in WOOD_KEYS for s in ("", "_hw")}
            assert all(row[k + "_hw"] <= row[k] for k in WOOD_KEYS)


def _river_arrivals(history: list[int]) -> int:
    """MOVE_WOOD actions that are river arrivals (log driving) rather than transport trips."""
    game = load_game(Replay(game="lignum", params={"players": 2, "joinery": True}))
    state = game.new_initial_state()
    n = 0
    for action in history:
        if not state.is_chance_node() and A.decode(action).name == "MOVE_WOOD":
            n += state.phase == PHASE_W2
        state.apply_action(action)
    return n


def test_counts_match_the_action_history() -> None:
    """Scripted tiny history: counters equal the same actions counted from the history."""
    ledger, history = _play(["heuristic-v2"] * 2, 4, check_every_step=False)
    names = [A.decode(a).name for a in history]
    flows = ledger.wood_flow()
    wanted = {
        "TAKE_WOOD": "cut",
        "SAW": "sawn",
        "PLACE_TASK": "tasks",
        "PLACE_JOINERY": "joinery",
    }
    for name, key in wanted.items():
        assert sum(_total(f, key) for f in flows) == names.count(name)
    hut_dry = sum(
        1 for a in history if A.decode(a).name == "HUT_DRY" and A.decode(a).params[0] == 0
    )
    dried = sum(_total(f, "dried") for f in flows)
    assert dried == names.count("DRY_ENTER") + hut_dry
    moves = names.count("MOVE_WOOD") + names.count("WC_MOVE")
    assert sum(_total(f, "arr_saw") + _total(f, "arr_sale") for f in flows) == moves
    carried = sum(_total(f, m) for f in flows for m in ("move_bearer", "move_wagon", "move_sledge"))
    assert carried == names.count("MOVE_WOOD") - _river_arrivals(history)
    rafted = sum(_total(f, "move_raft") for f in flows)
    assert rafted == names.count("RIVER_MOVE") + names.count("WC_MOVE")


def test_aggregate_and_tournament_json_key() -> None:
    ledger, _ = _play(["heuristic-v2"] * 2, 5, check_every_step=False)
    agg = aggregate(ledger.wood_flow())
    assert agg["total"]["cut"] == pytest.approx(
        sum(agg["rounds"][str(r)]["cut"] for r in range(1, 9))
    )
    r = run_tournament(["heuristic-v2", "heuristic-v1"], 2, 2, seed=3)
    for b in r["bots"].values():
        wf = b["wood_flow"]
        assert set(wf["rounds"]) == {str(i) for i in range(1, 9)}
        assert wf["total"]["cut"] >= wf["total"]["cut_hw"]
    json.dumps(r)


def test_cli_reports_partial_history(tmp_path) -> None:
    _, history = _play(["random"] * 2, 6, check_every_step=False)
    params = {"players": 2, "joinery": True}
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"game": "lignum", "params": params, "history": history[:80]}))
    out = io.StringIO()
    assert main([str(path)], out) == 0
    text = out.getvalue()
    assert "PARTIAL" in text and "hardwood" in text and "P1" in text
    full = tmp_path / "f.json"
    full.write_text(json.dumps({"game": "lignum", "params": params, "history": history}))
    out = io.StringIO()
    assert main([str(full)], out) == 0
    assert "complete game" in out.getvalue()


def _task_pieces_by_kind(seats: list[str], seed: int) -> tuple[Ledger, int, int]:
    """Play a game and count the pieces PLACE_TASK puts on tasks (all, hardwood), read from the
    task slot or the small storage before each action, independently of the ledger."""
    game = load_game(Replay(game="lignum", params={"players": len(seats), "joinery": True}))
    rng = random.Random(seed)
    state = game.new_initial_state()
    ledger = Ledger(state)
    n = hw = steps = 0
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            action = rng.choices(actions, weights=probs)[0]
        else:
            action = _bot(seats[state.current_player()]).choose(state.clone(), bot_rng(seed, steps))
            decoded = A.decode(action)
            if decoded.name == "PLACE_TASK":
                slot, where = decoded.params[0], decoded.params[1]
                seat = state.current_player()
                kind = (
                    state.small_storage[seat] if where == 2 else state._tables().task_slots[slot][2]  # pyright: ignore[reportPrivateUsage]
                )
                n += 1
                hw += kind == 2
        ledger.apply(action)
        steps += 1
    return ledger, n, hw


def test_hardwood_task_pieces_are_counted_exactly() -> None:
    """Pins the hardwood split of tasks (a mis-split would otherwise be absorbed into sold)."""
    total_n = total_hw = 0
    for seed in (10, 12, 14, 17):  # seeds where heuristic-v2 places task pieces
        ledger, n, hw = _task_pieces_by_kind(["heuristic-v2"] * 2, seed)
        flows = ledger.wood_flow()
        assert sum(_total(f, "tasks") for f in flows) == n
        assert sum(_total(f, "tasks_hw") for f in flows) == hw
        for f in flows:
            assert _total(f, "unexplained") == 0
        total_n += n
        total_hw += hw
    assert 0 < total_hw < total_n
