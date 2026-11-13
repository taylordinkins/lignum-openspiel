"""Hardwood pick bias and premium task ranking of heuristic-v4 (Phase 7 unit 1g step c)."""

from __future__ import annotations

import pyspiel

import lignum.game  # noqa: F401  (registers the game)
from lignum import actions as A
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.tasks import task_premium
from lignum.bots.weights import load_profile
from lignum.components import load_components


def _state() -> pyspiel.State:
    return pyspiel.load_game("python_lignum(players=2)").new_initial_state()


def test_premium_from_data() -> None:
    t = _state()._tables()  # pyright: ignore[reportPrivateUsage]
    tasks = {k.id: task_premium(t, k) for k in load_components().tasks}
    per_piece = {k.id: task_premium(t, k, True) for k in load_components().tasks}
    assert per_piece["task_08"] == tasks["task_08"] / 4
    order = sorted(tasks, key=lambda k: -tasks[k])
    assert set(order[:4]) == {"task_07", "task_08", "task_06", "task_12"}
    assert order[-2:] == ["task_01", "task_18"] or set(order[-2:]) <= {
        "task_01",
        "task_18",
        "task_19",
    }
    assert tasks["task_18"] == 3 and tasks["task_07"] == 13
    # task_01: reward 12, milled hardwood 5 + milled firewood 1, both unbonused
    assert tasks["task_01"] == 12 - 6


def test_keys_absent_in_v2_v3_and_set_in_v4() -> None:
    for name in ("heuristic-v2", "heuristic-v3"):
        w = load_profile(name)
        assert "pick_hw_task_bonus" not in w and "task_rank" not in w
    v4 = load_profile("heuristic-v4")
    # v4 is the control heuristic (unit 1g close): premium ranking and mill_saws on, pick bias off
    assert v4["pick_hw_task_bonus"] == 0 and v4["task_rank"] == "premium"
    assert v4["mill_saws"] == 1


def _pick_setup() -> tuple[pyspiel.State, list[int]]:
    s = _state()
    while s.legal_actions() and A.decode(s.legal_actions()[0]).name != "PICK_AREA":
        s.apply_action(s.legal_actions()[0])
    return s, s.legal_actions()


def test_pick_gating() -> None:
    s, legal = _pick_setup()
    base = HeuristicBot(load_profile("heuristic-v4"))
    assert base._hw_target(s) >= 0  # pyright: ignore[reportPrivateUsage]
    on = HeuristicBot({**load_profile("heuristic-v4"), "pick_hw_task_bonus": 100.0})
    # holding a hardwood task: target is its hardwood slots
    s.held_tasks = (
        tuple(i for i, k in enumerate(load_components().tasks) if k.id == "task_01"),
        (),
    )  # type: ignore[attr-defined]
    assert on._hw_target(s) >= 1  # pyright: ignore[reportPrivateUsage]
    import random

    a = on._pick_area(s, legal, random.Random(0))  # pyright: ignore[reportPrivateUsage]
    most = max(legal, key=lambda x: s.wood[A.decode(x).params[0]][2])
    assert s.wood[A.decode(a).params[0]][2] == s.wood[A.decode(most).params[0]][2]


def test_best_task_ranking_gated() -> None:
    s = _state()
    ids = [k.id for k in load_components().tasks]
    offered = [ids.index("task_01"), ids.index("task_07")]
    loose = {**load_profile("heuristic-v4"), "task_take_prob": 0.0, "task_take_margin": -99.0}
    pick = HeuristicBot({**loose, "task_rank": "premium"})._best_task(s, 0, offered)  # pyright: ignore[reportPrivateUsage]
    assert pick is not None and pick[0] == offered[1]
    pick = HeuristicBot({**loose, "task_rank": "premium_piece"})._best_task(s, 0, offered)  # pyright: ignore[reportPrivateUsage]
    assert pick is not None and pick[0] == offered[1]


def test_bonus_kind_is_conditional_in_v4_only():
    """v4 sets bonus_kind: hardwood; v2 and v3 leave the choice to the lookahead."""
    from lignum.bots.weights import load_profile

    assert load_profile("heuristic-v4")["bonus_kind"] == "hardwood_if_task"
    assert "bonus_kind" not in load_profile("heuristic-v2")
    assert "bonus_kind" not in load_profile("heuristic-v3")
