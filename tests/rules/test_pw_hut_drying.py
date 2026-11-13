"""Phase 4 unit 6: PW Hut Construction (R-095) and PW Drying (R-096), with the R-059 interaction.

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (5.7, A1, A7) and the harness only. There is no
scenario loader, so every state is reached by scripted play: a 2-player base-side game with chosen
PW_DRAW cards, a travel script per (round, seat) resolved lazily from that round's path, and
per-phase `W.Steps`. Seeds are searched until the path gives the scripted holdings.

Conventions
  * PW card index c = order in data/components/planned_work.yaml (Hut Construction 5, Drying 6);
    PLAN_WORK(c, pair) = 67 + 3c + pair - 1; a plan made in round 1 with pair 1 targets round 2.
  * BUILD_HUT(v) = 134 + v (v 1 = PW, 2 tokens), HUT_TOKEN(x) = 136 + x (board 0, shingle 1,
    stake 2, reed 3, joker 4), HUT_AREA(h) = 141 + h (0 drying, 1 food, 2 worker).
  * DRY_ENTER(p) = 432 + p (p 0 firewood disk, 1 firewood log), SELL ids 396..431.
  * Scenario dumps exist only at turn boundaries, and the forced advance of the drying areas is
    applied at the first DRY_ENTER or DONE (ACTIONS A7), so results are read at the next boundary.
Not covered here: the Small Workshop reed (unit 10) and the Drying Area Upgrade mix (unit 11).
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as SM
from tests.support import travel as T
from tests.support import woodwork as W

PW_LOC = 8
MARKET = 19
PW_DRAW0 = 47
PLAN0 = 67
BUILD_HUT0 = 134
BUILD_HUT_PW = 135
LOAN = H.TAKE_LOAN
CLEAR = R.MOVE_CLEARING
HUT_IDS = range(134, 168)
SELL_IDS = range(396, 432)
FW_DISK, FW_LOG = 0, 1
LOG = "firewood_log"
DISK = "firewood_disk"
SAW0 = 214

_DATA = R._yaml("planned_work.yaml")["planned_work"]  # pyright: ignore[reportPrivateUsage]
IDS: list[str] = [c["id"] for c in _DATA]
HUTC = IDS.index("pw_hut_construction")
DRYC = IDS.index("pw_drying")
TRADE = IDS.index("pw_trade")
CRAFT = IDS.index("pw_craftwork")
assert (HUTC, DRYC) == (5, 6)
assert all("summer" in _DATA[c]["seasons"] for c in (HUTC, DRYC))

LAYOUT = [HUTC, DRYC, TRADE, CRAFT]


def PLAN(c: int, pair: int = 1) -> int:
    return PLAN0 + 3 * c + (pair - 1)


def hut_token(x: int) -> int:
    return 136 + x


def hut_area(h: int) -> int:
    return 141 + h


BOARD, SHINGLE, STAKE, REED, JOKER = range(5)
TYPE_X = {"board": BOARD, "shingle": SHINGLE, "stake": STAKE, "reed": REED, "joker": JOKER}
CRAFT_TYPES = ("board", "shingle", "stake", "reed", "joker")


class NoSeed(Exception):
    """This seed's path cannot give the scripted holdings; try the next one."""


# --------------------------------------------------------------------------- scripted play


def build(cards: list[int], seed: int) -> Any:
    """Setup with the PW_DRAW outcomes `cards` in order; stops at the first travel node."""
    game: Any = H.as_game({"players": 2, "joinery": False})  # pyright: ignore[reportUnknownMemberType]
    s: Any = game.new_initial_state()
    rng = random.Random(seed)
    want = [PW_DRAW0 + c for c in cards]
    while not s.is_terminal():
        if s.is_chance_node():
            outs = [a for a, p in s.chance_outcomes() if p > 0]
            if want and all(PW_DRAW0 <= a < PW_DRAW0 + 10 for a in outs):
                a = want.pop(0)
                assert a in outs
                s.apply_action(a)
            else:
                s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
            continue
        sn = R.try_snapshot(s)
        if sn is None or sn["phase"] not in ("SP", "PK"):
            break
        s.apply_action(s.legal_actions()[0])
    assert not want and H.phase_of(s) == "TR"  # pyright: ignore[reportUnknownMemberType]
    return s


Want = tuple[Any, ...]
_HIRE = {"bearers": R.HIRE_BEARER, "woodcutters": R.HIRE_WOODCUTTER, "sawyers": R.HIRE_SAWYER}


