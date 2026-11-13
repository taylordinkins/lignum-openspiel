"""Winter / loan / shortfall helpers for unit-10 tests (R-064..R-077), spec-only.

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and the existing support modules. No scenario
loader exists in the harness, so every winter state is reached by scripted play through rounds 1-3
(`fall_steps`), exactly as in tests/support/sawmill.py.

Contents
  * `fall_steps`    : round-1 script for seat 0 (tokens, hires, sawing, carrying, drying, loans).
  * `reach`         : state at the first turn-boundary node (round, phase, seat) with a policy.
  * `requirement`   : (food, heating) of the visible winter-card half in a snapshot (data driven).
  * `settle`        : an independent reference model of winter feeding + heating + shortfall for
                      one seat (R-071..R-073), used for end-to-end comparisons. It follows the
                      deterministic test policy "TAKE_LOAN while it is the only way; sell the
                      lowest legal SELL id until DONE is legal" (what `rounds.default_action` does).
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from typing import Any, cast

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as M
from tests.support import woodwork as W

SEED = 1  # 2 players: year-1 card winter_1_4 top (food 5, heating 4), year-2 card winter_2_4 top
LOAN = 4
SHORTFALL = 3
TAKE_BONUS0 = 228
WINTER_CUT = 227
USE_SLEDGE = 211
END_TRIP = 213
PLACE_ALL = range(231, 384)
PIECES = (
    "firewood_disk",
    "firewood_log",
    "softwood_disk",
    "softwood_log",
    "hardwood_disk",
    "hardwood_log",
)
KINDS = ("firewood", "softwood", "hardwood")


def params(n: int = 2, j: bool = False) -> dict[str, Any]:
    return {"players": n, "joinery": j}


def winter_cards() -> dict[str, dict[str, Any]]:
    cards = cast("list[dict[str, Any]]", R._yaml("cards.yaml")["winter"])  # pyright: ignore[reportPrivateUsage]
    return {c["id"]: c for c in cards}


def requirement(sn: dict[str, Any], year: int) -> tuple[int, int]:
    """(food, heating) of the visible half of the year's winter card in the snapshot."""
    w = sn["supply"]["winter"][f"year{year}"]
    half = winter_cards()[w["card"]]["halves"][w["half"]]
    return int(half["food"]), int(half["heating"])


# --------------------------------------------------------------------------- scripts


def fall_steps(
    j: bool,
    *,
    n: int = 2,
    seed: int = SEED,
    loans: int = 0,
    food_tokens: int = 0,
    saw: bool = False,
    sledge: bool = False,
    bearers: int = 0,
    sawyer: bool = False,
    task: str | None = None,
    joiner: bool = False,
    carries: tuple[int, ...] = (),
    sawing: tuple[tuple[int, int, int], ...] = (),
    dry_round2: int = 0,
    dry_round1: int = 0,
    steps: W.Steps | None = None,
) -> W.Steps:
    """Round-1 script for seat 0, then optional drying entries of logs in the sale area.

    carries: destinations (0 sawing, 1 sale) of firewood disks carried in W3.
    sawing : (source, kind, logs to storage) per sawing action in W4 (kind 0 firewood).
    dry_roundN: that many firewood logs move from the sale area to drying 1 in round N's W7.
    The mill worker's single woodcut in W1 is left to `rounds.cut_all_wood` (use `policy`)."""
    st = steps or W.Steps()
    visits: list[tuple[int, list[Any]]] = []
    if saw:
        visits.append((W.spot_loc(n, j, seed, "saw", 0), []))
    if sledge:
        visits.append((W.spot_loc(n, j, seed, "sledge", 0), []))
    for i in range(food_tokens):
        visits.append((W.spot_loc(n, j, seed, "food", i), []))
    if bearers:
        visits.append((R.loc(j, "bearers"), [R.HIRE_BEARER] * bearers + [H.DONE]))
    if sawyer:
        visits.append((R.loc(j, "sawyers"), [R.HIRE_SAWYER, H.DONE]))
    if joiner:
        visits.append((R.loc(True, "joiner"), []))
    if task:
        visits.append((R.loc(j, "tasks"), [M.take_task(task)]))
    visits.sort(key=lambda v: v[0])
    plan: list[Any] = [H.TAKE_LOAN] * loans
    for loc, acts in visits:
        plan += [H.MOVE_TO(loc), *acts]
    plan.append(R.MOVE_CLEARING)
    st.add(1, "TR", 0, *plan)
    for dest in carries:
        st.add(1, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, dest))
    for src, k, nlogs in sawing:
        st.add(1, "W4", 0, W.Opt(W.assign(src)), M.saw(k, nlogs))
    for rnd, cnt in ((1, dry_round1), (2, dry_round2)):
        for _ in range(cnt):
            st.add(rnd, "W7", 0, M.dry_enter(M.FW_LOG))
    return st


