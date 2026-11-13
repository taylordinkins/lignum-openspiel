"""Lignum adapter: engine game <-> JSON, with a per-seat filtered view (D14, R-029).

``view(state, seat)`` returns a JSON dict. Everything except ``seat`` and ``private`` is public
and identical for every viewer; the only secret in the game is a seat's hidden cutting-area pick
before the reveal (R-038), which appears solely in the viewer's own ``private``.

Keys (seats are 0-based everywhere):
- ``seat``: the viewer. ``private``: ``{"pick": area | None}`` (viewer's own hidden pick).
- ``game``: ``{"players", "joinery"}``. ``loan_repayment``: repayment by loans held, R-077.
  ``round``, ``phase`` (code), ``phase_label``,
  ``is_terminal``, ``current_player`` (seat, or ``null`` at chance/terminal), ``chance`` (bool),
  ``legal_actions`` (``[{id, label}]`` for ``current_player``; ``[]`` at chance/terminal).
  ``returns``, ``score`` (per-seat components of ``final``, R-081..R-083), ``final`` (final
  dollars per seat: money after the final sale minus loan repayment, R-083) and
  ``winners`` (seats with the most final dollars, R-084) once terminal, else null.
- ``picks``: public cutting-area picks per seat (setup, then revealed round picks).
  ``picked``: seats that have made a hidden pick this round (who, never what).
  ``high_areas``, ``area_wood`` (per area, 3 sizes), ``area_food``.
- ``turn_order``, ``clearing``, ``foreman`` (location per seat).
- ``seats``: list (index = seat) of dicts: ``money``, ``loans``, ``joiners``, ``food``,
  ``hired`` {b, w, s}, ``mill_used`` (the mill worker is away from the worker area),
  ``cut_used`` (hired woodcutters used this round), ``woodpile``,
  ``river``, ``sawing``, ``sale``,
  ``sale_logs``, ``store``, ``dry``, ``joinery_wood``, ``equip``, ``held_craft``, ``held_tasks``.
- ``path``: ``{"boys", "women", "sf", "sp", "fodder", "joiner", "tokens", "locations",
  "clearing_slots"}``; ``tokens`` is a list of ``{spot, location, kind, taken}``, one per token spot
  in order; ``locations`` one ``{number, kind, name, capacity, foremen, pool, token}`` per location
  of the board side in play; ``clearing_slots`` the seat in each of slots A..D (or null).
  ``placement``: ``{discarded, discarded_ids}`` placement cards used so far (R-037).
  Seats also carry ``label`` ("P0"...).
- ``tasks``: ``{"row", "filled", "cards"}`` (``cards``: requirements and reward of every laid-out or
  held task card); ``winter``: ``{"order", "pay", "sf_due" (money due in the open shortfall, R-073),
  "cards" (visible half food/heating per year)}``.
- Phase 4 public items: ``fodder_values``; ``pw`` (laid-out planned-work cards); ``buildings``
  (supply); ``huts`` (built / spent totals, open build); ``craft`` (pile / removed). Per seat:
  ``fodder`` [slot 3, slot 2], ``buildings``, ``building_names``, ``small_storage``
  ``{kind, spent}``, ``huts`` (unspent tokens per area), ``plans`` ``[{card, name, pair, target}]``,
  ``plans_left``.
- ``log``: public log of revealed picks, ``[{"round", "picks"}]`` for the current state only.
  ``picks`` belongs to round 0 (setup) or to the round whose reveal produced it: before the
  current round's reveal (phases up to and including PK) it is labelled ``round - 1``.
  History masking is decided by ``history_mask`` (called by the session layer per rendered seat);
  export is refused by ``export_block`` while a round's picks are partly made.

Labels (``action_meta`` / ``chance_label``) are built from the engine's action decode
(``lignum.actions.decode``) and ``data/components`` names; they never call ``action_to_string``.
``action_meta`` returns ``{"label", "kind" (action family name), "params" (decoded params)}``.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from functools import cache
from typing import Any

import pyspiel

from lignum import actions as A
from lignum.components import Components, load_components
from lignum.game import PHASE_END, PHASE_FS, PHASE_NAMES, PHASE_PK, PHASE_RS
from lignum.huts import SET_SIZE
from lignum.rules import (
    CRAFT_ORDER,
    EQUIP_SLOTS,
    KIND_NAMES,
    SPOT_NAMES,
    building_param,
    has_building,
    plan_param,
)
from lignum.woodwork import NO_SLOT, STORAGE_SPENT, zone_count
from server.adapters import register_adapter
from server.adapters.base import JSON, GameAdapter

# Player-facing phase labels, keyed by the engine phase code (lignum.game.PHASE_NAMES).
# Form: "<code> · <name>". Names use the spec's terms (R-045 wood work, R-064.. winter).
PHASE_LABELS: dict[str, str] = {
    "SC": "SC · Setup",
    "SP": "SP · Setup: cutting-area token placement",
    "TR": "TR · Supply-path travel",
    "END": "END · Game over",
    "RS": "RS · Round start",
    "PK": "PK · Cutting-area picks",
    "W1": "W1 · Woodcutting",
    "W2": "W2 · Log driving, wood arrival",
    "W3": "W3 · Transportation",
    "W4": "W4 · Sawing",
    "W5": "W5 · Tasks",
    "W6": "W6 · Selling",
    "W7": "W7 · Drying",
    "WS": "WS · Winter start",
    "NB": "NB · Winter bonus",
    "N1": "N1 · Winter woodcutting",
    "N2": "N2 · Transportation by sledge",
    "N3": "N3 · Winter sawing",
    "N4": "N4 · Winter tasks",
    "N5": "N5 · Feeding",
    "N6": "N6 · Heating",
    "SF": "SF · Shortfall payment",
    "FS": "FS · Final sale",
}


@cache
def _comp() -> Components:
    return load_components()


_ZONES = ("sale area", "drying 1", "drying 2", "drying 3", "sawing area", "firewood storage")
_DESTS = ("sawing area", "sale area")
_EQUIP = ("raft", "sledge", "wagon")
_HUT_AREAS = ("drying", "food", "worker")
# Worker noun by phase code: the type a hired worker (ASSIGN_WORKER(0)) has in that phase, and the
# type the mill worker (w=1) or a hut worker (w=2) stands in for (ACTIONS 5.2).
_WORKER_NOUN = {
    "W1": "woodcutter",
    "N1": "woodcutter",
    "W3": "bearer",
    "N2": "bearer",
    "W4": "sawyer",
    "N3": "sawyer",
}


def _hut_tokens(st: pyspiel.State, v: int) -> int:
    """Token count of BUILD_HUT(v): 0 = normal build, 1 = PW Hut Construction (R-100, R-095)."""
    s: Any = st
    if v == 0:
        return SET_SIZE
    return int(plan_param(s._tables(), "pw_hut_construction", "tokens_needed"))


def _assign_worker(st: pyspiel.State, p: tuple[int, ...]) -> str:
    s: Any = st
    noun = _WORKER_NOUN.get(str(PHASE_NAMES[int(s.phase)]))
    if p[0] == 0:
        return f"Assign a hired {noun}" if noun else "Assign a hired worker"
    who = "the mill worker" if p[0] == 1 else "a hut worker"
    return f"Assign {who} (as {noun})" if noun else f"Assign {who}"


_PIECES = tuple(f"{k} {m}" for k in KIND_NAMES for m in ("log", "milled"))
_SPOT_LABELS = (
    "wagon",
    "raft",
    "saw",
    "sledge",
    "$1",
    "food",
    "X marker",
    "board",
    "shingle",
    "stake",
    "reed",
    "joker",
)


def _human(ident: str) -> str:
    return ident.replace("_", " ")


def _task_name(index: int) -> str:
    """Card id as used in 'Take task NN' labels (task_row and held_tasks hold indices)."""
    return _human(_comp().tasks[index].id)


def _req_text(kind: str, milled: bool, drying: int) -> str:
    dried = f", dried {drying}" if drying else ""
    return f"{kind} {'milled' if milled else 'log'}{dried}"


def _placement_name(index: int) -> str:
    return _human(str(_comp().placement[index].id))


def _bld_name(index: int) -> str:
    return str(_comp().buildings[index].name)


def _pw_name(index: int) -> str:
    return str(_comp().planned_work[index].name)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _location(state: Any, number: int) -> str:
    if number == 23:
        return "the forest clearing"
    side = _comp().path.sides["joinery" if state.joinery else "base"]
    for loc in side:
        if loc.number == number:
            n = loc.name
            return n if n.lower().startswith("token spot") else f"{n} (location {number})"
    return f"location {number}"


def _task_slot(state: Any, s: int) -> str:
    slot: tuple[int, int, int, int, int] = state._tables().task_slots[s]
    ti, ri, kind, milled, drying = slot
    task_id: str = _comp().tasks[ti].id
    what = f"{KIND_NAMES[kind]} {'milled' if milled else 'log'}"
    return (
        f"{what} (dried {drying}) on {_human(task_id)} (${_comp().tasks[ti].reward}) slot {ri + 1}"
    )


def _saw(p: tuple[int, ...]) -> str:
    k, n = p
    return f"Saw a {KIND_NAMES[k]} log, {n} milled to firewood storage"


def _sell_set(p: tuple[int, ...]) -> str:
    x, s, j = p
    jokers = f" with {_plural(j, 'joker')}" if j else ""
    return f"Sell a set of {s} {CRAFT_ORDER[x]} craftwork{jokers}"


_ACTION_FMT: dict[str, Callable[[Any, tuple[int, ...]], str]] = {
    "DONE": lambda st, p: "Done",
    "TAKE_LOAN": lambda st, p: "Take a loan",
    "PICK_AREA": lambda st, p: f"Pick cutting area {p[0] + 1}",
    "MOVE_TO": lambda st, p: f"Move to {_location(st, p[0])}",
    "HIRE_BEARER": lambda st, p: "Hire a bearer",
    "HIRE_WOODCUTTER": lambda st, p: "Hire a woodcutter",
    "HIRE_SAWYER": lambda st, p: "Hire a sawyer",
    "BUY_FODDER": lambda st, p: "Buy fodder",
    "BUY_SAW": lambda st, p: "Buy a saw",
    "BUY_FOOD": lambda st, p: "Buy food",
    "SELL_FOOD": lambda st, p: "Sell food",
    "TAKE_TASK": lambda st, p: f"Take {_task_name(p[0])}",
    "CHOOSE_BUILDING": lambda st, p: f"Take building: {_comp().buildings[p[0]].name}",
    "PLAN_WORK": lambda st, p: f"Plan {_comp().planned_work[p[0]].name} for pair {p[1] + 1}",
    "SELL_SET": lambda st, p: _sell_set(p),
    "SELL_SET_JOKERS": lambda st, p: "Sell a set of 2 jokers",
    "SELL_EQUIP": lambda st, p: f"Sell a {_EQUIP[p[0]]}",
    "TAKE_OVERTIME": lambda st, p: "Take overtime hardwood log",
    "BUILD_HUT": lambda st, p: f"Build a hut ({_hut_tokens(st, p[0])} tokens)",
    "HUT_TOKEN": lambda st, p: f"Hut: use {CRAFT_ORDER[p[0]]} token",
    "HUT_AREA": lambda st, p: f"Hut: assign token to {_HUT_AREAS[p[0]]} area",
    "HUT_FOOD": lambda st, p: f"Hut: take food of cutting area {p[0] + 1}",
    "HUT_DRY": lambda st, p: f"Hut: move {_PIECES[p[1]]} from {_ZONES[p[0]]} one area right",
    "MOVE_CUT_TOKEN": lambda st, p: f"Pay $1 and move cutting token to area {p[0] + 1}",
    "ASSIGN_WORKER": _assign_worker,
    "TAKE_WOOD": lambda st, p: f"Take {KIND_NAMES[p[1]]} from cutting area {p[0] + 1}",
    "MOVE_WOOD": lambda st, p: f"Move {KIND_NAMES[p[0]]} log to the {_DESTS[p[1]]}",
    "RIVER_MOVE": lambda st, p: f"Place {KIND_NAMES[p[0]]} log on the river",
    "WC_MOVE": lambda st, p: f"Waterchannel: {KIND_NAMES[p[0]]} log to the {_DESTS[p[1]]} at once",
    "USE_WAGON": lambda st, p: "Use a wagon",
    "USE_SLEDGE": lambda st, p: "Use a sledge",
    "USE_PW_LOGDRIVING": lambda st, p: "Use Log Driving",
    "END_TRIP": lambda st, p: "End trip",
    "SAW": lambda st, p: _saw(p),
    "WINTER_CUT": lambda st, p: "Cut winter firewood",
    "TAKE_BONUS": lambda st, p: f"Take a {KIND_NAMES[p[0]]} log (winter bonus)",
    "PLACE_TASK": lambda st, p: (
        f"Place {_task_slot(st, p[0])} from "
        f"{('required area', 'drying 1', 'Small Storage Area')[p[1]]}"
    ),
    "PLACE_JOINERY": lambda st, p: f"Place {KIND_NAMES[p[0]]} milled in joinery slot {p[1] + 1}",
    "STORE_PIECE": lambda st, p: f"Store {KIND_NAMES[p[0]]} milled from {_ZONES[p[1]]}",
    "SELL": lambda st, p: f"Sell {_PIECES[p[1]]} from {_ZONES[p[0]]}",
    "DRY_ENTER": lambda st, p: f"Move {_PIECES[p[0]]} to drying 1",
    "RIVER_SALE": lambda st, p: f"Sell river {KIND_NAMES[p[0]]}",
}


def _areas3(st: Any, p: tuple[int, ...]) -> str:
    combos: list[tuple[int, ...]] = list(itertools.combinations(range(6), int(st.n)))
    areas = combos[p[0]]
    return "Areas " + ", ".join(str(a + 1) for a in areas) + " start with 3 firewood"


def _winter(st: Any, p: tuple[int, ...]) -> str:
    year = len(st.draws.winter) + 1
    card = [w for w in _comp().winter if w.year == year][p[0]]
    return f"Winter year {year}: {_human(card.id)}, {('top', 'bottom')[p[1]]} half"


def _src(st: Any) -> Any:
    return st.rd if st.rd is not None else st.draws


def _spot_token(st: Any, p: tuple[int, ...]) -> str:
    spots = st._tables().token_spots
    i = len(_src(st).spots)
    where = f"spot {spots[i]}" if i < len(spots) else "a spot"
    return f"Path {where}: {_SPOT_LABELS[p[0]]}"


_CHANCE_FMT: dict[str, Callable[[Any, tuple[int, ...]], str]] = {
    "AREAS3": _areas3,
    "WINTER": _winter,
    "TASK_DRAW": lambda st, p: f"Task card drawn: {_human(_comp().tasks[p[0]].id)}",
    "PW_DRAW": lambda st, p: f"Planned work drawn: {_comp().planned_work[p[0]].name}",
    "PLACEMENT_DRAW": lambda st, p: f"Placement card drawn: {_human(_comp().placement[p[0]].id)}",
    "BUILDING_DRAW": lambda st, p: f"Building drawn: {_comp().buildings[p[0]].name}",
    "CRAFT_DRAW": lambda st, p: (
        f"Craftwork token drawn: {CRAFT_ORDER[p[0]]} ({len(_src(st).craft) + 1} of 3)"
    ),
    "SPOT_TOKEN": _spot_token,
}
assert len(_SPOT_LABELS) == len(SPOT_NAMES)


def _ints(x: Any) -> list[Any]:
    return [list(v) if isinstance(v, (tuple, list)) else v for v in x]  # pyright: ignore


class LignumAdapter(GameAdapter):
    name = "lignum"

    def load(self, params: dict[str, Any]) -> pyspiel.Game:
        parts: list[str] = []
        if params.get("num_players") is not None:
            parts.append(f"players={int(params['num_players'])}")
        if params.get("joinery") is not None:
            parts.append(f"joinery={str(bool(params['joinery'])).lower()}")
        if params.get("returns") is not None:
            parts.append(f"returns={params['returns']}")
        if not parts:
            return pyspiel.load_game("python_lignum")
        return pyspiel.load_game(f"python_lignum({','.join(parts)})")

    def view(self, state: pyspiel.State, seat: int) -> JSON:
        s: Any = state
        # Own hidden pick only (R-029): same rule as LignumObserver._visible_picks.
        own = [s.pk[seat]] if seat < len(s.pk) else []
        n = s.n
        seats = [
            {
                "label": f"P{i}",
                "money": s.money[i],
                "loans": s.loans[i],
                "joiners": s.joiners[i],
                "food": s.food[i],
                "hired": {"b": s.hired_b[i], "w": s.hired_w[i], "s": s.hired_s[i]},
                "mill_used": bool(s.mill_used[i]),
                "cut_used": s.cut_used[i],
                "woodpile": list(s.woodpile[i]),
                "river": list(s.river[i]),
                "sawing": list(s.sawing[i]),
                "sale": list(s.sale[i]),
                "sale_logs": list(s.sale_logs[i]),
                "store": list(s.store[i]),
                "dry": _ints(s.dry[i]),
                "joinery_wood": list(s.joinery_wood[i]),
                "equip": list(s.equip[i]),
                "held_craft": list(s.held_craft[i]),
                "held_tasks": list(s.held_tasks[i]),
                "held_task_ids": [_task_name(k) for k in s.held_tasks[i]],
                "fodder": [s.fodder3[i], s.fodder2[i]],
                "buildings": list(s.held_buildings[i]),
                "building_names": [_bld_name(b) for b in s.held_buildings[i]],
                "small_storage": self._storage(s.small_storage[i]),
                "huts": dict(zip(_HUT_AREAS, s.huts[i], strict=True)),
                "plans": self._plans(s, i),
                "plans_left": s._tables().pw_pairs - sum(1 for q in s.plans if q[0] == i),
            }
            for i in range(n)
        ]
        live = not s.is_terminal() and not s.is_chance_node()
        legal = (
            [{"id": a, **self.action_meta(state, a)} for a in state.legal_actions()] if live else []
        )
        final: list[int] = list(s.final) if s.is_terminal() else []
        winners = [i for i, d in enumerate(final) if d == max(final)] if final else None
        # Picks of round r are revealed at the end of PK, before travel; round 1 has setup picks.
        revealed = s.phase not in (PHASE_RS, PHASE_PK)
        picks_round = 0 if s.round == 1 else (s.round if revealed else s.round - 1)
        while picks_round in s._tables().winter_rounds:  # winter rounds have no picks of their own
            picks_round -= 1
        return {
            "seat": seat,
            "equip_slots": list(EQUIP_SLOTS),
            "kind_names": list(KIND_NAMES),
            "craft_order": list(CRAFT_ORDER),
            "private": {"pick": own[0] if own else None},
            "game": {"players": n, "joinery": bool(s.joinery)},
            "loan_repayment": list(s._tables().loan_repay),
            "round": s.round,
            "phase": PHASE_NAMES[s.phase],
            "phase_label": PHASE_LABELS[PHASE_NAMES[s.phase]],
            "is_terminal": s.is_terminal(),
            "legal_actions": legal,
            "returns": list(state.returns()) if final else None,
            "final": final or None,
            "winners": winners,
            "score": self._score(state) if final else None,
            "chance": s.is_chance_node(),
            "current_player": s.current_player() if live else None,
            "picks": list(s.picks),
            "picked": list(range(len(s.pk))),
            "high_areas": list(s.high_areas()),
            "area_wood": _ints(s.wood),
            "area_food": list(s.area_food),
            "turn_order": list(s.turn_order),
            "clearing": list(s.clearing),
            "foreman": list(s.foreman),
            "seats": seats,
            "path": {
                "boys": s.path_b,
                "women": s.path_w,
                "sf": s.path_sf,
                "sp": s.path_sp,
                "fodder": s.path_fodder,
                "joiner": s.path_joiner,
                "tokens": self._path_tokens(s),
                "locations": self._path_locations(s),
                "clearing_slots": self._clearing_slots(s),
            },
            "placement": {
                "discarded": list(s.placement_discarded),
                "discarded_ids": [_placement_name(k) for k in s.placement_discarded],
            },
            "fodder_values": list(_comp().setup.sawmill.fodder_slot_values),
            "pw": {
                "row": list(s.draws.pw),
                "names": [_pw_name(k) for k in s.draws.pw],
                "cards": [
                    {
                        "index": k,
                        "name": _pw_name(k),
                        "seasons": list(_comp().planned_work[int(k)].seasons),
                    }
                    for k in s.draws.pw
                ],
            },
            "buildings": {
                "supply": list(s.bld_supply),
                "names": [_bld_name(b) for b in s.bld_supply],
            },
            "huts": {
                "built": s.hut_built,
                "spent": s.hut_spent,
                "open": self._hut_build(s),
            },
            "craft": {"pile": list(s.craft_pile), "removed": list(s.craft_removed)},
            "tasks": {
                "cards": self._task_cards(s),
                "row": list(s.task_row),
                "row_ids": [_task_name(k) for k in s.task_row],
                "filled": list(s.filled),
                "filled_ids": [_task_name(k) for k, f in enumerate(s.filled) if f],
            },
            "winter": {
                "order": list(s.wint),
                "pay": s.pay,
                "sf_due": s.sf_due,
                "cards": self._winter_cards(s),
                "card_ids": [f"winter-{y + 1}-{w // 2 + 1}" for y, w in enumerate(s.draws.winter)],
            },
            "log": [{"round": picks_round, "picks": list(s.picks)}],
        }

    @staticmethod
    def _score(state: Any) -> list[JSON] | None:
        """Per-seat final-dollar components of a terminal state (R-081..R-083).

        Read-only: the state just before the final sale is rebuilt by replaying the history, the
        sale parts are recomputed from it with the engine's own tables, and ``money`` is the
        remainder, so the parts always sum to the engine's ``final``.
        """
        s: Any = state
        hist = list(s.history())
        game = s.get_game()
        replay = game.new_initial_state()
        pre: Any = None
        for a in hist:
            before = replay.clone()
            replay.apply_action(a)
            if replay.phase in (PHASE_FS, PHASE_END):
                pre = before
                break
        if pre is None:  # no final-sale transition found: no breakdown rather than a wrong one
            return None
        pre_s: Any = pre
        t = s._tables()
        comp = _comp()
        out: list[JSON] = []
        for seat in range(s.n):
            areas = 0
            for p in range(6):
                price = t.wood_price[p // 2][p % 2]
                if price < 0:
                    continue
                for zone in range(4):
                    areas += zone_count(pre_s, seat, zone, p) * (price + t.dry_bonus[zone])
            bonus = t.joinery_bonus
            if has_building(t, pre_s.held_buildings, seat, "small_joinery"):
                bonus = building_param(t, "small_joinery", "joinery_bonus")
            joinery = sum(
                t.wood_price[kind][1] + bonus
                for slot, kind in enumerate(pre_s.joinery_wood[seat])
                if kind != NO_SLOT and slot < pre_s.joiners[seat]
            )
            river = sum(
                (pre_s.river[seat][k] - s.river[seat][k]) * t.wood_price[k][0] for k in (0, 1)
            )
            office = 0
            if has_building(t, s.held_buildings, seat, "office"):
                office = len(s.held_tasks[seat]) * building_param(
                    t, "office", "money_per_task_card"
                )
            tasks: int = 0
            done: list[str] = []
            for held in _ints(s.held_tasks[seat]):
                task = comp.tasks[int(held)]
                if s.filled[held] == (1 << len(task.requirements)) - 1:
                    tasks += int(task.reward)
                    done.append(_task_name(int(held)))
            repay = t.loan_repay[s.loans[seat]]
            money: int = s.final[seat] + repay - areas - joinery - river - office - tasks
            out.append(
                {
                    "money": money,
                    "wood_sale": areas,
                    "river_sale": river,
                    "joinery_sale": joinery,
                    "office": office,
                    "tasks": tasks,
                    "tasks_done": done,
                    "loans": s.loans[seat],
                    "loan_repay": -repay,
                    "final": s.final[seat],
                }
            )
        return out

    @staticmethod
    def _storage(v: int) -> JSON:
        """R-114: Small Storage Area content (public): None if the seat has no piece in it."""
        if v == STORAGE_SPENT:
            return {"kind": None, "spent": True}
        if v == NO_SLOT:
            return {"kind": None, "spent": False}
        return {"kind": KIND_NAMES[v], "spent": False}

    @staticmethod
    def _plans(s: Any, seat: int) -> list[JSON]:
        """R-087: a seat's planned-work placements (public), in the order made."""
        return [
            {"card": c, "name": _pw_name(c), "pair": pair, "target": target}
            for q, c, pair, target in s.plans
            if q == seat
        ]

    @staticmethod
    def _hut_build(s: Any) -> JSON | None:
        """The hut build in progress (R-100), public; None when none is open."""
        if not s.hb_open:
            return None
        return {
            "tokens": [CRAFT_ORDER[x] for x in s.hb_tok],
            "areas": [_HUT_AREAS[h] for h in s.hb_area],
        }

    @staticmethod
    def _task_cards(s: Any) -> list[JSON]:
        """R-028: requirements and reward of every task card laid out or held (public)."""
        shown: list[int] = sorted({*s.task_row, *(k for h in s.held_tasks for k in h)})
        return [
            {
                "index": k,
                "id": _task_name(k),
                "reward": _comp().tasks[k].reward,
                "requirements": [
                    {
                        "kind": r.kind,
                        "milled": r.milled,
                        "drying": r.drying,
                        "text": _req_text(r.kind, r.milled, r.drying),
                        "filled": bool(s.filled[k] >> ri & 1),
                    }
                    for ri, r in enumerate(_comp().tasks[k].requirements)
                ],
            }
            for k in shown
        ]

    @staticmethod
    def _path_locations(s: Any) -> list[JSON]:
        """R-028, R-040: every location of the board side in play, in printed order: its kind,
        capacity, the foremen standing there (seats, in seat order), the pieces on offer (``pool``:
        count of bearers / woodcutters / fodder / joiner; sawyers ``{free, paid}``; else null)
        and, for a token spot, the token lying there."""
        side = _comp().path.sides["joinery" if s.joinery else "base"]
        spots = list(s._tables().token_spots)
        pools: dict[str, Any] = {
            "bearers": s.path_b,
            "woodcutters": s.path_w,
            "fodder": s.path_fodder,
            "joiner": s.path_joiner,
            "sawyers": {"free": s.path_sf, "paid": s.path_sp},
        }
        out: list[JSON] = []
        for loc in side:
            token: JSON | None = None
            if loc.number in spots and len(s.path_tokens) == len(spots):
                i = spots.index(loc.number)
                y = s.path_tokens[i]
                token = {"spot": i + 1, "kind": None if y < 0 else _SPOT_LABELS[y], "taken": y < 0}
            out.append(
                {
                    "number": loc.number,
                    "kind": loc.kind,
                    "name": loc.name,
                    "capacity": loc.capacity,
                    "foremen": [q for q in range(s.n) if s.foreman[q] == loc.number],
                    "pool": pools.get(loc.kind),
                    "token": token,
                }
            )
        return out

    @staticmethod
    def _clearing_slots(s: Any) -> list[int | None]:
        """R-024: the four clearing slots A..D: the seat standing in each, or null."""
        slots = _comp().path.forest_clearing.slots
        return [s.clearing[i] if i < len(s.clearing) else None for i in range(len(slots))]

    @staticmethod
    def _path_tokens(s: Any) -> list[JSON]:
        """R-017, R-024: one entry per token spot in spot order; all public, shown face up."""
        spots = s._tables().token_spots
        return [
            {
                "spot": i + 1,
                "location": spots[i],
                "kind": None if y < 0 else _SPOT_LABELS[y],
                "taken": y < 0,
            }
            for i, y in enumerate(s.path_tokens)
        ]

    @staticmethod
    def _winter_cards(s: Any) -> list[JSON]:
        """R-028: the visible winter half of each drawn winter card (public setup draws)."""
        t = s._tables()
        out: list[JSON] = []
        for year, w in enumerate(s.draws.winter):
            food, heating = t.winter_req[year][w // 2][w % 2]
            out.append({"year": year + 1, "food": food, "heating": heating})
        return out

    def action_meta(self, state: pyspiel.State, action_id: int) -> JSON:
        # Label of a decision for the acting seat. Callers must not use this for another seat's
        # unrevealed pick: the session layer asks history_mask first.
        a = A.decode(action_id)
        label = _ACTION_FMT[a.name](state, a.params)
        return {"label": label, "kind": a.name, "params": list(a.params)}

    def chance_label(self, state: pyspiel.State, action_id: int) -> str:
        a = A.decode_chance(action_id)
        return _CHANCE_FMT[a.name](state, a.params)

    def history_mask(
        self,
        state_before: pyspiel.State,
        actor: int,
        action_id: int,
        state_now: pyspiel.State,
        viewer: int,
    ) -> str | None:
        """R-038: another seat's pick is hidden until the round's picks are all made."""
        b: Any = state_before
        n: Any = state_now
        if b.phase == PHASE_PK and n.phase == PHASE_PK and n.round == b.round and actor != viewer:
            return f"P{actor} picked an area"
        return None

    def pick_revealed(
        self, state_before: pyspiel.State, actor: int, action_id: int, state_now: pyspiel.State
    ) -> bool:
        """R-038: a pick made in PK is revealed once the round's picks are all made."""
        b: Any = state_before
        n: Any = state_now
        return b.phase == PHASE_PK and not (n.phase == PHASE_PK and n.round == b.round)

    def chance_blocks_back(self, state_before: pyspiel.State, action_id: int) -> bool:
        """Every chance draw after a human decision is a round-start draw (tasks, craftwork,
        spot tokens, placement cards); Back must not cross it (chance key = seed, salt, history
        length, so the same draws would reappear)."""
        return True

    def export_block(self, state: pyspiel.State) -> str | None:
        s: Any = state
        if s.phase == PHASE_PK and len(s.pk) > 0:
            return "picks are unrevealed; export after the reveal"
        return None


register_adapter("lignum", LignumAdapter)