def _resolve(sn: dict[str, Any], seat: int, wants: list[Want], clear: bool) -> list[int]:
    """wants: ("plan", c, pair) | ("hire", name, n) | ("spots", kinds, n) | ("pick", [types])
    (for each listed craftwork type the lowest free spot holding it) | ("any", n) (the n lowest
    non-reed, non-joker craftwork spots)."""
    me = T.seat_of(sn, seat)
    toks = T.spots(sn)
    taken: set[int] = set()
    visits: list[tuple[int, list[int]]] = []

    def free(kind: tuple[str, ...]) -> list[int]:
        return sorted(
            loc
            for loc, t in toks.items()
            if t in kind and me["foreman"] < loc < MARKET and loc not in taken
        )

    for w in wants:
        kind = w[0]
        if kind == "plan":
            visits.append((PW_LOC, [PLAN(w[1], w[2])]))
        elif kind == "hire":
            name, count = w[1], w[2]
            if name == "woodcutters" and T.own_wood(sn, seat) - me["hired"]["woodcutters"] < count:
                raise NoSeed("not enough wood in the cutting area")
            visits.append((R.loc(False, name), [_HIRE[name]] * count + [H.DONE]))
        elif kind == "spots":
            locs = free(w[1])[: w[2]]
            taken.update(locs)
            visits += [(loc, []) for loc in locs]
        elif kind == "pick":
            for t in w[1]:
                got = free((t,))
                if not got:
                    raise NoSeed(f"no {t} spot")
                taken.add(got[0])
                visits.append((got[0], []))
        elif kind == "any":
            locs = free(("board", "shingle", "stake"))[: w[1]]
            if len(locs) < w[1]:
                raise NoSeed("not enough craftwork spots")
            taken.update(locs)
            visits += [(loc, []) for loc in locs]
        else:  # pragma: no cover
            raise AssertionError(kind)
    visits.sort(key=lambda v: v[0])
    out: list[int] = []
    for loc, acts in visits:
        out += [H.MOVE_TO(loc), *acts]
    if clear:
        out.append(R.MOVE_CLEARING)
    return out


class Tr:
    """Travel scripts per (round, seat), resolved at the seat's first travel node of the round.
    A seat with no entry goes to the clearing; with clear=False the queue ends without it."""

    def __init__(self, wants: dict[tuple[int, int], list[Want]], clear: bool = True):
        self.wants = wants
        self.clear = clear
        self.q: dict[tuple[int, int], list[int]] = {}

    def __call__(self, ctx: R.Ctx) -> int | None:
        key = (ctx.round, ctx.player)
        if ctx.phase != "TR" or key not in self.wants:
            return None
        if key not in self.q:
            assert ctx.snap is not None
            self.q[key] = _resolve(ctx.snap, ctx.player, self.wants[key], self.clear)
        return self.q[key].pop(0) if self.q[key] else None

    def exhausted(self, key: tuple[int, int]) -> bool:
        if key not in self.q:
            return self.wants.get(key) == []
        return not self.q[key]


def best_area(ctx: R.Ctx) -> int | None:
    if ctx.phase != "PK" or ctx.snap is None:
        return None
    legal = [a for a in ctx.legal if 2 <= a <= 7]
    if not legal:
        return None
    return max(legal, key=lambda a: (W.area_total(ctx.snap, a - 2), -a))


_CACHE: dict[Any, Any] = {}