def policy(steps: W.Steps | None = None) -> Callable[[R.Ctx], int | None]:
    # Steps pop their entries as they play: every drive gets a fresh copy of the script
    return R.chain(copy.deepcopy(steps), R.cut_all_wood) if steps else R.cut_all_wood


def reach(
    steps: W.Steps | None,
    stop: tuple[int, str, int],
    *,
    j: bool = False,
    n: int = 2,
    seed: int = SEED,
    extra: Callable[[R.Ctx], int | None] | None = None,
) -> Any:
    pol = policy(steps)
    if extra:
        pol = R.chain(extra, pol)
    run = R.drive(
        params(n, j),
        seed=seed,
        policy=pol,
        stop=lambda c: (c.round, c.phase, c.player) == stop,
    )
    assert run.stopped, f"never reached {stop}"
    return run.state


def last_fall_seat_run(
    steps: W.Steps | None, *, j: bool = False, n: int = 2, seed: int = SEED, stop_round: int = 5
) -> R.Run:
    return R.drive(
        params(n, j),
        seed=seed,
        policy=policy(steps),
        stop=lambda c: c.round == stop_round,
    )


def winter_run(steps: W.Steps | None = None, **kw: Any) -> R.Run:
    """Play to the first turn-boundary node of round 5 (the winter has been fully played)."""
    run = last_fall_seat_run(steps, **kw)
    assert run.stopped, "round 5 never started"
    run.event(4)  # round 4 must have been played (raises otherwise)
    return run


def winter_order(run: R.Run) -> list[int]:
    """Fall clearing order, read from the round-4 first node (R-064)."""
    order = run.event(4).after["clearing_order"]
    assert order is not None
    return list(order)


def seat(sn: dict[str, Any], i: int) -> dict[str, Any]:
    return cast("dict[str, Any]", H.seats(sn)[i])  # pyright: ignore[reportUnknownMemberType]


def pm(x: Any) -> Counter[str]:
    return W.pm(x)


# --------------------------------------------------------------------------- reference model


def _prices() -> tuple[dict[str, Any], dict[str, int]]:
    d = R.setup_data()
    return d["wood_prices"], d["drying_bonuses"]


def piece_price(zone: int, piece: str) -> int | None:
    """R-058 price of a piece in a SELL zone (0 sale, 1..3 drying, 4 sawing, 5 storage)."""
    prices, bonus = _prices()
    kind, state = piece.split("_")
    base = prices[kind]["milled" if state == "log" else "unmilled"]
    if base is None:
        return None
    extra = {
        0: bonus["sale_area"],
        1: bonus["drying_1"],
        2: bonus["drying_2"],
        3: bonus["drying_3"],
    }
    return int(base) + extra.get(zone, 0)


def zones_of(s: dict[str, Any]) -> list[Counter[str]]:
    dry = [pm(x) for x in s["drying"]]
    return [pm(s["sale"]), *dry, pm(s["sawing"]), pm(s["firewood_storage"])]


def sell_ids(zs: list[Counter[str]]) -> list[tuple[int, str]]:
    """Legal (zone, piece) sales in the winter shortfall (R-073 order rule)."""
    out: list[tuple[int, str]] = []
    for z in range(6):
        for name in PIECES:
            if zs[z][name] > 0 and piece_price(z, name) is not None:
                out.append((z, name))
    first = [t for t in out if t[0] <= 3]
    return first if first else out


