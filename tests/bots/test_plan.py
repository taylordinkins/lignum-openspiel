"""Phase 7 unit 6: the long-term task planner (lignum.bots.plan) and the heuristic-v7 seat.

The v3 feasibility gate did not gate (0.47 tasks per game left incomplete). These tests build
positions by editing a real round-1 Tasks-phase state and check that infeasible tasks are refused.
Task cards (data/components/tasks.yaml index): 17 = milled hardwood +2; 18 = milled hardwood +0
and milled softwood +0; 6 = milled hardwood, firewood and softwood, each +1.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from lignum.bots import HeuristicBot
from lignum.bots.plan import candidate_plan, format_plan, task_plan, task_take_ok, task_worth
from lignum.bots.weights import load_profile
from lignum.game import PHASE_W2, PHASE_W5, LignumState
from tests.harness import load_game

HW_LOG, SW_LOG, FW_LOG = 5, 3, 1  # piece types 2 * kind + milled


def board(round_: int = 1, phase: int = PHASE_W5, **over: Any) -> LignumState:
    """Round-1 W5 state of a 2-player game with seat 0 edited as given: empty wood areas."""
    game = load_game(players=2, joinery=True)
    s = game.new_initial_state()
    assert isinstance(s, LignumState)
    cr = random.Random(1)
    bot = HeuristicBot(profile="heuristic-v4")
    rng = random.Random(0)
    while not (s.phase == PHASE_W5 and s.round == 1):
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(cr.choices(acts, probs)[0])
        else:
            s.apply_action(bot.choose(s, rng))
    s = s.clone()
    s.round, s.phase = round_, phase
    s.sale = ((0, 0, 0), (0, 0, 0))
    s.sale_logs = ((0, 0, 0), (0, 0, 0))
    s.sawing = ((0, 0, 0), (0, 0, 0))
    s.woodpile = ((0, 0, 0), (0, 0, 0))
    s.river = ((0, 0, 0), (0, 0, 0))
    s.dry = (tuple((0,) * 6 for _ in range(3)),) * 2
    s.equip = ((0, 0, 1, 0), (0, 0, 1, 0))
    s.wood = ((2, 2, 1),) * 6
    s.held_tasks = ((), ())
    for k, v in over.items():
        setattr(s, k, v)
    return s


def with_logs(**kinds: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    base = [0, 0, 0]
    for name, n in kinds.items():
        base[("fw", "sw", "hw").index(name)] = n
    return (tuple(base), (0, 0, 0))  # type: ignore[return-value]


def test_drying_time_gate_gates() -> None:
    """Hardwood +2 from the sale area needs 3 rounds of drying (R-059): too late in round 7."""
    late = board(7, sale_logs=with_logs(hw=1), held_tasks=((17,), ()))
    tp = task_plan(late, 0).tasks[0]
    assert not tp.finishable
    assert "drying" in tp.reason
    assert not task_take_ok(board(7, sale_logs=with_logs(hw=1)), 0, 17)
    early = board(3, sale_logs=with_logs(hw=1), held_tasks=((17,), ()))
    tp = task_plan(early, 0).tasks[0]
    assert tp.finishable and tp.next_step == "dry" and tp.slack == 1
    assert task_take_ok(board(3, sale_logs=with_logs(hw=1)), 0, 17)  # slack 1 is enough
    assert not task_take_ok(board(3, sale_logs=with_logs(hw=1)), 0, 17, min_slack=2)


def test_no_drying_capacity_gate_gates() -> None:
    """Three +1 logs entering drying 1 together do not fit (2 logs per area, R-059); with a round
    more in hand they enter in two rounds and fit."""
    logs = with_logs(hw=1, sw=1, fw=1)
    tight = board(6, sale_logs=logs, held_tasks=((6,), ()))
    tp = task_plan(tight, 0).tasks[0]
    assert not tp.finishable and "capacity" in tp.reason
    roomy = board(5, sale_logs=logs, held_tasks=((6,), ()))
    assert task_plan(roomy, 0).tasks[0].finishable


def test_unobtainable_wood_kind_gates() -> None:
    """No hardwood in the seat's areas or in any public cutting area: card 18 cannot finish."""
    none_hw = board(1, wood=((2, 2, 0),) * 6, sale_logs=with_logs(sw=1), held_tasks=((18,), ()))
    tp = task_plan(none_hw, 0).tasks[0]
    assert not tp.finishable and "unobtainable" in tp.reason
    assert not task_take_ok(board(1, wood=((2, 2, 0),) * 6), 0, 18)
    some_hw = board(1, sale_logs=with_logs(sw=1), held_tasks=((18,), ()))
    tp = task_plan(some_hw, 0).tasks[0]
    assert tp.finishable
    assert [s.source for s in tp.missing] == ["cut", "sale"]