def reach(
    key: Any,
    wants: dict[tuple[int, int], list[Want]],
    steps: Any,
    stop: tuple[Any, ...],
    check: Any,
    cards: list[int] | None = None,
    max_seeds: int = 120,
) -> Any:
    """State at `stop` = ("node", round, phase, seat) or ("tr", round, seat) (the seat has played
    its whole travel script, clearing excluded), for the first seed whose path satisfies `check`.
    A fresh clone each call."""
    if key in _CACHE:
        return _CACHE[key].clone()
    for seed in range(1, max_seeds + 1):
        s = build(cards or LAYOUT, seed)
        tr = Tr(wants, clear=stop[0] != "tr")
        st: W.Steps = steps()
        pol = R.chain(tr, st, best_area)
        rng = random.Random(seed + 1000)
        rnd, ph = 1, "TR"
        found = None
        try:
            for _ in range(30000):
                if s.is_terminal():
                    break
                if s.is_chance_node():
                    s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
                    continue
                sn = R.try_snapshot(s)
                if sn is not None:
                    rnd, ph = sn["round"], sn["phase"]
                ctx = R.Ctx(s, rnd, ph, sn, rng)
                if sn is not None:
                    if stop[0] == "node" and (rnd, ph, s.current_player()) == stop[1:]:
                        found = s
                        break
                    if (
                        stop[0] == "tr"
                        and ph == "TR"
                        and rnd == stop[1]
                        and tr.exhausted((rnd, s.current_player()))
                        and s.current_player() == stop[2]
                    ):
                        found = s
                        break
                a = pol(ctx)
                if a is None:
                    a = R.default_action(ctx)
                assert a in s.legal_actions(), f"scripted action {a} illegal in r{rnd} {ph}"
                s.apply_action(a)
        except NoSeed:
            continue
        if found is not None and check(found):
            _CACHE[key] = found
            return found.clone()
    pytest.fail(f"no seed up to {max_seeds} gives the scripted holdings for {key!r}")


def snap(s: Any) -> dict[str, Any]:
    return T.snap(s)


def me(s: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(s), i)


def craft(s: Any, i: int = 0) -> Counter[str]:
    c = me(s, i)["craftwork"]
    return Counter({k: c.get(k, 0) for k in CRAFT_TYPES if c.get(k, 0)})


def huts(s: Any, i: int = 0) -> dict[str, int]:
    h = me(s, i).get("huts") or {}
    return {k: h.get(k, 0) for k in ("drying", "food", "worker")}


def plans_of(s: Any) -> list[dict[str, Any]]:
    return list(snap(s)["planned_work"]["plans"])


def legal_in(s: Any, rng: range | tuple[int, ...]) -> list[int]:
    return [a for a in s.legal_actions() if a in rng]


def sale(s: Any) -> Counter[str]:
    return W.pm(me(s)["sale"])


def drying(s: Any) -> list[Counter[str]]:
    return [W.pm(x) for x in me(s)["drying"]]


def to_next_boundary(s: Any, pred: Any, limit: int = 400) -> None:
    """End seats' turns (DONE, or the clearing in TR, chance outcomes) until `pred(snapshot,
    seat)` holds at a turn-boundary node of a different node than the start."""
    first = True
    for _ in range(limit):
        if not first and not s.is_chance_node():
            sn = R.try_snapshot(s)
            if sn is not None and pred(sn, s.current_player()):
                return
        first = False
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        elif H.DONE in s.legal_actions():
            s.apply_action(H.DONE)
        elif CLEAR in s.legal_actions():
            s.apply_action(CLEAR)
        else:
            s.apply_action(s.legal_actions()[0])
    raise AssertionError("to_next_boundary: limit")


def to_node(s: Any, rnd: int, phase: str, seat: int = 0) -> None:
    """Advance with the default policy to the turn boundary (rnd, phase, seat)."""
    to_next_boundary(
        s, lambda sn, p: (sn["round"], sn["phase"], p) == (rnd, phase, seat), limit=600
    )


# =========================================================================== R-095 fixtures


def hut_scn(
    key: str,
    r1: list[Want],
    *,
    plan: int | None = HUTC,
    p1_plan: int | None = None,
    r2: list[Want] | None = None,
    stop: tuple[Any, ...] = ("node", 2, "TR", 0),
    check: Any = None,
) -> Any:
    """P0 collects craftwork in round 1 (`r1` plus the plan of `plan`, pair 1: target round 2),
    optionally more in round 2 (`r2`); stops at `stop`."""
    wants: dict[tuple[int, int], list[Want]] = {
        (1, 0): list(r1) + ([("plan", plan, 1)] if plan is not None else [])
    }
    if p1_plan is not None:
        wants[(1, 1)] = [("plan", p1_plan, 1)]
    if r2 is not None:
        wants[(2, 0)] = r2
    return reach(key, wants, W.Steps, stop, check or (lambda s: True))


def two_boards() -> Any:
    return hut_scn(
        "two_boards", [("pick", ["board", "board"])], check=lambda s: craft(s) == {"board": 2}
    )


def build_pw(s: Any, toks: list[int], areas: list[int]) -> None:
    T.play(s, BUILD_HUT_PW, *map(hut_token, toks), *map(hut_area, areas))


# =========================================================================== R-095