def _pay(s: dict[str, Any], zs: list[Counter[str]], due: int) -> None:
    while s["money"] < due and s["loans"] < 2:
        s["money"] += LOAN
        s["loans"] += 1
    while s["money"] < due:
        opts = sell_ids(zs)
        if not opts:
            break
        z, name = min(opts, key=lambda t: (t[0], PIECES.index(t[1])))
        zs[z][name] -= 1
        s["money"] += cast("int", piece_price(z, name))
    s["money"] -= min(s["money"], due)


def settle(s: dict[str, Any], req: tuple[int, int], joiners: int = 0) -> dict[str, Any]:
    """Reference model of one seat's winter feeding then heating (R-071, R-072, R-073).

    `s` is a seat dict from a snapshot taken before feeding; the result has money, loans, food,
    and the six sellable/stored zones (`zones`: sale, drying1-3, sawing, storage)."""
    r: dict[str, Any] = {"money": s["money"], "loans": s["loans"]}
    zs = zones_of(s)
    food_due = req[0] + joiners
    missing = max(0, food_due - s["food"])
    r["food"] = 0
    _pay(r, zs, SHORTFALL * missing)
    stor = zs[5]
    left = req[1]
    for kind in KINDS:
        name = f"{kind}_log"
        take = min(left, stor[name])
        stor[name] -= take
        left -= take
    _pay(r, zs, SHORTFALL * left)
    r["zones"] = [+z for z in zs]
    return r


def zones_equal(s: dict[str, Any], want: list[Counter[str]]) -> bool:
    return [+z for z in zones_of(s)] == [+z for z in want]


# --------------------------------------------------------------------------- reaching winter


class Probe:
    """Records legal actions at scripted points; used as callable entries of `W.Steps`."""

    def __init__(self) -> None:
        self.seen: dict[str, list[list[int]]] = {}

    def at(self, key: str) -> Callable[[Any], None]:
        def rec(state: Any) -> None:
            self.seen.setdefault(key, []).append(list(state.legal_actions()))

        return rec

    def union(self, key: str) -> set[int]:
        """Legal ids over every recording of `key`. Every winter phase gives each seat an explicit
        node ending in DONE (user decision), so a missing node is a failure."""
        assert key in self.seen, f"probe {key!r} never ran (the node was not offered)"
        return {a for legal in self.seen[key] for a in legal}

    def last(self, key: str) -> list[int]:
        got = self.seen.get(key)
        assert got, f"probe {key!r} never ran (the node was not offered)"
        return got[-1]


def first_winter(
    steps: W.Steps | None = None, *, j: bool = False, n: int = 2, seed: int = SEED
) -> tuple[Any, dict[str, Any]]:
    """State and snapshot at the first turn-boundary node of round 4 (the winter start)."""
    run = R.drive(params(n, j), seed=seed, policy=policy(steps), stop=lambda c: c.round == 4)
    assert run.stopped, "round 4 never started"
    sn = R.try_snapshot(run.state)
    assert sn is not None
    return run.state, sn


def at_phase(
    steps: W.Steps | None,
    phase: str,
    which: int = 0,
    *,
    j: bool = False,
    n: int = 2,
    seed: int = SEED,
) -> tuple[Any, dict[str, Any]]:
    """State at the turn of the `which`-th seat (clearing order) in a round-4 phase, plus the
    snapshot of the winter start for before/after comparisons."""
    _, base = first_winter(steps, j=j, n=n, seed=seed)
    order = base["clearing_order"]
    s = reach(steps, (4, phase, order[which]), j=j, n=n, seed=seed)
    return s, base


def snap(s: Any) -> dict[str, Any]:
    sn = R.try_snapshot(s)
    assert sn is not None, "not at a turn boundary"
    return sn


def in_sf(s: Any) -> bool:
    """True at a shortfall node (mid-turn: no snapshot) or a SF-phase boundary."""
    if s.is_terminal() or s.is_chance_node():
        return False
    sn = R.try_snapshot(s)
    return sn is None or sn["phase"] == "SF"


