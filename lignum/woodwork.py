"""Wood-work legality, phases W1..W3 (R-045..R-053). Pure: no pyspiel, no I/O.

Each function returns the legal decisions as (name, params) pairs; ``LignumState`` encodes them
and applies the effects. Kinds are 0 firewood, 1 softwood, 2 hardwood; destinations are 0 sawing
area, 1 sale area (ACTIONS 1.5).
"""

from __future__ import annotations

from typing import Protocol

from lignum.rules import (
    EQUIP_SLOTS,
    SetupTables,
    building_param,
    has_building,
    plan_active,
    plan_param,
)

HARDWOOD = 2
SRC_HIRED = 0
SRC_MILL = 1
SRC_HUT = 2  # a hut worker token (R-103)
HUT_WORKER = 2  # index of the worker area in ``huts``
SRC_PAIR = -2  # w_worker while PW Sawing's second disk of a worker is open (R-092)
TRIP_NONE, TRIP_WAGON, TRIP_RAFT, TRIP_SLEDGE, TRIP_PW = 0, 1, 2, 3, 4
IDX_WAGON = EQUIP_SLOTS.index("wagon")
IDX_RAFT = EQUIP_SLOTS.index("raft")

IDX_SAW = EQUIP_SLOTS.index("saw")
IDX_SLEDGE = EQUIP_SLOTS.index("sledge")
NO_SLOT = -1  # empty joinery slot; also an empty, never-used Small Storage Area (R-114)
STORAGE_SPENT = 3  # Small Storage Area whose piece has moved to a task (R-114)
ZERO6 = (0, 0, 0, 0, 0, 0)
# Source zones for SELL (ACTIONS 1.5): 0 sale area, 1..3 drying areas.
ZONE_SALE, ZONE_D1, ZONE_D2, ZONE_D3 = 0, 1, 2, 3

Move = tuple[str, tuple[int, ...]]
Counts = tuple[int, int, int]


class WoodState(Protocol):
    """The slice of the game state the wood-work rules read (structural; see ``LignumState``)."""

    picks: tuple[int, ...]
    wood: tuple[Counts, ...]
    money: tuple[int, ...]
    loans: tuple[int, ...]
    hired_w: tuple[int, ...]
    hired_b: tuple[int, ...]
    equip: tuple[tuple[int, int, int, int], ...]
    fodder3: tuple[int, ...]
    fodder2: tuple[int, ...]
    woodpile: tuple[Counts, ...]
    river: tuple[Counts, ...]
    mill_used: tuple[int, ...]
    cut_used: tuple[int, ...]
    bear_used: tuple[int, ...]
    wcut: tuple[int, ...]
    clearing: tuple[int, ...]
    w_turn: int
    w_worker: int
    w_took: int
    w_moved: int
    trip_kind: int
    trip_n: int
    w_ld: int
    w_wc: int
    held_buildings: tuple[tuple[int, ...], ...]
    w_out: int
    w_outa: int
    cut_lost: int
    joinery: bool
    held_tasks: tuple[tuple[int, ...], ...]
    filled: tuple[int, ...]
    hired_s: tuple[int, ...]
    saw_used: tuple[int, ...]
    sawing: tuple[Counts, ...]
    sale: tuple[Counts, ...]
    sale_logs: tuple[Counts, ...]
    dry: tuple[tuple[tuple[int, ...], ...], ...]
    joinery_wood: tuple[tuple[int, ...], ...]
    small_storage: tuple[int, ...]
    w_dirty: int
    food: tuple[int, ...]
    store: tuple[Counts, ...]
    sf_due: int
    round: int
    plans: tuple[tuple[int, int, int, int], ...]
    huts: tuple[tuple[int, int, int], ...]