def test_R095_two_equal_tokens_build_a_hut_in_the_target_round():
    """R-095: in the target round two boards (the same type twice) allow BUILD_HUT(1); BUILD_HUT(0)
    needs 3 tokens and is not legal. The two tokens are flipped and give 2 hut tokens (drying and
    worker), the craftwork holding is empty afterwards."""
    s = two_boards()
    assert [p["target"] for p in plans_of(s)] == [2] and snap(s)["round"] == 2
    legal = set(s.legal_actions())
    assert BUILD_HUT_PW in legal
    assert BUILD_HUT0 not in legal
    s.apply_action(BUILD_HUT_PW)
    assert hut_token(BOARD) in s.legal_actions()
    T.play(s, hut_token(BOARD))
    assert hut_token(BOARD) in s.legal_actions()  # the same type again
    T.play(s, hut_token(BOARD), hut_area(0), hut_area(2))
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert huts(s) == {"drying": 1, "food": 0, "worker": 1}
    assert not craft(s)


def test_R095_hut_uses_exactly_two_tokens_not_three():
    """R-095: the PW hut takes 2 tokens and gives 2 hut tokens; after the second HUT_TOKEN only
    HUT_AREA (and TAKE_LOAN) is legal, no third HUT_TOKEN."""
    s = two_boards()
    T.play(s, BUILD_HUT_PW, hut_token(BOARD), hut_token(BOARD))
    legal = set(s.legal_actions())
    assert not legal & {hut_token(x) for x in range(5)}
    assert hut_area(0) in legal and hut_area(1) in legal and hut_area(2) in legal
    assert H.DONE not in legal and CLEAR not in legal
    T.play(s, hut_area(1), hut_area(1))
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert sum(huts(s).values()) == 2


def test_R095_two_different_types_build():
    """R-095: board + stake (two different types, no shingle) is a valid PW hut."""
    s = hut_scn(
        "board_stake",
        [("pick", ["board", "stake"])],
        check=lambda s: craft(s) == {"board": 1, "stake": 1},
    )
    assert BUILD_HUT_PW in s.legal_actions()
    assert BUILD_HUT0 not in s.legal_actions()
    build_pw(s, [BOARD, STAKE], [1, 1])
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert huts(s) == {"drying": 0, "food": 2, "worker": 0}


def test_R095_joker_counts_as_one_of_the_two():
    """R-095: a joker plus a board is a valid pair (any two of stake/board/shingle/joker)."""
    s = hut_scn(
        "joker_board",
        [("pick", ["joker", "board"])],
        check=lambda s: craft(s) == {"joker": 1, "board": 1},
    )
    assert BUILD_HUT_PW in s.legal_actions()
    s.apply_action(BUILD_HUT_PW)
    assert hut_token(JOKER) in s.legal_actions() and hut_token(BOARD) in s.legal_actions()


def test_R095_one_token_is_not_enough():
    """R-095: a single craftwork token never opens a PW hut build, even in the target round."""
    s = hut_scn("one_board", [("pick", ["board"])], check=lambda s: craft(s) == {"board": 1})
    assert [p["target"] for p in plans_of(s)] == [2]
    assert BUILD_HUT_PW not in s.legal_actions()
    assert BUILD_HUT0 not in s.legal_actions()


def test_R095_reed_is_excluded_without_the_small_workshop():
    """R-095: a reed bundle and a board do not make a PW hut (reed is excluded; the Small Workshop
    exception is unit 10)."""
    s = hut_scn(
        "reed_board",
        [("pick", ["reed", "board"])],
        check=lambda s: craft(s) == {"reed": 1, "board": 1},
    )
    assert [p["target"] for p in plans_of(s)] == [2]
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R095_two_reeds_do_not_build():
    """R-095: two reeds never build a PW hut."""
    s = hut_scn("two_reeds", [("pick", ["reed", "reed"])], check=lambda s: craft(s) == {"reed": 2})
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R095_not_legal_in_the_round_the_card_is_planned():
    """R-095/R-089: P0 plans Hut Construction in round 1 (target round 2) while holding two boards
    in round 1: BUILD_HUT(1) is not legal yet (not the target round), nor is BUILD_HUT(0)."""
    s = hut_scn(
        "planning_round",
        [("pick", ["board", "board"])],
        stop=("tr", 1, 0),
        check=lambda s: craft(s) == {"board": 2} and len(plans_of(s)) == 1,
    )
    assert snap(s)["round"] == 1
    assert BUILD_HUT_PW not in s.legal_actions()
    assert BUILD_HUT0 not in s.legal_actions()