def to_shortfall(
    steps: W.Steps | None, seat: int, *, j: bool = False, n: int = 2, seed: int = SEED
) -> Any:
    """Play round 4 up to the shortfall node of `seat` (feeding first). Other seats are resolved
    with the default policy. Fails if `seat` never reaches a shortfall."""
    _, base = first_winter(steps, j=j, n=n, seed=seed)
    last = base["clearing_order"][-1]
    s = reach(steps, (4, "N4", last), j=j, n=n, seed=seed)
    s.apply_action(H.DONE)
    for _ in range(200):
        if in_sf(s) and s.current_player() == seat:
            return s
        assert not s.is_terminal() and not s.is_chance_node(), "left winter without a shortfall"
        sn = R.try_snapshot(s)
        if sn is not None and sn["round"] != 4:
            raise AssertionError("round 4 ended without a shortfall for the seat")
        legal = s.legal_actions()
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("to_shortfall: too many steps")


def sells(legal: list[int]) -> list[int]:
    return [a for a in legal if a in M.SELL_IDS]


# --------------------------------------------------------------------------- final sale model


def final_dollars(
    s: dict[str, Any],
    req: tuple[int, int],
    joiners: int | None = None,
    river_choice: int | None = None,
) -> dict[str, Any]:
    """Reference model of one seat's end: year-2 winter (`settle`), then the final sale (R-081,
    R-082: sale and drying areas, river with ONE kind, joinery covered by joiners, tasks ignored
    because Phase 2 fixtures complete none), then the loan repayment (R-077, R-083).

    `s` is a seat dict from a snapshot taken before feeding in round 8. Raises if both firewood
    and softwood stand on the river (that choice is a seat decision, not modelled)."""
    j = int(s.get("joiners", 0)) if joiners is None else joiners
    st = settle(s, req, joiners=j)
    money = int(st["money"])
    zs = st["zones"]
    for z in range(4):
        for name, cnt in zs[z].items():
            money += cnt * (piece_price(z, name) or 0)
    river = pm(s.get("river"))
    kinds = {k.split("_")[0] for k, v in river.items() if v and piece_price(0, k) is not None}
    if len(kinds) > 1:
        assert river_choice is not None, "both kinds on the river: pass the seat's choice"
        kinds = {("firewood", "softwood")[river_choice]}
    for name, cnt in river.items():
        base = piece_price(5, name)  # no area bonus
        if base is not None and name.split("_")[0] in kinds:
            money += cnt * base
    bonus = int(R.setup_data()["joinery_bonus"])
    for q, kind in enumerate(s.get("joinery") or []):
        if kind and q < j:
            money += int(piece_price(5, f"{kind}_log") or 0) + bonus
    repay = R.setup_data()["loans"]["repayment"]
    loans = int(st["loans"])
    return {"dollars": money - (int(repay[loans]) if loans else 0), "loans": loans}


def winloss_returns(d: list[float]) -> list[float]:
    """R-084/R-085 from final dollars."""
    n = len(d)
    top = max(d)
    k = sum(1 for x in d if x == top)
    if k == n:
        return [0.0] * n
    win = (n - k) / (k * (n - 1))
    return [win if x == top else -1 / (n - 1) for x in d]


def margin_returns(d: list[float]) -> list[float]:
    """R-086: clip((d_i - mean of the others) / 50, -1, 1)."""
    n = len(d)
    out: list[float] = []
    for x in d:
        rest = (sum(d) - x) / (n - 1)
        out.append(max(-1.0, min(1.0, (x - rest) / 50)))
    return out


def _last_n4_of_round_8(c: R.Ctx) -> bool:
    return bool(
        c.round == 8
        and c.phase == "N4"
        and c.snap is not None
        and c.player == c.snap["clearing_order"][-1]
    )


