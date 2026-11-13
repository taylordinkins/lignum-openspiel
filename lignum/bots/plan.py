"""Long-term task planner (Phase 7 unit 6). Bot policy only; reusable by heuristic, solver, MCTS.

``task_plan(state, seat)`` is a pure function of the public state: it never reads the hidden
cutting-area picks (``state.picks``) and never mutates the state. For every task card the seat
holds it lists the required pieces (kind, milled, drying stage), the pieces already placed, and
for each missing piece the cheapest source (sale area, a drying area, sawing area, woodpile,
river, or wood not yet cut), the earliest W5 (Tasks phase) at which that piece can be placed, and
whether the whole card can be finished before the last placement (the round 8 N4 phase).

Timing follows the engine (R-055, R-058, R-059, R-069) and reuses the clock of
``lignum.bots.tasks.TaskPlanner``: rounds are indexed 1..7 without the first winter (round 8 = 7),
a log entering drying 1 at the W7 before W5 index ``i`` stands in area ``1 + s`` at ``i + s`` and
fits a stage-``s`` slot then, drying capacity is ``dry_cap_logs`` logs or ``dry_cap_disks`` disk
per entering round (a disk excludes logs), and nothing is placed or dried in the winter of year 1.

What it cannot see: the seat's hidden pick, other seats' competing cuts and the workers it will
hire. Wood not yet cut counts as obtainable when the public cutting areas hold enough of the
kind. A milled piece from a disk needs a saw in the equipment area or $ for one. All prices,
yields and capacities come from the engine tables (``SetupTables``) and ``data/components``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lignum.bots.tasks import Clock, TaskPlanner, _components, seq_index  # pyright: ignore[reportPrivateUsage]
from lignum.game import PHASE_N3, PHASE_W4, LignumState
from lignum.rules import SetupTables

KINDS = ("firewood", "softwood", "hardwood")
# next_step values, most urgent first
STEPS = ("place", "dry", "saw", "carry", "cut", "wait", "none")


@dataclass(frozen=True)
class Piece:
    kind: int  # 0 firewood, 1 softwood, 2 hardwood
    milled: bool
    stage: int  # drying stage the slot demands (0 = sale area or drying 1)

    def __str__(self) -> str:
        return f"{'milled' if self.milled else 'unmilled'} {KINDS[self.kind]} +{self.stage}"


@dataclass(frozen=True)
class Slot:
    index: int  # requirement index on the card
    piece: Piece
    placed: bool
    source: str  # placed, sale, dry1..dry3, sawing, woodpile, river, cut, none
    zone: int  # stock zone (0 sale, 1..3 drying) of ``source`` or -1
    ready: int | None  # W5 index at which the piece can be placed; None = never
    step: str  # one of STEPS for the work that moves this piece forward

    @property
    def piece_type(self) -> int:
        return 2 * self.piece.kind + int(self.piece.milled)


@dataclass(frozen=True)
class TaskPlan:
    task: int
    reward: int
    slots: tuple[Slot, ...]
    available: tuple[tuple[str, int], ...]  # (source, count) of wood of a still-needed kind
    finishable: bool
    reason: str
    slack: int  # rounds between the last placement and the latest missing piece
    done_by: int  # index of the W5 at which the last missing piece is placed
    next_step: str

    @property
    def missing(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if not s.placed)

    @property
    def placed(self) -> tuple[int, ...]:
        return tuple(s.index for s in self.slots if s.placed)

    @property
    def stock_pieces(self) -> tuple[tuple[int, int], ...]:
        """(zone, piece type) of the missing slots served from the sale / drying areas."""
        return tuple((s.zone, s.piece_type) for s in self.missing if s.zone >= 0)


@dataclass(frozen=True)
class Plan:
    round: int
    index: int  # seq index of the next W5
    last: int
    tasks: tuple[TaskPlan, ...]

    def get(self, task: int) -> TaskPlan | None:
        for tp in self.tasks:
            if tp.task == task:
                return tp
        return None


_PLANNERS: dict[int, tuple[SetupTables, TaskPlanner]] = {}


def _planner(t: SetupTables) -> TaskPlanner:
    hit = _PLANNERS.get(id(t))
    if hit is None or hit[0] is not t:
        hit = (t, TaskPlanner(t, {}))
        _PLANNERS[id(t)] = hit
    return hit[1]


class _Pool:
    """Disks of one kind in an upstream area: a disk is one unmilled piece or ``yield`` logs."""

    def __init__(self, disks: list[int], yields: tuple[int, int, int]) -> None:
        self.disks = list(disks)
        self.spare = [0, 0, 0]
        self.yields = yields

    def take(self, kind: int, milled: bool) -> bool:
        if milled:
            if self.spare[kind] > 0:
                self.spare[kind] -= 1
                return True
            if self.disks[kind] > 0:
                self.disks[kind] -= 1
                self.spare[kind] += max(1, self.yields[kind]) - 1
                return True
            return False
        if self.disks[kind] > 0:
            self.disks[kind] -= 1
            return True
        return False

    def has(self, kind: int, milled: bool) -> bool:
        return self.spare[kind] > 0 and milled or self.disks[kind] > 0


def _stock(state: LignumState, seat: int, t: SetupTables) -> dict[tuple[int, int], int]:
    return _planner(t)._stock(state, seat)  # pyright: ignore[reportPrivateUsage]


def _arrivals(state: LignumState, t: SetupTables, c: Clock, last: int) -> dict[str, int | None]:
    """W5 index at which wood in each upstream area is in the sale area (None = too late)."""
    rnd = state.round
    saw = c.arrive
    pile = c.arrive
    if rnd != t.winter_rounds[0] and (
        (rnd != t.winter_rounds[1] and state.phase == PHASE_W4)
        or (rnd == t.winter_rounds[1] and state.phase == PHASE_N3)
    ):
        pile += 1  # the carrying phase of this round is over: a bearer / sledge next round
    river = None if rnd == t.winter_rounds[1] else c.cut
    cut = c.cut
    out: dict[str, int | None] = {
        "sawing": saw,
        "woodpile": pile,
        "river": river if river is not None and river < last else None,
        "cut": cut if cut < last else None,  # no cutting in the winter of year 2
    }
    return {k: (v if v is not None and v <= last else None) for k, v in out.items()}


def _build(state: LignumState, seat: int, tasks: list[int]) -> Plan:
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    comps = _components().tasks
    pl = _planner(t)
    last = pl.last
    clock = pl._clock(state)  # pyright: ignore[reportPrivateUsage]
    arr = _arrivals(state, t, clock, last)
    stock = _stock(state, seat, t)
    cohort: dict[int, list[int]] = {}  # entering key -> [logs, disks]
    sawing = _Pool([int(x) for x in state.sawing[seat][:3]], t.sawing_yield)
    pile = _Pool([int(x) for x in state.woodpile[seat][:3]], t.sawing_yield)
    river = _Pool([int(x) for x in state.river[seat][:3]], t.sawing_yield)
    cut_n = [0, 0, 0]
    for area in state.wood:
        for k in range(3):
            cut_n[k] += int(area[k])
    cut = _Pool(cut_n, t.sawing_yield)
    pools = {"sawing": sawing, "woodpile": pile, "river": river, "cut": cut}
    saw_ok = bool(state.equip[seat][0]) or state.money[seat] >= t.price_saw
    held = state.held_tasks[seat]
    out: list[TaskPlan] = []

    def fits(key: int, milled: bool) -> bool:
        logs, disks = cohort.get(key, [0, 0])
        return (disks == 0 and logs < t.dry_cap_logs) if milled else (logs == 0 and disks < 1)

    def enter(key: int, milled: bool) -> None:
        row = cohort.setdefault(key, [0, 0])
        row[0 if milled else 1] += 1

    for ti in tasks:
        task = comps[ti]
        filled = state.filled[ti] if ti in held else 0
        slots: list[Slot] = []
        # hardest stage first so scarce drying capacity goes to the long-lead pieces
        order = sorted(range(len(task.requirements)), key=lambda r: -task.requirements[r].drying)
        by_idx: dict[int, Slot] = {}
        reasons: list[str] = []
        for r in order:
            req = task.requirements[r]
            piece = Piece(KINDS.index(req.kind), bool(req.milled), int(req.drying))
            if filled >> r & 1:
                by_idx[r] = Slot(r, piece, True, "placed", -1, None, "none")
                continue
            by_idx[r] = _slot(
                state,
                t,
                r,
                piece,
                clock,
                last,
                stock,
                pools,
                arr,
                cohort,
                saw_ok,
                reasons,
                fits,
                enter,
            )
        slots = [by_idx[r] for r in range(len(task.requirements))]
        missing = [s for s in slots if not s.placed]
        bad = [s for s in missing if s.ready is None]
        done_by = max((s.ready for s in missing if s.ready is not None), default=clock.first)
        finishable = not bad
        reason = "complete" if not missing else "ok"
        if bad:
            reason = reasons[0] if reasons else f"no source for {bad[0].piece}"
        steps = [s.step for s in missing]
        nxt = min(steps, key=STEPS.index) if steps and finishable else "none"
        avail: dict[str, int] = {}
        need_kinds = {(s.piece.kind, s.piece.milled) for s in missing}
        for (z, p), n in stock.items():
            if (p // 2, bool(p % 2)) in need_kinds:
                name = "sale" if z == 0 else f"dry{z}"
                avail[name] = avail.get(name, 0) + n
        for name, pool in pools.items():
            if name == "cut":
                continue
            n = sum(pool.disks[k] for k, _ in need_kinds) + sum(
                pool.spare[k] for k, m in need_kinds if m
            )
            if n:
                avail[name] = n
        out.append(
            TaskPlan(
                ti,
                task.reward,
                tuple(slots),
                tuple(sorted(avail.items())),
                finishable,
                reason,
                last - done_by if finishable else -1,
                done_by,
                nxt,
            )
        )
    return Plan(state.round, clock.first, last, tuple(out))


def _slot(
    state: LignumState,
    t: SetupTables,
    r: int,
    piece: Piece,
    clock: Clock,
    last: int,
    stock: dict[tuple[int, int], int],
    pools: dict[str, _Pool],
    arr: dict[str, int | None],
    cohort: dict[int, list[int]],
    saw_ok: bool,
    reasons: list[str],
    fits: Any,
    enter: Any,
) -> Slot:
    """Pick the source with the earliest placement for one missing piece and claim it."""
    pl = _planner(t)
    p = 2 * piece.kind + int(piece.milled)
    stage = piece.stage
    # candidates: (ready, priority, source, zone, key into pools/stock)
    cands: list[tuple[int, int, str, int]] = []
    for (z, q), n in stock.items():
        if q != p or n <= 0:
            continue
        at = pl._ready(z, stage, clock)  # pyright: ignore[reportPrivateUsage]
        if at is None:
            continue
        if z == 0 and stage:
            while not fits(at - stage, piece.milled) and at <= last:
                at += 1
        if at > last:
            continue
        cands.append((at, 0, "sale" if z == 0 else f"dry{z}", z))
    for pri, name in enumerate(("sawing", "woodpile", "river", "cut"), start=1):
        base = arr[name]
        if base is None or not pools[name].has(piece.kind, piece.milled):
            continue
        if name == "sawing" and not piece.milled:
            continue  # unmilled wood is not taken out of the sawing area
        if piece.milled and not saw_ok:
            continue
        at = base if stage == 0 else base + 1 + stage
        if stage:
            while not fits(at - stage, piece.milled) and at <= last:
                at += 1
        if at > last:
            continue
        cands.append((at, pri, name, -1))
    if not cands:
        anywhere = any(q == p and n > 0 for (_, q), n in stock.items()) or any(
            pool.has(piece.kind, piece.milled) for pool in pools.values()
        )
        if not anywhere:
            why = f"wood kind unobtainable: {piece}"
        elif piece.milled and not saw_ok:
            why = f"no saw for {piece}"
        elif stage:
            why = f"no drying time or capacity for {piece}"
        else:
            why = f"no time for {piece}"
        reasons.append(why)
        return Slot(r, piece, False, "none", -1, None, "none")
    at, _, name, zone = min(cands, key=lambda c: (c[0], c[1]))
    if name in pools:
        pools[name].take(piece.kind, piece.milled)
        step = {"sawing": "saw", "woodpile": "carry", "river": "wait", "cut": "cut"}[name]
        if name == "woodpile" and not piece.milled:
            step = "carry"
        if stage:
            enter(at - stage, piece.milled)
    else:
        q = p
        stock[(zone, q)] -= 1
        if zone == 0:
            step = "dry" if stage else "place"
            if stage:
                enter(at - stage, piece.milled)
        else:
            step = "place" if at == clock.first else "wait"
    return Slot(r, piece, False, name, zone, at, step)


def task_plan(state: LignumState, seat: int) -> Plan:
    """Plan for the unfinished tasks ``seat`` holds, the nearest to done first (they claim the
    wood first). Pure: reads only public state and the seat's own holdings."""
    comps = _components().tasks
    held = [
        h
        for h in state.held_tasks[seat]
        if state.filled[h] != (1 << len(comps[h].requirements)) - 1
    ]
    held.sort(
        key=lambda h: (
            len(comps[h].requirements) - bin(state.filled[h]).count("1"),
            -comps[h].reward,
        )
    )
    return _build(state, seat, held)