def test_R095_not_legal_in_the_round_after_the_target():
    """R-095: with two boards carried unbuilt from round 1 to round 3 (the round after the target
    round 2), BUILD_HUT(1) is not legal."""
    s = hut_scn(
        "round_after",
        [("pick", ["board", "board"])],
        stop=("node", 3, "TR", 0),
        check=lambda s: craft(s) == {"board": 2},
    )
    assert snap(s)["round"] == 3
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R095_other_seats_plan_does_not_help_me():
    """R-089/R-095: P1 planned Hut Construction for round 2; P0 (no plan) holding two boards in
    round 2 may not use BUILD_HUT(1)."""
    s = hut_scn(
        "other_plan",
        [("pick", ["board", "board"])],
        plan=None,
        p1_plan=HUTC,
        check=lambda s: craft(s) == {"board": 2},
    )
    assert [p["seat"] for p in plans_of(s)] == [1]
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R095_no_plan_no_pw_build():
    """R-095: without any Hut Construction plan, two boards in round 2 give no BUILD_HUT at all."""
    s = hut_scn(
        "no_plan",
        [("pick", ["board", "board"])],
        plan=None,
        check=lambda s: craft(s) == {"board": 2},
    )
    assert plans_of(s) == []
    assert not legal_in(s, range(134, 136))


def test_R095_repeatable_in_the_target_round():
    """R-095: with four tokens (two collected in round 1, two more in round 2) the seat builds a PW
    hut twice in the target round: each uses 2 tokens and gives 2 hut tokens, 4 in all."""
    s = hut_scn(
        "four_tokens",
        [("any", 2)],
        r2=[("any", 2)],
        stop=("tr", 2, 0),
        check=lambda s: sum(craft(s).values()) == 4 and not craft(s)["reed"],
    )
    held = craft(s)
    assert BUILD_HUT_PW in s.legal_actions()
    first = sorted(list(held.elements()), key=lambda t: TYPE_X[t])[:2]
    build_pw(s, [TYPE_X[t] for t in first], [0, 0])
    assert BUILD_HUT_PW in s.legal_actions()  # the second pair is still held
    rest = held - Counter(first)
    second = sorted(list(rest.elements()), key=lambda t: TYPE_X[t])
    build_pw(s, [TYPE_X[t] for t in second], [0, 1])
    assert BUILD_HUT_PW not in s.legal_actions()
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert huts(s) == {"drying": 3, "food": 1, "worker": 0}
    assert not craft(s)


def test_R095_three_tokens_leave_one_after_a_pw_build():
    """R-095: building from a holding of three tokens uses 2; the third stays in hand and cannot
    start another PW build alone."""
    s = hut_scn(
        "three_tokens",
        [("any", 3)],
        check=lambda s: sum(craft(s).values()) == 3,
    )
    held = craft(s)
    first = sorted(list(held.elements()), key=lambda t: TYPE_X[t])[:2]
    build_pw(s, [TYPE_X[t] for t in first], [2, 2])
    assert BUILD_HUT_PW not in s.legal_actions()
    assert BUILD_HUT0 not in s.legal_actions()
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert sum(craft(s).values()) == 1
    assert huts(s)["worker"] == 2


def test_R095_window_closes_after_first_move():
    """R-095/R-100 (C5, A1): BUILD_HUT(1) is legal at the start of the travel turn but not after
    the first move to a location (the window closes at the first non-window action)."""
    s = hut_scn(
        "window",
        [("pick", ["board", "board"])],
        stop=("node", 2, "TR", 0),
        check=lambda s: craft(s) == {"board": 2},
    )
    assert BUILD_HUT_PW in s.legal_actions()
    s.apply_action(LOAN)  # a loan does not close the window
    assert BUILD_HUT_PW in s.legal_actions()
    mv = [a for a in s.legal_actions() if a != CLEAR and 7 <= a <= 30]
    assert mv
    s.apply_action(mv[0])
    # in the middle of a visit the window is closed
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R095_loan_mid_build_keeps_it_open():
    """R-095/ACTIONS 5.7: TAKE_LOAN is the only other action during a PW build and keeps it open."""
    s = two_boards()
    s.apply_action(BUILD_HUT_PW)
    assert LOAN in s.legal_actions()
    s.apply_action(LOAN)
    T.play(s, hut_token(BOARD), hut_token(BOARD), hut_area(0), hut_area(0))
    s.apply_action(CLEAR)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "TR")
    assert me(s)["loans"] == 1
    assert huts(s)["drying"] == 2


