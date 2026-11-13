"""Scenario snapshot of a state (docs/SCENARIOS.md 2, 4, 8). Minimal: setup fields only.

Later units extend ``dump_scenario`` as the state grows; the field names are those of the
scenario format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lignum.components import Components, load_components
from lignum.constants import NUM_AREAS
from lignum.rules import CRAFT_ORDER, EQUIP_SLOTS, KIND_NAMES, SPOT_NAMES
from lignum.woodwork import STORAGE_SPENT

if TYPE_CHECKING:
    from lignum.game import LignumState

_cache: list[Components] = []


class ScenarioError(Exception):
    """Scenario format error; the first argument is the code (e.g. "S-NOTDECISION")."""


def _components() -> Components:
    if not _cache:
        _cache.append(load_components())
    return _cache[0]


def _pieces(counts: tuple[int, ...]) -> dict[str, int]:
    """Piece map of unmilled disks by kind (SCENARIOS 1.2); zero entries are left out."""
    return {
        f"{k}_disk": c
        for k, c in zip(("firewood", "softwood", "hardwood"), counts, strict=True)
        if c
    }


def _logs(counts: tuple[int, ...]) -> dict[str, int]:
    """Piece map of milled logs by kind."""
    return {
        f"{k}_log": c
        for k, c in zip(("firewood", "softwood", "hardwood"), counts, strict=True)
        if c
    }


def _storage_piece(value: int) -> str | None:
    """The Small Storage Area piece key (R-114), or None when empty or spent."""
    return f"{KIND_NAMES[value]}_log" if 0 <= value < len(KIND_NAMES) else None


def _merge(*maps: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in maps:
        out.update(m)
    return out


def dump_scenario(state: LignumState) -> dict[str, Any]:
    """Implements R-012..R-020, R-031, R-032: the resolved scenario of a decision-node state."""
    from lignum.game import (
        N_PHASES,
        PHASE_FS,
        PHASE_NAMES,
        PHASE_PK,
        PHASE_RS,
        PHASE_SF,
        PHASE_TR,
        PHASE_W2,
        PHASE_WS,
        W_PHASES,
    )

    if state.is_terminal() or state.is_chance_node():
        raise ScenarioError("S-NOTDECISION")
    if state.hb_open:  # SCENARIOS 1.3: an open hut build is mid-turn
        raise ScenarioError("S-MIDTURN")
    if state.visit_loc:  # SCENARIOS 1.3: a supply-path visit in progress is mid-turn
        raise ScenarioError("S-MIDTURN")
    in_winter = state.phase in N_PHASES or state.phase in (PHASE_WS, PHASE_SF, PHASE_FS)
    if state.phase == PHASE_SF:  # SCENARIOS 3: SF is not a resting phase
        raise ScenarioError("S-MIDTURN")
    # RS / WS: a taken Overtime (before its DONE) sets w_dirty and is mid-turn: the dump would
    # not record that the holder has already decided (SCENARIOS 7).
    if state.phase in (PHASE_RS, PHASE_WS) and state.w_dirty:
        raise ScenarioError("S-MIDTURN")
    if (
        (state.phase in W_PHASES and state.phase != PHASE_W2)
        or (in_winter and state.phase != PHASE_WS)
    ) and (state.w_dirty or state.w_worker >= 0):
        raise ScenarioError("S-MIDTURN")  # a worker assigned or an action taken this turn
    comp = _components()
    game: Any = state.get_game()
    t = game.tables
    dr = state.draws
    n = state.n
    in_pk = state.phase == PHASE_PK or state.phase == PHASE_RS  # RS: Overtime node, picks follow
    seats: list[dict[str, Any]] = []
    for seat in range(n):
        f = state.foreman[seat]
        slot = state.clearing.index(seat) if seat in state.clearing else -1
        seats.append(
            {
                "money": state.money[seat],
                "loans": state.loans[seat],
                "hired": {
                    "woodcutters": state.hired_w[seat],
                    "bearers": state.hired_b[seat],
                    "sawyers": state.hired_s[seat],
                },
                "mill_worker_used": bool(state.mill_used[seat]),
                "task_taken": bool(state.task_taken[seat]),
                "fodder_bought": bool(state.fodder_bought[seat]),
                "foreman": "ABCD"[slot] if slot >= 0 else f,
                "cutting_area": (
                    None
                    if in_pk or in_winter
                    else state.picks[seat] + 1
                    if seat < len(state.picks)
                    else None
                ),
                "joiners": state.joiners[seat],
                "buildings": [comp.buildings[b].id for b in state.held_buildings[seat]],
                "huts": dict(zip(("drying", "food", "worker"), state.huts[seat], strict=True)),
                "equipment": dict(zip(EQUIP_SLOTS, state.equip[seat], strict=True)),
                "craftwork": dict(zip(CRAFT_ORDER, state.held_craft[seat], strict=True)),
                "food": state.food[seat],
                "fodder": {
                    "slot3": bool(state.fodder3[seat]),
                    "slot2": bool(state.fodder2[seat]),
                },
                "tasks": [
                    {
                        "id": comp.tasks[c].id,
                        "filled": [
                            r
                            for r in range(len(comp.tasks[c].requirements))
                            if state.filled[c] >> r & 1
                        ],
                    }
                    for c in state.held_tasks[seat]
                ],
                "firewood_storage": _logs(state.store[seat]),
                "drying": [_merge(_pieces(a[:3]), _logs(a[3:])) for a in state.dry[seat]],
                "joinery": [None if k < 0 else KIND_NAMES[k] for k in state.joinery_wood[seat]],
                "small_storage": _storage_piece(state.small_storage[seat]),
                "small_storage_spent": state.small_storage[seat] == STORAGE_SPENT,
                "woodpile": _pieces(state.woodpile[seat]),
                "sawing": _pieces(state.sawing[seat]),
                "sale": _merge(_pieces(state.sale[seat]), _logs(state.sale_logs[seat])),
                "river": _pieces(state.river[seat]),
            }
        )
    if in_pk:  # R-038, SCENARIOS 4.4: hidden picks of the seats before current_player
        for seat, area in enumerate(state.pk):
            seats[seat]["pick"] = area + 1
    areas = [
        {
            "wood": {"firewood": w[0], "softwood": w[1], "hardwood": w[2]},
            "food": state.area_food[a],
            "cut_lost": bool(state.cut_lost >> a & 1),  # R-099: reduced by an outside take
        }
        for a, w in enumerate(state.wood[:NUM_AREAS])
    ]
    side_tokens = {
        number: (None if y < 0 else "x" if SPOT_NAMES[y] == "x_marker" else SPOT_NAMES[y])
        for number, y in zip(t.token_spots, state.path_tokens, strict=not in_winter)
    }
    winter_years = {}
    for year, w in enumerate(dr.winter, start=1):
        cards = [c for c in comp.winter if c.year == year]
        winter_years[f"year{year}"] = {
            "card": cards[w // 2].id,
            "half": ("top", "bottom")[w % 2],
        }
    return {
        "format": 1,
        "parameters": {
            "players": n,
            "joinery": state.joinery,
            "returns": game.returns_mode,
            "easy_winter": game.easy_winter,
        },
        "round": state.round,
        "phase": PHASE_NAMES[state.phase],
        "current_player": state.current_player(),
        "turn_order": list(state.turn_order),
        "clearing_order": list(state.clearing)
        if state.phase == PHASE_TR or state.phase in W_PHASES
        else list(state.wint)
        if in_winter
        else None,
        "seats": seats,
        "cutting_areas": areas,
        "path": None
        if in_winter
        else {
            "bearers": state.path_b,
            "woodcutters": state.path_w,
            "sawyers_free": state.path_sf,
            "sawyers_paid": state.path_sp,
            "fodder": state.path_fodder,
            "joiner": state.path_joiner,
            "tokens": side_tokens,
        },
        "planned_work": {
            "laid_out": [comp.planned_work[c].id for c in dr.pw],
            "plans": [
                {"seat": seat, "card": comp.planned_work[c].id, "pair": pair, "target": target}
                for seat, c, pair, target in state.plans
            ],
        },
        "supply": {
            "tasks_laid_out": [comp.tasks[i].id for i in state.task_row],
            "placement_discarded": [comp.placement[i].id for i in state.placement_discarded],
            "winter": winter_years,
            "buildings": [comp.buildings[b].id for b in state.bld_supply],
            "craftwork_removed": {
                name: state.craft_removed[x] for x, name in enumerate(CRAFT_ORDER)
            },
        },
    }