def candidate_plan(state: LignumState, seat: int, card: int) -> TaskPlan:
    """Plan of ``card`` (not yet held) allocated after the wood the held tasks claim."""
    held = [t.task for t in task_plan(state, seat).tasks]
    plan = _build(state, seat, [*held, card])
    tp = plan.get(card)
    assert tp is not None
    return tp


def task_take_ok(state: LignumState, seat: int, task_card: int, min_slack: int = 1) -> bool:
    """Whether to TAKE ``task_card``: finishable from the current board, with ``min_slack`` rounds
    to spare (R-055, R-056: an unfinished card pays nothing)."""
    tp = candidate_plan(state, seat, task_card)
    return tp.finishable and tp.slack >= min_slack


def task_worth(state: LignumState, seat: int, w: Mapping[str, Any]) -> dict[int, float]:
    """Value of each unfinished held task: ~0 (``dead_share`` of progress) when unfinishable,
    else ``finish_value`` x reward less ``cost_weight`` x the sale value of the missing pieces,
    plus reward/pieces x (``progress`` per placed piece + ``credit_<source>`` per missing piece,
    source = stock (sale / drying areas), sawing, woodpile, river, cut)."""
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    out: dict[int, float] = {}
    for tp in task_plan(state, seat).tasks:
        need = len(tp.slots)
        per = tp.reward / need
        if not tp.finishable:
            out[tp.task] = tp.reward * len(tp.placed) / need * w.get("dead_share", 0.0)
            continue
        cost = 0.0
        for s in tp.missing:
            cost += max(0, t.wood_price[s.piece.kind][int(s.piece.milled)]) + (
                t.dry_bonus[s.piece.stage + 1] if s.piece.stage else 0
            )
        got = w.get("progress", 0.0) * len(tp.placed)
        for s in tp.missing:  # how far each missing piece has come: sale / drying, sawing, ...
            got += w.get("credit_" + ("stock" if s.zone >= 0 else s.source), 0.0)
        out[tp.task] = (
            tp.reward * w.get("finish_value", 0.85) - cost * w.get("cost_weight", 0.3) + per * got
        )
    return out


def format_plan(plan: Plan) -> str:
    """Multi-line diagnostic text of a plan."""
    lines = [f"plan round {plan.round} next W5 index {plan.index} (last {plan.last})"]
    for tp in plan.tasks:
        lines.append(
            f"  task {tp.task} reward {tp.reward} finishable={tp.finishable} ({tp.reason}) "
            f"slack={tp.slack} next={tp.next_step}"
        )
        for s in tp.slots:
            where = "placed" if s.placed else f"{s.source} ready={s.ready} step={s.step}"
            lines.append(f"    slot {s.index}: {s.piece} -> {where}")
    return "\n".join(lines)


__all__ = [
    "Piece",
    "Plan",
    "Slot",
    "TaskPlan",
    "candidate_plan",
    "format_plan",
    "seq_index",
    "task_plan",
    "task_take_ok",
    "task_worth",
]