# =========================================================================== R-096 fixtures


def _carries(dests: tuple[int, ...]) -> list[Any]:
    out: list[Any] = []
    for d in dests:
        out += [W.Opt(W.assign(0)), W.move_wood(W.FW, d)]
    return out


def dry_scn(
    key: str,
    *,
    plan: int | None = DRYC,
    p1_plan: int | None = None,
    dests: tuple[int, ...] = (0,),
    saws: int = 1,
    mills: int = 1,
    in_r1: bool = False,
    stop: tuple[Any, ...] = ("node", 2, "W7", 0),
    check: Any = None,
) -> Any:
    """P0 cuts len(dests) firewood disks in round 1 (hired woodcutter + mill worker) and carries
    each to dest 0 (sawing area) or 1 (sale area, unmilled). `mills` disks are then milled (1 saw
    per mill, saws collected in round 1) in round 2 (or round 1 with `in_r1`) at W4, all logs to
    the sale area. A plan is for round 1 pair 1 (target round 2). Stops at `stop`."""
    n = len(dests)
    r1: list[Want] = [("hire", "bearers", n)]
    if n == 2:
        r1.append(("hire", "woodcutters", 1))
    if saws:
        r1.append(("spots", ("saw",), min(saws, 1)))  # 2 players: one saw token per path
    wants: dict[tuple[int, int], list[Want]] = {}
    if in_r1 and mills:
        r1.append(("hire", "sawyers", 1))
    elif mills > 1 or (mills and not in_r1):
        wants[(2, 0)] = [("hire", "sawyers", 1)] if mills >= 1 and n >= 1 else []
    if saws == 2:  # the second saw comes from round 2's path
        wants[(2, 0)] = [*wants.get((2, 0), []), ("spots", ("saw",), 1)]
    wants[(1, 0)] = r1 + ([("plan", plan, 1)] if plan is not None else [])
    if p1_plan is not None:
        wants[(1, 1)] = [("plan", p1_plan, 1)]
    if mills == 2:
        # one sawyer plus the mill worker mill; the sawyer is hired in the milling round
        pass
    mill_round = 1 if in_r1 else 2

    def steps() -> W.Steps:
        st = W.Steps()
        cuts = [0, 1][:n] if n == 2 else [1]
        for src in cuts:
            st.add(1, "W1", 0, W.Opt(W.assign(src)), W.first_take(-1))
        st.add(1, "W3", 0, *_carries(dests))
        if mills:
            st.add(mill_round, "W4", 0, W.Opt(W.assign(0)), W.Opt(SM.saw(0, 0)))
            if mills == 2:
                st.add(mill_round, "W4", 0, W.Opt(W.assign(1)), W.Opt(SM.saw(0, 0)))
        return st

    return reach(key, wants, steps, stop, check or (lambda s: True))


def four_logs(key: str = "four_logs", **kw: Any) -> Any:
    return dry_scn(
        key,
        check=lambda s: sale(s) == Counter({LOG: 4}) and not drying(s)[0],
        **kw,
    )


def enter(s: Any, piece: int = FW_LOG) -> None:
    s.apply_action(SM.dry_enter(piece))


def count_entries(s: Any, piece: int = FW_LOG) -> int:
    """Apply DRY_ENTER(piece) while legal; returns how many went in."""
    n = 0
    while SM.dry_enter(piece) in s.legal_actions():
        s.apply_action(SM.dry_enter(piece))
        n += 1
        assert n < 20
    return n


# =========================================================================== R-096


def test_R096_fixture_four_logs_in_sale_at_w7_target_round():
    """R-096 (fixture sanity): P0 holds the Drying plan for round 2 and 4 milled firewood in the
    sale area at the round-2 drying phase."""
    s = four_logs()
    assert [(p["seat"], p["target"]) for p in plans_of(s)] == [(0, 2)]
    assert sale(s) == Counter({LOG: 4})


def test_R096_four_milled_logs_enter_first_area_in_target_round():
    """R-096: in the target round the first drying area holds 4 milled logs: all four DRY_ENTER."""
    s = four_logs()
    assert count_entries(s) == 4
    to_next_boundary(s, lambda sn, p: sn["round"] == 3)
    # (one more turn boundary is fine; the logs keep drying, see the forced-advance tests)
    assert sum(sum(d.values()) for d in drying(s)) == 4
    assert not sale(s)


