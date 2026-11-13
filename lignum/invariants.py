"""Invariant checker for random simulations (PLAN.md section 6 item 2; SCENARIOS.md section 7).

``check_invariants`` returns the violations found in one state; ``assert_invariants`` raises.
Only what the Phase 2 state records is checked. Impossible or vacuous checks:

* Equipment, wood, food and money are not conserved (R-009), so only limits are checked
  (saws <= max, equipment tokens on the path <= the R-017 recipe).
* Buildings are not modelled in the state yet (no huts or held buildings); only the drawn
  building set is checked. Planned-work plans are checked per SCENARIOS.md S-PW (pair
  unused, target = made round + pair, printed season, no duplicate card/target, one plan per
  seat per made round); "plans only grow" needs two states and is not checked.
* Drying over-capacity is a warning in SCENARIOS.md S-DRY because huts and PW Drying can cause it.
  Here it is an error until a hut has been built (``hut_built``); afterwards it is not checked.
* Fodder on the path is only restocked at the round start, so its conservation is checked in
  the phases where the path exists (not in winter).
* Returns are checked in the game's own ``returns`` mode; the test grid runs both modes.

Constants come from the game's setup tables (``lignum.rules.SetupTables``), never hard-coded.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any

import pyspiel

from lignum.components import Task, load_components
from lignum.constants import MAX_JOINERS
from lignum.rules import (
    CRAFT_ORDER,
    EQUIP_SLOTS,
    FIRST_CRAFT_SPOT,
    SPOT_NAMES,
    building_param,
    has_building,
    plan_param,
)

if TYPE_CHECKING:
    from lignum.game import LignumState


@cache
def _tasks() -> tuple[Task, ...]:
    return load_components().tasks


class InvariantError(AssertionError):
    """One or more invariants failed; the message lists them."""


def check_invariants(state: pyspiel.State) -> list[str]:
    """Return the violated invariants of ``state`` (empty when it is consistent)."""
    from lignum import game as G
    from lignum.woodwork import NO_SLOT, STORAGE_SPENT

    s: LignumState = state  # type: ignore[assignment]
    out: list[str] = []
    game: Any = s.get_game()
    t = game.tables
    n = s.n
    phase = G.PHASE_NAMES[s.phase]

    def bad(msg: str) -> None:
        out.append(f"[{phase} r{s.round}] {msg}")

    # -- flow -------------------------------------------------------------------------------
    if s.is_terminal():
        r = s.returns()
        # margin returns are clipped at +-1 and then not zero-sum for n >= 3 (R-086)
        clipped = game.returns_mode == "margin" and n >= 3 and any(abs(x) >= 1.0 for x in r)
        if len(r) != n or (abs(sum(r)) > 1e-6 and not clipped):
            bad(f"returns {r} do not sum to 0")
        if len(s.final) != n:
            bad("terminal state without final dollars")
        return out
    if s.is_chance_node():
        outcomes = s.chance_outcomes()
        if not outcomes:
            bad("chance node without outcomes")
        elif abs(sum(p for _, p in outcomes) - 1.0) > 1e-6:
            bad("chance probabilities do not sum to 1")
    else:
        if not 0 <= s.current_player() < n:
            bad(f"bad current player {s.current_player()}")
        elif not s.legal_actions():
            bad("non-terminal decision node without a legal action")
    if sorted(s.turn_order) != list(range(n)):
        bad(f"turn_order {s.turn_order} is not a permutation")

    # -- limits -----------------------------------------------------------------------------
    for seat in range(n):
        if s.money[seat] < 0:
            bad(f"P{seat} money {s.money[seat]} < 0")
        if not 0 <= s.loans[seat] <= t.max_loans:
            bad(f"P{seat} loans {s.loans[seat]}")
        if s.equip[seat][EQUIP_SLOTS.index("saw")] > t.max_saws:
            bad(f"P{seat} holds more than {t.max_saws} saws")
        if min(s.equip[seat]) < 0 or s.food[seat] < 0 or min(s.held_craft[seat]) < 0:
            bad(f"P{seat} negative equipment, food or craftwork")
        if not 0 <= s.joiners[seat] <= MAX_JOINERS:
            bad(f"P{seat} joiners {s.joiners[seat]}")
        if s.joiners[seat] and not s.joinery:
            bad(f"P{seat} has joiners without joinery")
        if s.fodder2[seat] not in (0, 1) or s.fodder3[seat] not in (0, 1):
            bad(f"P{seat} fodder flags")

    # -- workers (S-WORKERS) ----------------------------------------------------------------
    winter = s.phase >= G.PHASE_WS
    no_hired = winter or s.phase in (G.PHASE_SC, G.PHASE_SP, G.PHASE_RS, G.PHASE_PK)
    for name, path, hired, total in (
        ("bearers", s.path_b, s.hired_b, t.path_bearers),
        ("woodcutters", s.path_w, s.hired_w, t.path_woodcutters),
        ("sawyers", s.path_sf + s.path_sp, s.hired_s, t.path_sawyers_free + t.path_sawyers_paid),
    ):
        if path < 0 or min(hired) < 0:
            bad(f"negative {name}")
        if path + sum(hired) != total:
            bad(f"{name}: path {path} + hired {sum(hired)} != {total}")
        if no_hired and sum(hired):
            bad(f"{name} hired outside the round")
    for seat in range(n):
        if not (
            0 <= s.cut_used[seat] <= s.hired_w[seat]
            and 0 <= s.bear_used[seat] <= s.hired_b[seat]
            and 0 <= s.saw_used[seat] <= s.hired_s[seat]
        ):
            bad(f"P{seat} used more workers than hired")
        if s.mill_used[seat] not in (0, 1):
            bad(f"P{seat} mill_used {s.mill_used[seat]}")
    if max(s.hired_s) > 2:
        bad("a seat hired more than 2 sawyers")
    if s.path_sf < 0 or s.path_sp < 0:
        bad("negative sawyers on the path")

    # -- turn-local state is clean outside its phases -------------------------------------
    if s.phase not in (G.PHASE_W1, G.PHASE_W3, G.PHASE_W4, *G.N_PHASES[1:4]) and (
        s.w_worker != -1 or s.trip_kind != G.TRIP_NONE
    ):
        bad("worker or trip state left over outside the wood-work phases")
    if s.phase != G.PHASE_TR and s.visit_loc != 0:
        bad("an open path visit outside TR")
    if s.phase != G.PHASE_PK and s.pk:
        bad("hidden picks outside PK")
    if s.phase != G.PHASE_RS and s.rd is not None:
        bad("round-start draws outside RS")
    if s.ot_q and s.phase not in (G.PHASE_RS, G.PHASE_WS):
        bad("Overtime nodes pending outside RS / WS")
    if s.w_out > plan_param(t, "pw_cutting", "workers_moved") or s.w_ld > 1:
        bad("PW Cutting / Log Driving used beyond its limit in one turn")
    if s.phase != G.PHASE_FS and s.fs_pending:
        bad("final-sale choosers pending outside FS")

    # -- fodder ------------------------------------------------------------------------------
    if not winter and s.path_fodder + sum(s.fodder_bought) != t.path_fodder:
        bad(f"fodder: path {s.path_fodder} + bought {sum(s.fodder_bought)} != {t.path_fodder}")

    # -- joiners (S-JOINERS) -----------------------------------------------------------------
    if s.joinery:
        if s.path_joiner + sum(s.joiners) > t.joiner_supply:
            bad(f"joiners: path {s.path_joiner} + held {sum(s.joiners)} > {t.joiner_supply}")
        if s.phase in (G.PHASE_RS, G.PHASE_PK) and s.path_joiner != (
            1 if sum(s.joiners) < t.joiner_supply else 0
        ):
            bad("Joiner location not restocked correctly at the round start")
    elif s.path_joiner:
        bad("joiner on the path without joinery")

    # -- buildings (S-BUILDINGS): drawn set only ---------------------------------------------
    b = s.draws.buildings
    if len(set(b)) != len(b):
        bad("a building drawn twice")
    if s.phase > G.PHASE_SP:
        expected = t.sequence.count("BUILDING_DRAW")
        if len(b) != expected:
            bad(f"{len(b)} buildings drawn, expected {expected}")

    # -- craftwork and tokens (S-TOKENS, S-CRAFT) -------------------------------------------
    if s.phase > G.PHASE_SC and not winter:
        on_path = [0] * len(CRAFT_ORDER)
        equip_on_path: dict[str, int] = {}
        for y in s.path_tokens:
            if y >= FIRST_CRAFT_SPOT:
                on_path[y - FIRST_CRAFT_SPOT] += 1
            elif y >= 0:
                equip_on_path[SPOT_NAMES[y]] = equip_on_path.get(SPOT_NAMES[y], 0) + 1
        for x, name in enumerate(CRAFT_ORDER):
            held = sum(c[x] for c in s.held_craft)
            total = s.craft_pile[x] + on_path[x] + held + s.craft_removed[x]
            if total != t.craft_totals[x] or s.craft_pile[x] < 0:
                bad(f"craftwork {name}: {total} != {t.craft_totals[x]}")
        from lignum.rules import EQUIPMENT_ORDER

        for i, name in enumerate(EQUIPMENT_ORDER):
            if equip_on_path.get(name, 0) > t.equipment[i]:
                bad(f"more {name} tokens on the path than the recipe ({t.equipment[i]})")

    # -- huts (S-LIMITS, token conservation, R-100..R-103) ----------------------------------
    if any(min(h) < 0 for h in s.huts):
        bad("negative hut tokens")
    if sum(map(sum, s.huts)) + s.hut_spent != s.hut_built:
        bad("hut tokens built != unspent + spent")
    if s.hut_built > sum(s.craft_removed):
        bad("more hut tokens than flipped craftwork tokens")

    # -- wood zones --------------------------------------------------------------------------
    zones = (s.woodpile, s.river, s.sawing, s.sale, s.sale_logs, s.store, s.wood)
    for rows in zones:
        if any(min(row) < 0 for row in rows):
            bad("negative wood count")
    if any(min(a) < 0 for rows in s.dry for a in rows):
        bad("negative drying count")
    if any(a[2] for rows in s.dry for a in rows):
        bad("unmilled hardwood in a drying area")

    # -- drying capacity (S-DRY; an error here, see the module docstring) ---------------------
    for seat, areas in enumerate(s.dry):
        # PW Drying (R-096): from its target round on, a doubled stack may stand over capacity
        mult = 1
        for pl in s.plans:
            if pl[0] == seat and t.pw_ids[pl[1]] == "pw_drying" and pl[3] <= s.round:
                mult = max(mult, plan_param(t, "pw_drying", "first_area_capacity_multiplier"))
        for i, a in enumerate(areas):
            disks, logs = sum(a[:3]), sum(a[3:])
            if s.hut_built:  # huts may overfill an area and mix disks with logs (R-101); global:
                continue  # no per-seat count of built huts is kept (unspent tokens only)
            if has_building(t, s.held_buildings, seat, "drying_area_upgrade"):
                cap = building_param(t, "drying_area_upgrade", "drying_area_capacity")
                if disks + logs > cap * mult:
                    bad(f"P{seat} drying {i + 1} over capacity")
                continue
            if disks and logs:
                bad(f"P{seat} drying {i + 1}: disk with logs")
            if disks > t.dry_cap_disks * mult or logs > t.dry_cap_logs * mult:
                bad(f"P{seat} drying {i + 1} over capacity")

    # -- tasks and joinery wood (locked) --------------------------------------------------------
    ntasks = len(s.filled)
    held_all = [c for h in s.held_tasks for c in h]
    if len(set(held_all)) != len(held_all):
        bad("a task held twice")
    if set(held_all) & set(s.task_row):
        bad("a task both laid out and held")
    if len(set(s.task_row)) != len(s.task_row):
        bad("a task laid out twice")
    if not set(held_all) | set(s.task_row) <= set(s.tasks_seen):
        bad("task not in tasks_seen")
    tasks = _tasks()
    for c in range(ntasks):
        if s.filled[c] >> len(tasks[c].requirements):
            bad(f"task {tasks[c].id}: filled bit out of range")
        if s.filled[c] and c not in held_all:
            bad(f"task {tasks[c].id}: requirements filled but not held")
    for seat in range(n):
        kinds = [k for k in s.joinery_wood[seat] if k != NO_SLOT]
        if len(set(kinds)) != len(kinds):
            bad(f"P{seat} joinery wood kinds repeat")
        if kinds and not s.joinery:
            bad(f"P{seat} joinery wood without joinery")
        if len(s.joinery_wood[seat]) != MAX_JOINERS:
            bad(f"P{seat} joinery slots")
        stored = s.small_storage[seat]  # R-114: one piece per game, only with the building
        if stored not in (NO_SLOT, 0, 1, 2, STORAGE_SPENT):
            bad(f"P{seat} small storage state {stored}")
        elif stored != NO_SLOT and not has_building(
            t, s.held_buildings, seat, "small_storage_area"
        ):
            bad(f"P{seat} small storage used without the building")
    # -- planned work (S-PW) ----------------------------------------------------------------
    seen_pairs: set[tuple[int, int]] = set()
    seen_targets: set[tuple[int, int, int]] = set()
    seen_made: set[tuple[int, int]] = set()
    for seat, card, pair, target in s.plans:
        made = target - pair
        if not 1 <= pair <= t.pw_pairs or (seat, pair) in seen_pairs:
            bad(f"P{seat} plan pair {pair} invalid or reused")
        if not 1 <= made <= s.round or target > 8:
            bad(f"P{seat} plan target {target} out of range for pair {pair}")
        elif (target - 1) % 4 not in t.pw_seasons[card]:
            bad(f"P{seat} plan card {card} not printed for target round {target}")
        if (seat, card, target) in seen_targets:
            bad(f"P{seat} plans card {card} for target {target} twice")
        if (seat, made) in seen_made:
            bad(f"P{seat} plans twice in round {made}")
        seen_pairs.add((seat, pair))
        seen_targets.add((seat, card, target))
        seen_made.add((seat, made))
    return out


def assert_invariants(state: pyspiel.State) -> None:
    """Raise ``InvariantError`` listing every violation, with the action history."""
    problems = check_invariants(state)
    if problems:
        raise InvariantError("; ".join(problems) + f"\nhistory: {state.history()}")