def test_next_step_follows_the_wood() -> None:
    both = board(1, sale_logs=with_logs(hw=1, sw=1), held_tasks=((18,), ()))
    tp = task_plan(both, 0).tasks[0]
    assert tp.finishable and tp.next_step == "place" and tp.slack == 6
    disks = board(1, PHASE_W2, sawing=((0, 1, 1), (0, 0, 0)), held_tasks=((18,), ()))
    tp = task_plan(disks, 0).tasks[0]
    assert tp.finishable and tp.next_step == "saw"
    pile = board(1, PHASE_W2, woodpile=((0, 1, 1), (0, 0, 0)), held_tasks=((18,), ()))
    assert task_plan(pile, 0).tasks[0].next_step == "carry"
    no_saw = board(
        1, PHASE_W2, equip=((0, 0, 0, 0), (0, 0, 0, 0)), money=(0, 0), sawing=((0, 1, 1), (0, 0, 0))
    )
    tp = candidate_plan(no_saw, 0, 18)
    assert not tp.finishable and "saw" in tp.reason


def test_placed_pieces_and_completion() -> None:
    s = board(1, sale_logs=with_logs(sw=1), held_tasks=((18,), ()), filled=(0,) * 18 + (1,))
    tp = task_plan(s, 0).tasks[0]
    assert tp.placed == (0,) and [m.index for m in tp.missing] == [1]
    full = board(1, held_tasks=((18,), ()), filled=(0,) * 18 + (3,))
    assert task_plan(full, 0).tasks == ()  # finished cards are not planned


class _Poison(tuple):  # type: ignore[type-arg]
    def __getitem__(self, i: Any) -> Any:
        raise AssertionError("the plan read the hidden picks")

    def __iter__(self) -> Any:
        raise AssertionError("the plan read the hidden picks")


def test_pure_and_blind_to_hidden_picks() -> None:
    s = board(3, sale_logs=with_logs(hw=1), held_tasks=((17,), ()))
    before = str(s)
    picks = s.picks
    s.picks = _Poison(picks)
    plan = task_plan(s, 0)  # raises if it touches state.picks
    candidate_plan(s, 0, 18)
    s.picks = picks
    assert plan.tasks[0].task == 17
    assert str(s) == before
    assert "task 17" in format_plan(plan)


def test_worth_unfinishable_is_zero_and_finishable_counts() -> None:
    w = {"finish_value": 0.85, "cost_weight": 0.3, "progress": 0.0}
    dead = board(7, sale_logs=with_logs(hw=1), held_tasks=((17,), ()))
    assert task_worth(dead, 0, w) == {17: 0.0}
    live = board(3, sale_logs=with_logs(hw=1), held_tasks=((17,), ()))
    assert 0 < task_worth(live, 0, w)[17] <= 10


def test_v7_profile_extends_v6() -> None:
    v6 = {k: v for k, v in load_profile("heuristic-v6").items() if k not in ("plan",)}
    v7 = {k: v for k, v in load_profile("heuristic-v7").items() if k != "plan"}
    assert v6 == v7 and load_profile("heuristic-v7")["plan"]["enabled"]
    assert "plan" not in load_profile("heuristic-v6")


def _play(seed: int, bots: list[HeuristicBot]) -> tuple[list[tuple[bool, bool, bool]], int]:
    """One game: (seat is v7, plan finishable at take time, task completed) per taken card."""
    game = load_game(players=2, joinery=True)
    s = game.new_initial_state()
    assert isinstance(s, LignumState)
    cr = random.Random(f"c{seed}")
    rngs = [random.Random(f"{seed}:{i}") for i in range(2)]
    taken: list[tuple[int, int, bool, bool]] = []
    while not s.is_terminal():
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(cr.choices(acts, probs)[0])
            continue
        p = s.current_player()
        a = bots[p].choose(s, rngs[p])
        before = (s.clone(), tuple(s.held_tasks[p]))
        s.apply_action(a)
        for card in set(s.held_tasks[p]) - set(before[1]):
            verdict = candidate_plan(before[0], p, card).finishable
            taken.append((p, card, bots[p]._plan_on, verdict))  # pyright: ignore[reportPrivateUsage]
    from lignum.components import load_components

    need = {i: len(t.requirements) for i, t in enumerate(load_components().tasks)}
    rows = [
        (v7, verdict, s.filled[card] == (1 << need[card]) - 1) for p, card, v7, verdict in taken
    ]
    return rows, len(taken)


def _gate_stats(games: int) -> dict[str, float]:
    rows: list[tuple[bool, bool, bool]] = []
    for g in range(games):
        mine = [HeuristicBot(profile="heuristic-v7"), HeuristicBot(profile="heuristic-v6")]
        if g % 2:
            mine.reverse()
        rows += _play(100 + g, mine)[0]
    v7 = [r for r in rows if r[0]]
    assert all(r[1] for r in v7), "a v7 seat took a task the plan calls unfinishable"
    tp = sum(1 for r in rows if r[1] and r[2])
    fp = sum(1 for r in rows if r[1] and not r[2])
    fn = sum(1 for r in rows if not r[1] and r[2])
    return {
        "taken": len(rows),
        "v7_taken": len(v7),
        "v7_completed": sum(r[2] for r in v7),
        "precision": tp / max(1, tp + fp),
        "recall": tp / max(1, tp + fn),
    }


def test_v7_takes_only_finishable_tasks_small() -> None:
    _gate_stats(3)


@pytest.mark.slow
def test_gate_precision_recall_over_20_games(capsys: pytest.CaptureFixture[str]) -> None:
    stats = _gate_stats(20)
    with capsys.disabled():
        print("\nplan gate (v7 vs v6, 20 games):", stats)
    assert stats["taken"] > 0