def test_R096_without_plan_only_two_logs_enter():
    """R-096 baseline / R-059: the same four logs in the round-2 drying phase without the plan fill
    the first area to its normal capacity of 2 only."""
    s = four_logs("four_logs_noplan", plan=None)
    assert plans_of(s) == []
    assert count_entries(s) == 2


def test_R096_other_seats_plan_does_not_double_my_area():
    """R-089/R-096: P1 planned Drying for round 2; P0 (no plan) still fits 2 logs only."""
    s = four_logs("four_logs_p1plan", plan=None, p1_plan=DRYC)
    assert [p["seat"] for p in plans_of(s)] == [1]
    assert count_entries(s) == 2


def test_R096_not_doubled_in_the_planning_round():
    """R-089/R-096: planning Drying in round 1 does not double the area in round 1 itself (the
    target round is 2): 4 logs milled in round 1 enter the first area two at a time only."""
    s = dry_scn(
        "four_logs_r1",
        in_r1=True,
        stop=("node", 1, "W7", 0),
        check=lambda s: sale(s) == Counter({LOG: 4}),
    )
    assert [p["target"] for p in plans_of(s)] == [2]
    assert count_entries(s) == 2


def test_R096_not_doubled_in_the_round_after_the_target():
    """R-096: the doubling is for the target round's entries only; the 4 logs stay a stack over the
    normal capacity and are forced on together at round 3's drying phase (R-059), leaving area 1
    empty."""
    s = four_logs()
    count_entries(s)
    to_node(s, 3, "W7", 0)
    assert drying(s)[0] == Counter({LOG: 4})  # still on area 1 at the turn boundary (A7)
    s.apply_action(H.DONE)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert drying(s)[0] == Counter()
    assert drying(s)[1] == Counter({LOG: 4})


def test_R096_round_after_target_only_normal_capacity_for_entries():
    """R-096: the doubling is for the target round only: with 8 logs in the sale area, 4 enter in
    round 2 and in round 3 only 2 (the normal capacity) more can enter."""
    s = dry_scn(
        "eight_logs",
        dests=(0, 0),
        saws=2,
        mills=2,
        check=lambda s: sale(s) == Counter({LOG: 8}),
    )
    assert count_entries(s) == 4
    to_node(s, 3, "W7", 0)
    assert count_entries(s) == 2


def _two_disks_in_sale(key: str, plan: int | None) -> Any:
    return dry_scn(
        key,
        plan=plan,
        dests=(1, 1),
        saws=0,
        mills=0,
        check=lambda s: sale(s) == Counter({DISK: 2}),
    )


def test_R096_two_unmilled_disks_fit_in_target_round():
    """R-096: the first area holds 2 unmilled disks in the target round."""
    s = _two_disks_in_sale("two_disks_plan", DRYC)
    assert count_entries(s, FW_DISK) == 2


def test_R096_without_plan_only_one_disk_fits():
    """R-059 baseline: without the plan the first area takes 1 unmilled disk."""
    s = _two_disks_in_sale("two_disks_noplan", None)
    assert count_entries(s, FW_DISK) == 1


def test_R096_disk_and_logs_never_mix_disk_first():
    """R-096: once a disk is in the first area no log may enter it, even with the doubled
    capacity (a disk is never mixed with logs)."""
    s = dry_scn(
        "disk_and_logs",
        dests=(0, 1),
        check=lambda s: sale(s) == Counter({LOG: 4, DISK: 1}),
    )
    legal = set(s.legal_actions())
    assert SM.dry_enter(FW_DISK) in legal and SM.dry_enter(FW_LOG) in legal
    enter(s, FW_DISK)
    assert SM.dry_enter(FW_LOG) not in s.legal_actions()
    assert SM.dry_enter(FW_DISK) not in s.legal_actions()  # only one disk is in the sale area


def test_R096_disk_and_logs_never_mix_log_first():
    """R-096: once a log is in the first area the disk may not enter it."""
    s = dry_scn(
        "disk_and_logs",
        dests=(0, 1),
        check=lambda s: sale(s) == Counter({LOG: 4, DISK: 1}),
    )
    enter(s, FW_LOG)
    assert SM.dry_enter(FW_DISK) not in s.legal_actions()
    assert SM.dry_enter(FW_LOG) in s.legal_actions()


