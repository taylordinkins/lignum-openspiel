"""Per-seat money ledger: splits each seat's final dollars (R-083) by component.

The engine only exposes the money total, so the ledger observes the game from outside: every
``apply_action`` of the traced state runs with ``lignum.game._bump`` swapped for a recorder that
sees each change to ``state.money`` together with the engine function making it. Nothing in the
engine changes, and bots search on their own clones, so only the real game is traced (and the
swap lives only for the duration of one apply, so bot timings are not slowed).

Components (names follow ``lignum.bots.value``'s terms; with ``start`` they sum to the final
dollars exactly). Engine function (or action) each is read from:

  wood_sales      R-058 sales, R-081 steps 1-2: _sell, _sell_river, _begin_final_sale
  joinery         R-082 covered pieces at the final sale: _begin_final_sale, split from the same
                  engine payout with the covered pieces priced from the setup tables
  tasks           R-056 completed task rewards: _advance_final_sale
  office          R-116 Office bonus (an Office owner's first payout there): _advance_final_sale
  craftwork       R-105 sets sold: _acquire with SELL_SET / SELL_SET_JOKERS
  winter          R-071..R-073 shortfall payments, D9 forgiveness: _settle, _next_winter_turn
  loan_proceeds   R-075 money taken from loans: TAKE_LOAN
  loan_repayment  R-077 repayment at the end (not an engine bump): -loan_repay[loans]
  joiner_income   R-079 $ per joiner at a seasonal round start: the one direct write to money,
                  so it is the money change left over after an apply
  spending        hiring, fodder, saws, planned work, food, tasks, token moves: _acquire,
                  MOVE_CUT_TOKEN
  other_income    $ token spot, food and equipment sales: _take_token, _acquire
  unattributed    engine money change from an unknown caller (must be 0; breakdown/detail raise)
  start           starting money (setup data)

Sub-components (``Ledger.detail()``, additive: ``breakdown()`` and COMPONENTS are unchanged).
Each group sums to its parent component exactly:

  winter    = feed_shortfall + heat_shortfall (dollars actually paid for missing units, R-073;
              units come from stock for free)
  spending  = hire_bearer + hire_woodcutter + hire_sawyer + fodder + saws + planned_work + food
              + tasks_bought + cut_token + buildings + other   ("buildings" is free by R-106, so
              it stays 0; "other" catches any unnamed purchase)

Memo items (``winter_info``; units or money already counted in another component, so they are
not part of any sum): feed/heat required, from_stock and missing units, the price per missing
unit, forgiven dollars (D9, not money), forced loans (TAKE_LOAN in the R-073 shortfall step,
proceeds counted in loan_proceeds) and forced sales (SELL in that step, counted in wood_sales).

Funnels (``Ledger.funnels()``, valid at any point of a game): tasks_taken, task_pieces (wood
pieces placed on tasks), tasks_completed, tasks_incomplete with ``incomplete_slots_filled`` /
``incomplete_slots_total``; joiners_hired, joinery_placed, joinery_sold (covered pieces paid at
the final sale, R-082), joinery_unsold (placed but not covered or game not over).

Wood-flow funnel (``Ledger.wood_flow()``, additive, derived by diffing the zone counts of each
seat around every applied action; the engine is untouched). Per seat and per round (the round
the action was applied in), counted in pieces ("all") and again for hardwood only (``*_hw``):
cut (TAKE_WOOD into the woodpile), move_bearer / move_wagon / move_sledge (MOVE_WOOD by trip
kind), move_raft (RIVER_MOVE / WC_MOVE, counted when the piece leaves the woodpile), arr_saw /
arr_sale (arrival in the sawing / sale area, from the woodpile or the river), sawn (disks
milled), saw_extra (logs beyond one per disk), sold (SELL plus the final sale), dried (entered
drying 1: DRY_ENTER, or HUT_DRY from the sale area), tasks (PLACE_TASK), joinery
(PLACE_JOINERY), heated (firewood storage consumed), other_in (wood added to the woodpile
outside woodcutting: winter bonus and cut, Overtime) and
unexplained (zone changes no action accounts for; 0 when the diff is complete). Gauges, at the
start of each task phase (W5, N4): avail_sale, avail_d1, avail_d2, avail_d3 (pieces held).
Conservation, checked by ``wood_conservation()``: cut + other_in + saw_extra equals the pieces
still in play (``wood_in_play``) + sold + heated + tasks + joinery. Pieces in play at the end
are the "unsold at game end".

Task completion rounds (``Ledger.completion_rounds()``, additive): for each seat the round number
in which each of its tasks was completed (the PLACE_TASK that filled the last slot), in order.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

import lignum.game as engine
from lignum import actions as A
from lignum.components import load_components as _components
from lignum.rules import building_param, has_building
from lignum.woodwork import NO_SLOT, TRIP_NONE, TRIP_PW, TRIP_SLEDGE, TRIP_WAGON

COMPONENTS = (
    "start",
    "wood_sales",
    "joinery",
    "tasks",
    "office",
    "craftwork",
    "winter",
    "loan_proceeds",
    "loan_repayment",
    "joiner_income",
    "spending",
    "other_income",
    "unattributed",
)
# Folded into one "other" column of the text report (start money, spending and small incomes).
OTHER = ("start", "joiner_income", "spending", "other_income", "unattributed")

SPENDING_KEYS = (
    "hire_bearer",
    "hire_woodcutter",
    "hire_sawyer",
    "fodder",
    "saws",
    "planned_work",
    "food",
    "tasks_bought",
    "cut_token",
    "buildings",
    "other",
)
WINTER_KEYS = ("feed_shortfall", "heat_shortfall")
WINTER_INFO_KEYS = (
    "feed_required",
    "feed_from_stock",
    "feed_missing_units",
    "heat_required",
    "heat_from_stock",
    "heat_missing_units",
    "shortfall_price",
    "forgiven_dollars",
    "forced_loans",
    "forced_loan_dollars",
    "forced_sales",
    "forced_sale_dollars",
)
FUNNEL_KEYS = (
    "tasks_taken",
    "task_pieces",
    "tasks_completed",
    "tasks_incomplete",
    "incomplete_slots_filled",
    "incomplete_slots_total",
    "joiners_hired",
    "joinery_placed",
    "joinery_sold",
    "joinery_unsold",
)
_SPEND_BY_ACTION = {
    "HIRE_BEARER": "hire_bearer",
    "HIRE_WOODCUTTER": "hire_woodcutter",
    "HIRE_SAWYER": "hire_sawyer",
    "BUY_FODDER": "fodder",
    "BUY_SAW": "saws",
    "PLAN_WORK": "planned_work",
    "BUY_FOOD": "food",
    "TAKE_TASK": "tasks_bought",
    "MOVE_CUT_TOKEN": "cut_token",
    "CHOOSE_BUILDING": "buildings",
}

_CRAFT_SALES = ("SELL_SET", "SELL_SET_JOKERS")
# Engine functions that take a loan (TAKE_LOAN); a payment chained after a loan is not proceeds.
_LOAN_CALLERS = ("_apply_travel", "_apply_wood", "_apply_overtime", "_apply_final_sale")
_RUN_LOCK = threading.Lock()


WOOD_KEYS = (
    "cut",
    "move_bearer",
    "move_wagon",
    "move_sledge",
    "move_raft",
    "arr_saw",
    "arr_sale",
    "sawn",
    "saw_extra",
    "sold",
    "dried",
    "tasks",
    "joinery",
    "heated",
    "other_in",
    "unexplained",
)
WOOD_GAUGES = ("avail_sale", "avail_d1", "avail_d2", "avail_d3")
_TRIP_MODE = {
    TRIP_NONE: "move_bearer",
    TRIP_WAGON: "move_wagon",
    TRIP_SLEDGE: "move_sledge",
    TRIP_PW: "move_raft",
}
Pair = tuple[int, int]  # (pieces, of which hardwood)
_ZONES = ("woodpile", "river", "sawing", "sale", "logs", "store", "dry", "small")
_CHECKED = ("woodpile", "river", "sawing", "store", "small", "pool")


def _row(row: tuple[int, ...]) -> Pair:
    """Pieces of a (fw, sw, hw) zone or a 6-vector (disks, logs)."""
    return (sum(row), row[2] + (row[5] if len(row) > 3 else 0))


def _wood_snapshot(st: Any, seat: int) -> dict[str, Pair]:
    small = st.small_storage[seat]
    dry = [_row(v) for v in st.dry[seat]]
    return {
        "woodpile": _row(st.woodpile[seat]),
        "river": _row(st.river[seat]),
        "sawing": _row(st.sawing[seat]),
        "sale": _row(st.sale[seat]),
        "logs": _row(st.sale_logs[seat]),
        "store": _row(st.store[seat]),
        "dry": (sum(d[0] for d in dry), sum(d[1] for d in dry)),
        "small": (1 if 0 <= small <= 2 else 0, 1 if small == 2 else 0),
    }


def _pool(z: dict[str, Pair]) -> Pair:
    """Sale area (disks and logs) plus the drying areas: what can be sold, dried or placed."""
    return (
        z["sale"][0] + z["logs"][0] + z["dry"][0],
        z["sale"][1] + z["logs"][1] + z["dry"][1],
    )


def _empty_flow() -> dict[str, int]:
    return {k: 0 for key in WOOD_KEYS for k in (key, key + "_hw")}


_FUNNEL_BY_ACTION = {
    "TAKE_TASK": "tasks_taken",
    "PLACE_TASK": "task_pieces",
    "PLACE_JOINERY": "joinery_placed",
}


class Ledger:
    """Wrap a freshly created state; call ``apply`` instead of ``state.apply_action``.

    Not thread-safe: ``run`` swaps the module-level ``lignum.game._bump`` for its duration, so use
    processes, not threads, for parallel games. Overlapping ``run`` calls raise ``RuntimeError``.
    ``breakdown()`` and ``detail()`` raise if any money change was left unattributed."""

    def __init__(self, state: Any) -> None:
        self.state = state
        self.parts: list[dict[str, int]] = [dict.fromkeys(COMPONENTS, 0) for _ in range(state.n)]
        for seat in range(state.n):
            self.parts[seat]["start"] = state.money[seat]
        self._office_paid: set[int] = set()
        self.spending: list[dict[str, int]] = [
            dict.fromkeys(SPENDING_KEYS, 0) for _ in range(state.n)
        ]
        self.winter: list[dict[str, int]] = [dict.fromkeys(WINTER_KEYS, 0) for _ in range(state.n)]
        self.winter_info: list[dict[str, int]] = [
            dict.fromkeys(WINTER_INFO_KEYS, 0) for _ in range(state.n)
        ]
        self._count: list[dict[str, int]] = [dict.fromkeys(FUNNEL_KEYS, 0) for _ in range(state.n)]
        self._done: list[dict[int, int]] = [{} for _ in range(state.n)]  # task -> round completed
        self._wood: list[dict[int, dict[str, int]]] = [{} for _ in range(state.n)]
        self._gauges: list[dict[int, dict[str, int]]] = [{} for _ in range(state.n)]

    def apply(self, action: int) -> None:
        st = self.state
        name = "" if st.is_chance_node() else A.decode(action).name
        if name:
            counter = _FUNNEL_BY_ACTION.get(name)
            if counter:
                self._count[st.current_player()][counter] += 1
        seat, rnd = (st.current_player(), st.round) if name == "PLACE_TASK" else (-1, 0)
        wood = self._wood_before(action, name)
        self.run(lambda: st.apply_action(action), name)
        self._wood_after(wood)
        if seat >= 0:
            total = _components().tasks
            for held in st.held_tasks[seat]:
                full = st.filled[held] == (1 << len(total[int(held)].requirements)) - 1
                if full and held not in self._done[seat]:
                    self._done[seat][held] = rnd

    def _add(self, seat: int, rnd: int, key: str, n: int, hw: int) -> None:
        if n or hw:
            row = self._wood[seat].setdefault(rnd, _empty_flow())
            row[key] += n
            row[key + "_hw"] += hw

    def _wood_before(self, action: int, name: str) -> tuple[Any, ...]:
        st = self.state
        seat = -1 if st.is_chance_node() else st.current_player()
        decoded = None if not name else A.decode(action)
        small = st.small_storage[seat] if seat >= 0 else NO_SLOT
        return (
            seat,
            st.round,
            st.phase,
            st.trip_kind,
            name,
            decoded.params if decoded else (),
            small,
            [_wood_snapshot(st, s) for s in range(st.n)],
        )

    def _wood_after(self, before: tuple[Any, ...]) -> None:
        """Wood-flow bookkeeping for one applied action (see the module docstring)."""
        st = self.state
        seat, rnd, phase, trip, name, params, small, snaps = before
        # Explicit effect of the action on the acting seat: zone -> (pieces, hardwood) change.
        eff: dict[str, Pair] = {}
        counts: dict[str, Pair] = {}

        def zone(z: str, kind: int, d: int) -> None:
            old = eff.get(z, (0, 0))
            eff[z] = (old[0] + d, old[1] + (d if kind == 2 else 0))

        def count(key: str, kind: int) -> None:
            old = counts.get(key, (0, 0))
            counts[key] = (old[0] + 1, old[1] + (1 if kind == 2 else 0))

        t = st._tables()  # pyright: ignore[reportPrivateUsage]
        if name == "TAKE_WOOD":
            count("cut", params[1])
            zone("woodpile", params[1], 1)
        elif name == "MOVE_WOOD":
            kind, dest = params
            if phase == engine.PHASE_W2:
                zone("river", kind, -1)
            else:
                zone("woodpile", kind, -1)
                if trip in _TRIP_MODE:
                    count(_TRIP_MODE[trip], kind)
                else:  # a trip kind the funnel does not know: surface it, do not guess
                    count("unexplained", kind)
            count("arr_saw" if dest == 0 else "arr_sale", kind)
            zone("sawing" if dest == 0 else "pool", kind, 1)
        elif name == "RIVER_MOVE":
            count("move_raft", params[0])
            zone("woodpile", params[0], -1)
            zone("river", params[0], 1)
        elif name == "WC_MOVE":
            kind, dest = params
            count("move_raft", kind)
            count("arr_saw" if dest == 0 else "arr_sale", kind)
            zone("woodpile", kind, -1)
            zone("sawing" if dest == 0 else "pool", kind, 1)
        elif name == "SAW":
            count("sawn", params[0])
            zone("sawing", params[0], -1)
        elif name == "SELL":
            area, p = params
            count("sold", p // 2)
            zone({4: "sawing", 5: "store"}.get(area, "pool"), p // 2, -1)
        elif name == "DRY_ENTER":
            count("dried", params[0] // 2)
        elif name == "HUT_DRY":  # R-101: one piece one area right; sale area -> drying 1 enters
            if params[0] == 0:
                count("dried", params[1] // 2)
        elif name == "PLACE_TASK":
            kind = t.task_slots[params[0]][2] if params[1] != 2 else small
            count("tasks", kind)
            zone("small" if params[1] == 2 else "pool", kind, -1)
        elif name == "PLACE_JOINERY":
            count("joinery", params[0])
            zone("pool", params[0], -1)
        elif name == "STORE_PIECE":
            zone("pool", params[0], -1)
            zone("small", params[0], 1)
        after = [_wood_snapshot(st, s) for s in range(st.n)]
        for key, (n, hw) in counts.items():
            self._add(seat, rnd, key, n, hw)
        for s in range(st.n):
            b, a = snaps[s], after[s]
            own = s == seat
            e = eff if own else {}
            d = {z: (a[z][0] - b[z][0], a[z][1] - b[z][1]) for z in _ZONES}
            pb, pa = _pool(b), _pool(a)
            d["pool"] = (pa[0] - pb[0], pa[1] - pb[1])
            if name == "SAW" and own:  # disks become logs: the gain is the saw yield
                gain = (d["logs"][0] + d["store"][0], d["logs"][1] + d["store"][1])
                self._add(s, rnd, "saw_extra", gain[0] - 1, gain[1] - (1 if params[0] == 2 else 0))
                e["pool"] = d["pool"]
                e["store"] = d["store"]
            if name in ("DRY_ENTER", "HUT_DRY") and own:
                e["pool"] = (0, 0)
            res = {
                z: (d[z][0] - e.get(z, (0, 0))[0], d[z][1] - e.get(z, (0, 0))[1]) for z in _CHECKED
            }
            # Residuals, each allowed only where the rules produce it (anything else stays
            # unexplained): pool/river losses are the final sale (R-081); the store emptying is
            # winter heating (R-072); a woodpile gain is wood added outside woodcutting.
            final_sale = name == "RIVER_SALE" or (
                st.phase in (engine.PHASE_FS, engine.PHASE_END) and phase != st.phase
            )
            allowed: list[tuple[str, str]] = []
            if final_sale:
                allowed += [("pool", "sold"), ("river", "sold")]
            if phase in (engine.PHASE_N4, engine.PHASE_SF):
                allowed.append(("store", "heated"))
            for z, key in allowed:
                if res[z][0] < 0 or res[z][1] < 0:
                    self._add(s, rnd, key, -res[z][0], -res[z][1])
                    res[z] = (0, 0)
            if name in ("TAKE_BONUS", "WINTER_CUT", "TAKE_OVERTIME") and (
                res["woodpile"][0] > 0 or res["woodpile"][1] > 0
            ):
                self._add(s, rnd, "other_in", res["woodpile"][0], res["woodpile"][1])
                res["woodpile"] = (0, 0)
            odd = [r for r in res.values() if r != (0, 0)]
            if odd:
                self._add(
                    s, rnd, "unexplained", sum(abs(r[0]) for r in odd), sum(abs(r[1]) for r in odd)
                )
        if st.phase in (engine.PHASE_W5, engine.PHASE_N4) and phase != st.phase:
            for s in range(st.n):
                z = after[s]
                dry = [_row(v) for v in st.dry[s]]
                sale = (z["sale"][0] + z["logs"][0], z["sale"][1] + z["logs"][1])
                g = self._gauges[s].setdefault(st.round, {})
                for key, (n, hw) in zip(WOOD_GAUGES, [sale, *dry], strict=True):
                    g[key], g[key + "_hw"] = n, hw

    def wood_in_play(self, seat: int) -> Pair:
        """Pieces (all, hardwood) the seat holds in wood zones: not yet sold, burnt or locked."""
        z = _wood_snapshot(self.state, seat)
        return (sum(v[0] for v in z.values()), sum(v[1] for v in z.values()))

    def wood_conservation(self) -> list[Pair]:
        """Per seat (all, hardwood): pieces that came in minus pieces in play and out; 0 when the
        funnel is consistent."""
        out: list[Pair] = []
        for seat in range(self.state.n):
            tot = {k: 0 for k in WOOD_KEYS}
            tot_hw = dict(tot)
            for row in self._wood[seat].values():
                for k in WOOD_KEYS:
                    tot[k] += row[k]
                    tot_hw[k] += row[k + "_hw"]
            play = self.wood_in_play(seat)
            res: list[int] = []
            for i, t_ in enumerate((tot, tot_hw)):
                came = t_["cut"] + t_["other_in"] + t_["saw_extra"]
                gone = t_["sold"] + t_["heated"] + t_["tasks"] + t_["joinery"]
                res.append(came - play[i] - gone)
            out.append((res[0], res[1]))
        return out

    def wood_flow(self) -> list[dict[str, Any]]:
        """Per seat: ``rounds`` (round -> counter dict, WOOD_KEYS and ``*_hw``), ``gauges``
        (round -> avail_* at the start of that round's task phase) and ``unsold`` /
        ``unsold_hw`` (pieces still in play now; at the terminal state, unsold at game end)."""
        out: list[dict[str, Any]] = []
        for seat in range(self.state.n):
            play = self.wood_in_play(seat)
            out.append(
                {
                    "rounds": {r: dict(v) for r, v in sorted(self._wood[seat].items())},
                    "gauges": {r: dict(v) for r, v in sorted(self._gauges[seat].items())},
                    "unsold": play[0],
                    "unsold_hw": play[1],
                }
            )
        return out

    def run(self, step: Any, name: str = "") -> None:
        """Run ``step()`` (an engine transition of the traced state) under the recorder; ``name``
        is the action name it stands for (e.g. ``TAKE_LOAN``)."""
        if not _RUN_LOCK.acquire(blocking=False):
            raise RuntimeError("Ledger.run overlaps another Ledger.run (the _bump swap is global)")
        try:
            self._run(step, name)
        finally:
            _RUN_LOCK.release()

    def _run(self, step: Any, name: str) -> None:
        st = self.state
        before = st.money
        joiners_before = st.joiners
        recorded = [0] * st.n
        original = engine._bump  # pyright: ignore[reportPrivateUsage]

        def traced(values: tuple[int, ...], index: int, delta: int) -> tuple[int, ...]:
            if values is st.money:
                caller = sys._getframe(1).f_code.co_name  # pyright: ignore[reportPrivateUsage]
                self._detail(caller, name, index, delta)
                for comp, amount in self._classify(caller, name, index, delta):
                    self.parts[index][comp] += amount
                recorded[index] += delta
            return original(values, index, delta)

        engine._bump = traced  # pyright: ignore[reportPrivateUsage]
        try:
            step()
        finally:
            engine._bump = original  # pyright: ignore[reportPrivateUsage]
        for seat in range(st.n):
            self._count[seat]["joiners_hired"] += st.joiners[seat] - joiners_before[seat]
        for seat in range(st.n):
            rest = st.money[seat] - before[seat] - recorded[seat]
            if rest:  # the only direct write to state.money is the R-079 joiner income
                self.parts[seat][
                    "joiner_income" if st.joinery and rest > 0 else "unattributed"
                ] += rest

    def _feed_due(self, seat: int) -> int:
        """Food due this winter (R-071, R-109), the same formula as the engine's."""
        st = self.state
        t = st._tables()  # pyright: ignore[reportPrivateUsage]
        due = st._winter_requirement()[0] + st.joiners[seat] * t.joiner_food  # pyright: ignore[reportPrivateUsage]
        if has_building(t, st.held_buildings, seat, "storeroom"):
            due = max(0, due - building_param(t, "storeroom", "winter_food_reduction"))
        return due

    def _detail(self, caller: str, name: str, seat: int, delta: int) -> None:
        """Sub-component bookkeeping for one engine money change (see the module docstring)."""
        st = self.state
        t = st._tables()  # pyright: ignore[reportPrivateUsage]
        if name == "TAKE_LOAN" and caller in _LOAN_CALLERS and st.phase == engine.PHASE_SF:
            self.winter_info[seat]["forced_loans"] += 1
            self.winter_info[seat]["forced_loan_dollars"] += delta
        elif caller == "_sell" and st.phase == engine.PHASE_SF:
            self.winter_info[seat]["forced_sales"] += 1
            self.winter_info[seat]["forced_sale_dollars"] += delta
        elif caller in ("_settle", "_next_winter_turn"):
            info = self.winter_info[seat]
            feed = st.pay == engine.FEED
            kind = "feed" if feed else "heat"
            required = self._feed_due(seat) if feed else st._winter_requirement()[1]  # pyright: ignore[reportPrivateUsage]
            if caller == "_settle":
                missing = -delta // t.shortfall_unit
            else:  # R-073 step 4: pay what is held, forgive the rest (D9)
                missing = st.sf_due // t.shortfall_unit
                info["forgiven_dollars"] += st.sf_due + delta
            info[f"{kind}_required"] += required
            info[f"{kind}_missing_units"] += missing
            info[f"{kind}_from_stock"] += required - missing
            info["shortfall_price"] = t.shortfall_unit
            self.winter[seat][f"{kind}_shortfall"] += delta
        elif caller == "_acquire" and name not in _CRAFT_SALES + ("SELL_FOOD", "SELL_EQUIP"):
            self.spending[seat][_SPEND_BY_ACTION.get(name, "other")] += delta
        elif caller == "_apply_wood" and name == "MOVE_CUT_TOKEN":
            self.spending[seat]["cut_token"] += delta
        elif caller == "_begin_final_sale":
            sold = sum(
                1
                for slot, kind in enumerate(st.joinery_wood[seat])
                if kind != -1 and slot < st.joiners[seat]
            )
            self._count[seat]["joinery_sold"] += sold

    def _covered_joinery(self, seat: int) -> int:
        """Dollars the engine pays for the seat's joinery pieces under a joiner (R-082): the
        wood's joinery price plus the joinery bonus (the Small Joinery one if held)."""
        st = self.state
        t = st._tables()  # pyright: ignore[reportPrivateUsage]
        bonus = t.joinery_bonus
        if has_building(t, st.held_buildings, seat, "small_joinery"):
            bonus = building_param(t, "small_joinery", "joinery_bonus")
        return sum(
            t.wood_price[kind][1] + bonus
            for slot, kind in enumerate(st.joinery_wood[seat])
            if 0 <= kind < 3 and slot < st.joiners[seat]
        )

    def _classify(self, caller: str, name: str, seat: int, delta: int) -> list[tuple[str, int]]:
        st = self.state
        if name == "TAKE_LOAN" and caller in _LOAN_CALLERS:
            return [("loan_proceeds", delta)]
        if caller in ("_sell", "_sell_river"):
            return [("wood_sales", delta)]
        if caller == "_begin_final_sale":
            # The engine pays sale/drying wood and covered joinery in one bump; split it with
            # the setup tables (covered slots only, still unsold at this point).
            joinery = self._covered_joinery(seat)
            return [("joinery", joinery), ("wood_sales", delta - joinery)]
        if caller == "_advance_final_sale":
            t = st._tables()  # pyright: ignore[reportPrivateUsage]
            if has_building(t, st.held_buildings, seat, "office") and seat not in self._office_paid:
                self._office_paid.add(seat)  # the engine pays the Office bonus first (R-116)
                assert delta == len(st.held_tasks[seat]) * building_param(
                    t, "office", "money_per_task_card"
                )
                return [("office", delta)]
            return [("tasks", delta)]
        if caller in ("_settle", "_next_winter_turn"):
            return [("winter", delta)]
        if caller == "_acquire":
            if name in _CRAFT_SALES:
                return [("craftwork", delta)]
            if name in ("SELL_FOOD", "SELL_EQUIP"):
                return [("other_income", delta)]
            return [("spending", delta)]
        if caller == "_take_token":
            return [("other_income", delta)]
        if caller == "_apply_wood" and name == "MOVE_CUT_TOKEN":
            return [("spending", delta)]
        return [("unattributed", delta)]

    def detail(self) -> list[dict[str, dict[str, int]]]:
        """Per-seat sub-components: ``winter`` and ``spending`` (each sums to its parent
        component) and ``winter_info`` (memo items, not money). Raises if money is unattributed."""
        self._check_attributed()
        return [
            {
                "winter": dict(self.winter[s]),
                "spending": dict(self.spending[s]),
                "winter_info": dict(self.winter_info[s]),
            }
            for s in range(self.state.n)
        ]

    def _check_attributed(self) -> None:
        for seat in range(self.state.n):
            if self.parts[seat]["unattributed"]:
                raise AssertionError(
                    f"ledger seat {seat}: {self.parts[seat]['unattributed']} dollars unattributed"
                )

    def funnels(self) -> list[dict[str, int]]:
        """Per-seat task and joinery funnels (valid mid-game; see the module docstring)."""
        st = self.state
        comps = _components()
        out: list[dict[str, int]] = []
        for seat in range(st.n):
            f = dict(self._count[seat])
            for held in st.held_tasks[seat]:
                total = len(comps.tasks[int(held)].requirements)
                filled = bin(st.filled[held]).count("1")
                if filled == total:
                    f["tasks_completed"] += 1
                else:
                    f["tasks_incomplete"] += 1
                    f["incomplete_slots_filled"] += filled
                    f["incomplete_slots_total"] += total
            f["joinery_unsold"] = f["joinery_placed"] - f["joinery_sold"]
            out.append(f)
        return out

    def completion_rounds(self) -> list[list[int]]:
        """Per seat, the round each completed task was finished in (completion order)."""
        return [sorted(d.values()) for d in self._done]

    def breakdown(self) -> list[dict[str, int]]:
        """Per-seat components of the final dollars; call at the terminal state. The components
        sum to ``state.final[seat]`` exactly and ``unattributed`` must be 0 (both checked; raises
        AssertionError otherwise)."""
        self._check_attributed()
        st = self.state
        t = st._tables()  # pyright: ignore[reportPrivateUsage]
        out: list[dict[str, int]] = []
        for seat in range(st.n):
            parts = dict(self.parts[seat])
            parts["loan_repayment"] = -t.loan_repay[st.loans[seat]]
            if sum(parts.values()) != st.final[seat]:
                raise AssertionError(f"ledger seat {seat}: {parts} != final {st.final[seat]}")
            out.append(parts)
        return out