def _loan(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    return [("TAKE_LOAN", ())] if s.loans[seat] < t.max_loans else []


def _placements(pile: Counts) -> list[Move]:
    """MOVE_WOOD(k, d) for the kinds in ``pile``; unmilled hardwood only to the sawing area
    (R-046)."""
    out: list[Move] = []
    for k, count in enumerate(pile):
        if count:
            out.append(("MOVE_WOOD", (k, 0)))
            if k != HARDWOOD:
                out.append(("MOVE_WOOD", (k, 1)))
    return out


def outside_areas(t: SetupTables, s: WoodState, seat: int) -> list[int]:
    """Implements R-099 item 2: other cutting areas holding wood into which the seat may still
    send a worker (PW Cutting target round, fewer than 2 workers out, all in one area)."""
    if not plan_active(t, s, seat, "pw_cutting") or s.w_out >= plan_param(
        t, "pw_cutting", "workers_moved"
    ):
        return []
    own = s.picks[seat]
    return [a for a in range(len(s.wood)) if a != own and sum(s.wood[a]) and s.w_outa in (-1, a)]


def w1_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-047, R-048, R-099 (O-U2-5, O-U2-10): decisions of the acting seat in W1."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    area = s.picks[seat]
    pile = s.wood[area]
    outside = outside_areas(t, s, seat)
    if s.w_worker >= 0:
        out += [("TAKE_WOOD", (area, k)) for k, c in enumerate(pile) if c]
        out += [("TAKE_WOOD", (a, k)) for a in outside for k, c in enumerate(s.wood[a]) if c]
    elif sum(pile) or outside:
        if s.hired_w[seat] - s.cut_used[seat] > 0:
            out.append(("ASSIGN_WORKER", (SRC_HIRED,)))
        if not s.mill_used[seat]:
            out.append(("ASSIGN_WORKER", (SRC_MILL,)))
        if s.huts[seat][HUT_WORKER]:
            out.append(("ASSIGN_WORKER", (SRC_HUT,)))
    sharing = any(s.picks[e] == area for e in s.clearing[: s.w_turn])
    lost = bool(s.cut_lost >> area & 1)  # user ruling 2026-11-06: outside take reduced the area
    if (sharing or lost) and not s.w_took and not s.w_moved and s.money[seat] >= t.token_move_price:
        taken = set(s.picks)
        out += [("MOVE_CUT_TOKEN", (a,)) for a in range(len(s.wood)) if a not in taken]
    return out


def w2_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-049: the arriving river pieces must be placed; no DONE."""
    return _loan(t, s, seat) + _placements(s.river[seat])


def wc_moves(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-107: WC_MOVE(k, d), a just-placed river piece arriving at once; once per
    transport phase (turn) of the seat, hardwood disks only to the sawing area (R-046)."""
    if s.w_wc >= building_param(
        t, "waterchannel", "immediate_pieces_per_transport_phase"
    ) or not has_building(t, s.held_buildings, seat, "waterchannel"):
        return []
    return [
        ("WC_MOVE", (k, d))
        for k, c in enumerate(s.woodpile[seat])
        if c
        for d in (0, 1)
        if not (k == HARDWOOD and d == 1)
    ]


def w3_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-050..R-053: decisions of the acting seat in W3 (trips, ACTIONS 5.8)."""
    out = _loan(t, s, seat)
    pile = s.woodpile[seat]
    if s.trip_kind == TRIP_WAGON:
        out += _placements(pile)
    elif s.trip_kind in (TRIP_PW, TRIP_RAFT):  # R-098: the PW trip spends no raft
        out += [("RIVER_MOVE", (k,)) for k, c in enumerate(pile) if c]
        out += wc_moves(t, s, seat)
    elif s.w_worker >= 0:
        out += _placements(pile)
        # user decision 2026-11-05: a trip is offered only if a piece can move afterwards
        if sum(pile) and s.equip[seat][IDX_WAGON] and (s.fodder3[seat] or s.fodder2[seat]):
            out.append(("USE_WAGON", ()))
        if s.equip[seat][IDX_RAFT]:
            out += [("RIVER_MOVE", (k,)) for k, c in enumerate(pile) if c]
            out += wc_moves(t, s, seat)
    elif sum(pile):
        if not s.w_ld and plan_active(t, s, seat, "pw_log_driving"):
            out.append(("USE_PW_LOGDRIVING", ()))  # R-098: one trip per turn, either order
        if s.hired_b[seat] - s.bear_used[seat] > 0:
            out.append(("ASSIGN_WORKER", (SRC_HIRED,)))
        if not s.mill_used[seat]:
            out.append(("ASSIGN_WORKER", (SRC_MILL,)))
        if s.huts[seat][HUT_WORKER]:
            out.append(("ASSIGN_WORKER", (SRC_HUT,)))
    if s.trip_kind != TRIP_NONE:
        if s.trip_n >= 1:  # user decision 2026-11-05: END_TRIP is the only early exit
            out.append(("END_TRIP", ()))
    else:
        out.append(("DONE", ()))
    return out


def piece_idx(p: int) -> int:
    """Index of piece p = 2*kind + milled (ACTIONS 1.5) in a 6-vector of disks then logs."""
    return p // 2 + 3 * (p % 2)


def zone_count(s: WoodState, seat: int, zone: int, p: int) -> int:
    """Pieces of type p in the sale area (zone 0) or drying area ``zone`` (1..3)."""
    if zone == ZONE_SALE:
        kind = p // 2
        return (s.sale_logs if p % 2 else s.sale)[seat][kind]
    return s.dry[seat][zone - 1][piece_idx(p)]


def saw_yield(t: SetupTables, s: WoodState, seat: int, kind: int) -> int:
    """Implements R-054, R-094: logs from one disk; PW Heating Supply makes firewood yield more."""
    if kind == 0 and plan_active(t, s, seat, "pw_heating_supply"):
        return int(plan_param(t, "pw_heating_supply", "logs_per_firewood_disk"))
    return t.sawing_yield[kind]


def w4_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-054: sawing. A sawyer (or the unused mill worker) and a saw per disk; the
    logs are placed at once by SAW(kind, n logs to storage)."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    disks = s.sawing[seat]
    if s.w_worker >= 0 or s.w_worker == SRC_PAIR:
        for k, c in enumerate(disks):
            if c:
                out += [("SAW", (k, n)) for n in range(saw_yield(t, s, seat, k) + 1)]
    if s.w_worker < 0 and s.equip[seat][IDX_SAW] and sum(disks):
        if s.hired_s[seat] - s.saw_used[seat] > 0 and s.round not in t.winter_rounds:
            out.append(("ASSIGN_WORKER", (SRC_HIRED,)))
        if not s.mill_used[seat]:
            out.append(("ASSIGN_WORKER", (SRC_MILL,)))
        if s.huts[seat][HUT_WORKER]:
            out.append(("ASSIGN_WORKER", (SRC_HUT,)))
    return out


def w5_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-055, R-057: task and joinery placement from the sale and drying areas."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    held = s.held_tasks[seat]
    final = s.round == t.winter_rounds[1]  # R-114: the stored piece moves in round 8 only
    stored = s.small_storage[seat] if final else NO_SLOT
    for slot, (task, req, kind, milled, stage) in enumerate(t.task_slots):
        if task not in held or s.filled[task] >> req & 1:
            continue
        mine = (kind, milled, stage)
        if any(  # identical free requirements are filled lowest slot first (ACTIONS 1.6)
            tk == task and rq < req and not s.filled[task] >> rq & 1 and (kd, ml, sg) == mine
            for tk, rq, kd, ml, sg in t.task_slots
        ):
            continue
        p = 2 * kind + milled
        if zone_count(s, seat, (ZONE_SALE, ZONE_D2, ZONE_D3)[stage], p):
            out.append(("PLACE_TASK", (slot, 0)))
        if stage == 0 and zone_count(s, seat, ZONE_D1, p):
            out.append(("PLACE_TASK", (slot, 1)))
        if milled and 0 <= stored < 3 and stored == kind:  # R-114, O-U4-12: any stage
            out.append(("PLACE_TASK", (slot, 2)))
    if (
        has_building(t, s.held_buildings, seat, "small_storage_area")
        and building_param(t, "small_storage_area", "capacity") >= 1  # state: one piece
        and s.small_storage[seat] == NO_SLOT
    ):  # R-114: one piece per game, committed while empty and never used
        out += [
            ("STORE_PIECE", (k, z))
            for k in range(3)
            for z in range(4)
            if zone_count(s, seat, z, 2 * k + 1)
        ]
    if s.joinery:
        placed = s.joinery_wood[seat]
        for k in range(3):
            if k not in placed and zone_count(s, seat, ZONE_D2, 2 * k + 1):
                out += [("PLACE_JOINERY", (k, q)) for q in range(3) if placed[q] == NO_SLOT]
    return out


def w6_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-058: sell sale-area and drying wood; DONE only once drying 3 is empty."""
    out = _loan(t, s, seat)
    if not any(s.dry[seat][2]):
        out.append(("DONE", ()))
    for z in range(4):
        for p in range(6):
            if t.wood_price[p // 2][p % 2] >= 0 and zone_count(s, seat, z, p):
                out.append(("SELL", (z, p)))
    return out


def w7_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-059 (A7): the forced advance happens at the first DRY_ENTER or at DONE, so
    drying 1 is treated as empty until then; sale wood enters drying 1 under its capacity."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    d1 = s.dry[seat][0] if s.w_dirty else ZERO6
    disks, logs = sum(d1[:3]), sum(d1[3:])
    mult = 1  # R-096: PW Drying doubles the first area in its target round
    if plan_active(t, s, seat, "pw_drying"):
        mult = plan_param(t, "pw_drying", "first_area_capacity_multiplier")
    upgraded = 0
    if has_building(t, s.held_buildings, seat, "drying_area_upgrade"):
        upgraded = building_param(t, "drying_area_upgrade", "drying_area_capacity")
    for p in range(6):
        if not zone_count(s, seat, ZONE_SALE, p):
            continue
        if upgraded:  # R-111: any mix of pieces up to the building's capacity
            fits = disks + logs < upgraded * mult
        elif p % 2:
            fits = not disks and logs < t.dry_cap_logs * mult
        else:
            fits = not logs and disks < t.dry_cap_disks * mult
        if fits:
            out.append(("DRY_ENTER", (p,)))
    return out


# --- winter (R-064..R-073)


def overtime_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-097 / ACTIONS 5.9: the holder's RS/WS node; TAKE_OVERTIME (once), then DONE."""
    take = [] if s.w_dirty else [("TAKE_OVERTIME", ())]
    return [*_loan(t, s, seat), ("DONE", ()), *take]


def nb_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-065: one unmilled disk of any kind from the supply, or decline; DONE ends."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    if not s.w_dirty:
        out += [("TAKE_BONUS", (k,)) for k in range(3)]
    return out


def n1_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-066, R-103: the mill worker (once a round, C6) or a hut worker cuts."""
    out = _loan(t, s, seat)
    out.append(("DONE", ()))
    if s.w_worker >= 0:
        out.append(("WINTER_CUT", ()))
    else:
        if not s.mill_used[seat]:
            out.append(("ASSIGN_WORKER", (SRC_MILL,)))
        if s.huts[seat][HUT_WORKER]:
            out.append(("ASSIGN_WORKER", (SRC_HUT,)))
    return out


def n2_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-067: sledge trip of up to 2 pieces, 1 more per food (up to 3 food)."""
    out = _loan(t, s, seat)
    pile = s.woodpile[seat]
    if s.trip_kind == TRIP_SLEDGE:
        if s.trip_n < t.sledge_free or (
            s.food[seat] > 0 and s.trip_n < t.sledge_free + t.sledge_food
        ):
            out += _placements(pile)
        if s.trip_n >= 1:
            out.append(("END_TRIP", ()))
        return out
    out.append(("DONE", ()))
    if s.w_worker >= 0:
        if sum(pile) and s.equip[seat][IDX_SLEDGE]:
            out.append(("USE_SLEDGE", ()))
    elif sum(pile) and s.equip[seat][IDX_SLEDGE]:
        if not s.mill_used[seat]:
            out.append(("ASSIGN_WORKER", (SRC_MILL,)))
        if s.huts[seat][HUT_WORKER]:
            out.append(("ASSIGN_WORKER", (SRC_HUT,)))
    return out


def n4_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-069: no placement in the winter of year 1; round 8 follows R-055/R-057."""
    if s.round == t.winter_rounds[0]:
        return [*_loan(t, s, seat), ("DONE", ())]
    return w5_actions(t, s, seat)


def sellable_winter(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-073 step 3: SELL(zone, piece) options; the sawing area (zone 4) and the
    firewood storage (zone 5) only once zones 0..3 hold nothing sellable."""
    first: list[Move] = []
    for z in range(4):
        for p in range(6):
            if t.wood_price[p // 2][p % 2] >= 0 and zone_count(s, seat, z, p):
                first.append(("SELL", (z, p)))
    if first:
        return first
    out: list[Move] = []
    for p in range(6):
        if t.wood_price[p // 2][p % 2] < 0:
            continue
        if p % 2 == 0 and s.sawing[seat][p // 2]:
            out.append(("SELL", (4, p)))
        if p % 2 == 1 and s.store[seat][p // 2]:
            out.append(("SELL", (5, p)))
    return out


def sf_actions(t: SetupTables, s: WoodState, seat: int) -> list[Move]:
    """Implements R-073: loans first (the only action while short and loans remain), then
    selling only once loans cannot cover the bill (extra sales continue once covered), DONE once
    covered or nothing sells."""
    short = s.money[seat] < s.sf_due
    if short and s.loans[seat] < t.max_loans:
        return [("TAKE_LOAN", ())]
    # Selling starts only when loans cannot cover the bill (step 3), then continues freely.
    out = sellable_winter(t, s, seat) if short or s.w_dirty else []
    if not short or not out:
        out.append(("DONE", ()))
    return out