def test_R096_five_logs_cap_at_four():
    """R-096: the doubled area holds 4 logs, not more: with 8 milled logs in the sale area (two
    sawyers' worth, two saws) only 4 enter, the other 4 stay in the sale area."""
    s = dry_scn(
        "eight_logs",
        dests=(0, 0),
        saws=2,
        mills=2,
        check=lambda s: sale(s) == Counter({LOG: 8}),
    )
    assert count_entries(s) == 4
    s.apply_action(H.DONE)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "W7")
    assert drying(s)[0] == Counter({LOG: 4})
    assert sale(s) == Counter({LOG: 4})


def test_R096_forced_advance_over_capacity_example():
    """R-096 example: 4 logs put into area 1 in the target round (2) all move together into area 2
    at round 3's drying phase (over its capacity of 2); winter round 4 does not dry them; round 5's
    drying moves all 4 into area 3; round 6's selling must sell all 4 (DONE illegal until then)
    for 4 x ($1 + $2).

    Fixture: scripted P0 cannot pay winter 1 (it would hit the R-073 shortfall sale, which sells
    these logs; see test_R096_winter_shortfall_sells_the_drying_logs), so before the drying phase of
    round 3 the seats are given food, heating wood and money directly (white-box, as the
    winter-payment tests do)."""
    s = four_logs("example_logs")
    count_entries(s)
    to_node(s, 3, "W7", 0)
    assert drying(s) == [Counter({LOG: 4}), Counter(), Counter()]
    s.food = (20, 20)  # winter 1 is then paid in full: no loans and no shortfall sale
    s.store = ((20, 0, 0), (20, 0, 0))
    s.money = (30, 30)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert drying(s) == [Counter(), Counter({LOG: 4}), Counter()]
    # winter round 4: nothing dries
    to_node(s, 5, "W6", 0)
    assert drying(s) == [Counter(), Counter({LOG: 4}), Counter()]
    to_node(s, 5, "W7", 0)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 6)
    to_node(s, 6, "W6", 0)
    assert drying(s) == [Counter(), Counter(), Counter({LOG: 4})]
    assert H.DONE not in s.legal_actions()
    money = me(s)["money"]
    sells = legal_in(s, SELL_IDS)
    assert sells
    while sells:
        s.apply_action(sells[0])
        sells = legal_in(s, SELL_IDS)
    assert H.DONE in s.legal_actions()
    s.apply_action(H.DONE)
    to_next_boundary(s, lambda sn, p: p == 0 and sn["phase"] != "W6")
    assert me(s)["money"] == money + 12
    assert drying(s)[2] == Counter()


def test_R096_winter_shortfall_sells_the_drying_logs():
    """R-096/R-073/R-074: in the example scenario P0 (money $4, no food, no heating wood) cannot
    pay winter 1: after both loans the shortfall sale takes the 4 logs from the drying area (the
    sale and drying areas come first), the rest of the debt is forgiven (D9): at round 5 the drying
    areas are empty, P0 holds 2 loans and $0."""
    s = four_logs("example_logs")
    count_entries(s)
    to_node(s, 3, "W7", 0)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert drying(s) == [Counter(), Counter({LOG: 4}), Counter()]
    to_node(s, 5, "PK", 0)
    assert drying(s) == [Counter(), Counter(), Counter()]
    assert me(s)["loans"] == 2 and me(s)["money"] == 0


def test_R096_forced_advance_ignores_destination_capacity_when_area_2_busy():
    """R-096/R-059: area 2 may be over capacity by the PW stack: after the round-3 advance area 2
    holds all 4 logs although its capacity is 2, and nothing is left behind in area 1."""
    s = four_logs("example_logs")
    count_entries(s)
    to_node(s, 3, "W7", 0)
    s.apply_action(H.DONE)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    d = drying(s)
    assert sum(d[1].values()) == 4 and not d[0] and not d[2]


def test_R096_two_disks_forced_on_together():
    """R-096/R-059: two unmilled disks in the first area (over the normal capacity of 1) move on
    together into the second area at the next drying phase."""
    s = _two_disks_in_sale("two_disks_plan", DRYC)
    count_entries(s, FW_DISK)
    to_node(s, 3, "W7", 0)
    assert drying(s)[0] == Counter({DISK: 2})
    s.apply_action(H.DONE)
    to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert drying(s)[1] == Counter({DISK: 2}) and not drying(s)[0]