def play_to_end(
    steps: W.Steps | None,
    *,
    n: int = 2,
    j: bool = False,
    returns: str = "win_loss",
    seed: int = SEED,
    fs: dict[int, int] | None = None,
) -> tuple[dict[str, Any], Any, list[tuple[int, str, int]]]:
    """Play with `steps` to the last seat's N4 turn of round 8, snapshot there (before the year-2
    feeding and heating), then play the default policy to the end.
    Returns (snapshot, final state, decision log of round 8)."""
    run = R.drive(
        {**params(n, j), "returns": returns},
        seed=seed,
        policy=policy(steps),
        stop=_last_n4_of_round_8,
    )
    assert run.stopped, "round 8 N4 never reached"
    sn = snap(run.state)
    s = run.state
    log: list[tuple[int, str, int]] = [e for e in run.log if e[0] == 8]
    for _ in range(500):
        if s.is_terminal():
            return sn, s, log
        assert not s.is_chance_node(), "chance node after round 8 N4"
        sn2 = R.try_snapshot(s)
        log.append((8, sn2["phase"] if sn2 else "SF", s.current_player()))
        legal = s.legal_actions()
        if sn2 is not None and sn2["phase"] == "FS":
            # final-sale river choice: DONE is never offered; the seat's chosen kind is played
            assert H.DONE not in legal, "DONE must not be offered at FS"
            sales = [a for a in legal if RIVER_SALE0 <= a < RIVER_SALE0 + 2]
            assert sales, f"FS without a RIVER_SALE option: {legal}"
            want = RIVER_SALE0 + (fs or {}).get(s.current_player(), 0)
            assert want in sales, (want, legal)
            s.apply_action(want)
            continue
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("play_to_end: too many steps")


def raft_steps(seats: tuple[int, ...]) -> W.Steps:
    """Each listed seat takes a raft token in round 7, skips woodcutting and moves one firewood
    disk onto its river with its mill worker (log driving, R-053). River wood left after year 2's
    fall is sold at the final sale and cannot be sold earlier (R-046, R-073)."""

    def raft_loc(s: Any) -> int:
        toks: dict[int, str] = H.tokens(snap(s))  # pyright: ignore[reportUnknownMemberType]
        locs = [k for k, v in toks.items() if v == "raft"]
        assert locs, "no raft token on the path"
        return H.MOVE_TO(min(locs))

    st = W.Steps()
    for seat in seats:
        st.add(7, "TR", seat, raft_loc, R.MOVE_CLEARING)
        st.add(7, "W1", seat, H.DONE)
        st.add(7, "W3", seat, W.Opt(W.assign(1)), W.river_move(W.FW), W.Opt(W.END_TRIP))
    return st


# --------------------------------------------------------------------------- final sale choice

RIVER_SALE0 = 438  # RIVER_SALE(k): k 0 firewood, 1 softwood (ACTIONS section 3)


def softwood_pick_seed(n: int = 2, j: bool = False, rnd: int = 5) -> tuple[int, int]:
    """(seed, 0-based area) with softwood in a cutting area other than area 0 at round `rnd`'s
    picks under default play (the other seats pick area 0). Placement cards (R-037) add it."""
    for seed in range(300):
        run = R.drive(
            params(n, j),
            seed=seed,
            policy=R.cut_all_wood,
            stop=lambda c: c.round == rnd and c.phase == "PK",
        )
        if not run.stopped:
            continue
        sn = snap(run.state)
        for a in range(1, 6):
            if W.area_wood(sn, a)["softwood"] > 0:
                return seed, a
    raise AssertionError("no seed with softwood in a cutting area")


def both_kinds_steps(seat: int, rnd: int = 5) -> W.Steps:
    """`seat` cuts a softwood disk in round `rnd` (picks the area holding softwood, mill worker),
    then in round 7 takes BOTH raft tokens, skips woodcutting and moves one firewood and one
    softwood disk onto its river: both kinds stand on the river at the end of year 2's fall."""
    cache: list[int] = []

    def first_raft(s: Any) -> int:
        toks: dict[int, str] = H.tokens(snap(s))  # pyright: ignore[reportUnknownMemberType]
        locs = sorted(k for k, v in toks.items() if v == "raft")
        assert len(locs) >= 2, "two raft tokens needed"
        cache[:] = locs
        return H.MOVE_TO(locs[0])

    def second_raft(_s: Any) -> int:
        return H.MOVE_TO(cache[1])

    st = W.Steps()
    st.add(rnd, "PK", seat, W.kind_pick("softwood"))
    st.add(rnd, "W1", seat, W.Opt(W.assign(1)), W.first_take(W.SW), W.Opt(H.DONE))
    st.add(7, "TR", seat, first_raft, second_raft, R.MOVE_CLEARING)
    st.add(7, "W1", seat, H.DONE)
    st.add(
        7, "W3", seat, W.Opt(W.assign(1)), W.river_move(W.FW), W.river_move(W.SW), W.Opt(END_TRIP)
    )
    return st
