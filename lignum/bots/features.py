"""Raw value-function features of a seat, shared by training and runtime (Phase 7 unit 3).

``tools/collect_games.py`` records these per decision, ``tools/fit_value.py`` fits on them and
``lignum.bots.fitted`` evaluates the fitted value from them, so all three must compute exactly
the same numbers: this is the single implementation. Names and meaning: docs/BOT_DATA.md.
Pure Python (no numpy). Perfect information: reads only the seat's public board, never the
hidden cutting-area picks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from lignum.bots.value import _components, _winter_cost  # pyright: ignore[reportPrivateUsage]
from lignum.game import LignumState
from lignum.rules import CRAFT_ORDER, has_building

FEATURE_NAMES = (
    "money",
    "loan_level",
    "loan_repay",
    "joiners",
    "food",
    "store",
    "sale_unmilled_f",
    "sale_unmilled_s",
    "sale_unmilled_h",
    "sale_logs_f",
    "sale_logs_s",
    "sale_logs_h",
    "dry_unmilled_f",
    "dry_unmilled_s",
    "dry_unmilled_h",
    "dry_logs_f",
    "dry_logs_s",
    "dry_logs_h",
    "woodpile_f",
    "woodpile_s",
    "woodpile_h",
    "sawing_f",
    "sawing_s",
    "sawing_h",
    "river_f",
    "river_s",
    "river_h",
    "joinery_covered",
    "joinery_uncovered",
    "tasks_held",
    "tasks_complete",
    "task_reward_held",
    "task_reward_complete",
    "task_reward_progress",
    "office",
    "craft_tokens",
    "craft_jokers",
    "plans_live",
    "buildings",
    "winters_ahead",
    "rounds_to_winter",
    "winter_shortfall",
)
_KINDS = 3


def _kind3(vals: Sequence[int]) -> list[int]:
    return [int(v) for v in vals[:_KINDS]]


def features(state: LignumState, seat: int, vw: Any) -> list[float]:
    """Raw feature inputs of the value function for ``seat`` (order: FEATURE_NAMES). Perfect
    information: reads only the seat's own public board, never the hidden cutting picks."""
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    tasks = _components().tasks
    dry = state.dry[seat]
    held = state.held_tasks[seat]
    reward_held = reward_done = progress = 0.0
    complete = 0
    for h in held:
        need = len(tasks[h].requirements)
        done = bin(state.filled[h]).count("1")
        reward_held += tasks[h].reward
        progress += tasks[h].reward * min(done, need) / need
        if done >= need:
            complete += 1
            reward_done += tasks[h].reward
    covered = uncovered = 0
    for slot, kind in enumerate(state.joinery_wood[seat]):
        if 0 <= kind < _KINDS:
            if slot < state.joiners[seat]:
                covered += 1
            else:
                uncovered += 1
    craft = state.held_craft[seat]
    winters_ahead = sum(1 for wr in t.winter_rounds if wr >= state.round)
    ahead = [wr - state.round for wr in t.winter_rounds if wr >= state.round]
    flat = dict(vw)
    flat["winter_min_weight"] = 1.0  # unweighted dollars of shortfall ahead
    row: list[float] = [
        state.money[seat],
        state.loans[seat],
        t.loan_repay[state.loans[seat]],
        state.joiners[seat],
        state.food[seat],
        sum(state.store[seat]),
        *_kind3(state.sale[seat]),
        *_kind3(state.sale_logs[seat]),
        *[sum(dry[a][k] for a in range(3)) for k in range(_KINDS)],
        *[sum(dry[a][3 + k] for a in range(3)) for k in range(_KINDS)],
        *_kind3(state.woodpile[seat]),
        *_kind3(state.sawing[seat]),
        *_kind3(state.river[seat]),
        covered,
        uncovered,
        len(held),
        complete,
        reward_held,
        reward_done,
        round(progress, 4),
        int(has_building(t, state.held_buildings, seat, "office")),
        sum(craft[: len(CRAFT_ORDER) - 1]),
        craft[len(CRAFT_ORDER) - 1],
        sum(1 for p in state.plans if p[0] == seat and p[3] >= state.round),
        len(state.held_buildings[seat]),
        winters_ahead,
        min(ahead) if ahead else 0,
        round(_winter_cost(state, t, seat, flat), 4),
    ]
    return row
