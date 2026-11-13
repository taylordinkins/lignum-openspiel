"""Phase 4 unit 2: selling craftwork sets at the Market (R-105, R-104, R-042, R-006).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (section 5.6, SELL_SET 97-128, SELL_SET_JOKERS 129)
and docs/SCENARIOS.md only, through tests/harness.py and tests/support/{rounds,travel}.py. There is
no scenario loader, so craftwork gets into a seat's hands by scripted play: seat 0 takes craftwork
token spots (R-042) in round 1 (and round 2 for sets that need more than the 3 craftwork tokens a
path fill carries) and then enters the Market (the last non-spot location but one, R-021/R-022).
Which tokens are on the path is random, so `reach` searches for a seed whose fill lets seat 0
collect an exact holding; the tests then read the actual holding from the snapshot.

Conventions
  * SELL_SET(x, s, j) id = 97 + 8x + i with i indexing (s, j) as in ACTIONS 5.6; 129 = jokers only.
  * A Market visit is MOVE_TO(market), actions, then DONE if still open (T.end_visit).
  * Prices come from the setup data (`craftwork_set_prices`: 2 -> 2, 3 -> 4, 4 -> 6), read via
    tests/support/rounds.setup_data().
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

BUY_SAW, BUY_FOOD = 35, 36
SELL_SET0, SELL_JOKERS = 97, 129
SELL_ALL = range(97, 130)
TYPES = ("board", "shingle", "stake", "reed")
CRAFT = (*TYPES, "joker")
_IDX = {(2, 0): 0, (2, 1): 1, (3, 0): 2, (3, 1): 3, (3, 2): 4, (4, 0): 5, (4, 1): 6, (4, 2): 7}
BOOLS = (True, False)
PRICE = {2: 2, 3: 4, 4: 6}


def sell(x: int, s: int, j: int = 0) -> int:
    """ACTIONS 5.6: SELL_SET(x, s, j) for real type x (0..3), total size s, j jokers."""
    return SELL_SET0 + 8 * x + _IDX[(s, j)]


def market(joinery: bool) -> int:
    return 21 if joinery else 19


def sell_ids(state: Any) -> set[int]:
    return {a for a in state.legal_actions() if a in SELL_ALL}


def me(state: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(state), i)


def removed(state: Any) -> dict[str, int]:
    return dict(T.snap(state)["supply"]["craftwork_removed"])


def holding(state: Any, i: int = 0) -> dict[str, int]:
    return dict(me(state, i)["craftwork"])


def oracle_sells(h: dict[str, int]) -> set[int]:
    """Independent statement of R-105 / ACTIONS 5.6: which SELL ids a holding allows."""
    out: set[int] = set()
    jk = h.get("joker", 0)
    for x, t in enumerate(TYPES):
        for (s, j), _ in _IDX.items():
            if s - j >= 1 and s - j <= h.get(t, 0) and j <= jk:
                out.add(sell(x, s, j))
    if jk >= 2:
        out.add(SELL_JOKERS)
    return out


# --------------------------------------------------------------------------- reaching states

_seed_cache: dict[tuple[Any, ...], tuple[int, dict[str, int]] | None] = {}


def _want_full(want: dict[str, int]) -> dict[str, int]:
    return {k: want.get(k, 0) for k in CRAFT}


def reach(
    shape: Callable[[str, str], dict[str, int]],
    joinery: bool,
    key: str,
    max_seed: int = 600,
) -> tuple[Any, dict[str, int]]:
    """Round-1/2 state at a seat-0 move node (3 players) where seat 0 holds exactly one of the
    candidate holdings `shape(t, u)` over real types t != u (all other players in the clearing),
    with the Market still ahead. Returns (state, holding). Fails the test if no seed in range."""
    ck = (key, joinery)
    if ck not in _seed_cache:
        _seed_cache[ck] = None
        for seed in range(1, max_seed + 1):
            for t in TYPES:
                for u in TYPES:
                    if t == u:
                        continue
                    w = _want_full(shape(t, u))
                    if _try(w, joinery, seed) is not None:
                        _seed_cache[ck] = (seed, w)
                        break
                if _seed_cache[ck]:
                    break
            if _seed_cache[ck]:
                break
    found = _seed_cache[ck]
    if found is None:
        pytest.fail(f"no seed up to {max_seed} lets seat 0 collect shape {key!r}")
    seed, w = found
    st = _try(w, joinery, seed)
    assert st is not None
    return st, w


def _try(want: dict[str, int], joinery: bool, seed: int) -> Any | None:
    mk = market(joinery)

    def policy(ctx: R.Ctx) -> int | None:
        if ctx.phase != "TR" or ctx.player != 0 or ctx.snap is None:
            return None
        if R.MOVE_CLEARING not in ctx.legal:
            return None
        sn = ctx.snap
        seat = T.seat_of(sn, 0)
        pos = seat["foreman"]
        best: int | None = None
        for loc, tok in T.spots(sn).items():
            wanted = tok in CRAFT and pos < loc < mk and seat["craftwork"][tok] < want[tok]
            if wanted and H.MOVE_TO(loc) in ctx.legal and (best is None or loc < best):
                best = loc
        return None if best is None else H.MOVE_TO(best)

    def stop(ctx: R.Ctx) -> bool:
        if ctx.round > 2:
            return True
        if ctx.phase != "TR" or ctx.player != 0 or ctx.snap is None:
            return False
        if R.MOVE_CLEARING not in ctx.legal:
            return False
        return T.seat_of(ctx.snap, 0)["craftwork"] == want

    run = R.drive({"players": 3, "joinery": joinery}, seed=seed, policy=policy, stop=stop)
    if not run.stopped:
        return None
    st = run.state
    if holding(st) != want or H.MOVE_TO(mk) not in st.legal_actions():
        return None
    return st


def visit_market(state: Any, joinery: bool, *acts: int) -> Any:
    T.play(state, H.MOVE_TO(market(joinery)), *acts)
    return state


def finish(state: Any) -> None:
    T.end_visit(state)


# a candidate-holding generator needs (t, u); wrappers:
def S_pair(t: str, u: str) -> dict[str, int]:
    return {t: 2}


def S_triple(t: str, u: str) -> dict[str, int]:
    return {t: 3}


def S_quad(t: str, u: str) -> dict[str, int]:
    return {t: 4}


def S_single(t: str, u: str) -> dict[str, int]:
    return {t: 1}


def S_real_joker(t: str, u: str) -> dict[str, int]:
    return {t: 1, "joker": 1}


def S_pair_joker(t: str, u: str) -> dict[str, int]:
    return {t: 2, "joker": 1}


def S_triple_joker(t: str, u: str) -> dict[str, int]:
    return {t: 3, "joker": 1}


def S_pair_2jokers(t: str, u: str) -> dict[str, int]:
    return {t: 2, "joker": 2}


def S_one_2jokers(t: str, u: str) -> dict[str, int]:
    return {t: 1, "joker": 2}


def S_jokers(t: str, u: str) -> dict[str, int]:
    return {"joker": 2}


def S_two_pairs(t: str, u: str) -> dict[str, int]:
    return {t: 2, u: 2}


def S_example(t: str, u: str) -> dict[str, int]:
    """R-105 example: 3 of one type, 1 of another, 1 joker."""
    return {t: 3, u: 1, "joker": 1}


def S_quad_joker_extra(t: str, u: str) -> dict[str, int]:
    return {t: 4, "joker": 1}


def S_one_joker(t: str, u: str) -> dict[str, int]:
    return {"joker": 1}


# --------------------------------------------------------------------------- $0 scenario


_broke_cache: dict[tuple[str, bool], int] = {}


def broke_with(kind: str, joinery: bool) -> Any:
    """4 players; P0 at $0 with 2 loans on location 10 (T.broke_p0) takes craftwork spots between
    location 10 and the Market (the others are already in the clearing): 'pair' = two identical
    real tokens, 'single' = one token. Returns the state at P0's next move node."""
    mk = market(joinery)
    for seed in range(1, 300):
        if _broke_cache.get((kind, joinery), seed) != seed:
            continue
        s = T.broke_p0(joinery, seed)
        tok = {loc: t for loc, t in T.spots(T.snap(s)).items() if 10 < loc < mk and t in CRAFT}
        if kind == "single":
            locs = sorted(tok)[:1]
        else:
            locs = []
            for t in TYPES:
                got = sorted(loc for loc, x in tok.items() if x == t)
                if len(got) >= 2:
                    locs = got[:2]
                    break
        if not locs:
            continue
        _broke_cache[(kind, joinery)] = seed
        for loc in locs:
            T.play(s, H.MOVE_TO(loc))
            assert s.current_player() == 0
        return s
    pytest.fail(f"no seed gives P0 a {kind} of craftwork after location 10")


# --------------------------------------------------------------------------- tests: prices

PRICE_CASES = [
    pytest.param(S_pair, 2, 0, 2, id="pair-2"),
    pytest.param(S_triple, 3, 0, 4, id="triple-4"),
    pytest.param(S_quad, 4, 0, 6, id="quad-6"),
    pytest.param(S_real_joker, 2, 1, 2, id="real+joker-2"),
    pytest.param(S_pair_joker, 3, 1, 4, id="pair+joker-4"),
    pytest.param(S_one_2jokers, 3, 2, 4, id="real+2jokers-4"),
    pytest.param(S_triple_joker, 4, 1, 6, id="triple+joker-6"),
    pytest.param(S_pair_2jokers, 4, 2, 6, id="pair+2jokers-6"),
]


def test_R105_prices_come_from_setup_data():
    """R-105: the base prices of 2/3/4 identical tokens are $2/$4/$6, read from the setup data
    `craftwork_set_prices` (the tests below use the literal values and rely on this agreeing)."""
    assert R.setup_data()["craftwork_set_prices"] == {2: 2, 3: 4, 4: 6}


def _real_type(h: dict[str, int]) -> int:
    return next(i for i, t in enumerate(TYPES) if h[t] > 0)


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("shape,s,j,price", PRICE_CASES)
def test_R105_set_sells_at_size_price_and_tokens_leave_the_game(shape, s, j, price, joinery):
    """R-105: a set of 2/3/4 tokens (identical, jokers counting as any type) pays $2/$4/$6 by
    total size only; the sold tokens leave the seat's craftwork area and are counted in
    craftwork_removed (out of the game); unsold tokens stay."""
    st, h = reach(shape, joinery, shape.__name__)
    x = _real_type(h)
    m0, rm0 = me(st)["money"], removed(st)
    visit_market(st, joinery)
    assert sell(x, s, j) in st.legal_actions()
    T.play(st, sell(x, s, j))
    finish(st)
    assert st.current_player() != 0 or T.at_move_node(st)
    seat = me(st)
    assert seat["money"] == m0 + price
    exp = dict(h)
    exp[TYPES[x]] -= s - j
    exp["joker"] -= j
    assert seat["craftwork"] == exp
    rm1 = removed(st)
    assert rm1[TYPES[x]] - rm0[TYPES[x]] == s - j
    assert rm1["joker"] - rm0["joker"] == j


@pytest.mark.parametrize("joinery", BOOLS)
def test_R105_jokers_only_set_sells_for_two_dollars(joinery):
    """R-105: a set may be made of jokers only; two jokers are a 2-set for $2 (SELL_SET_JOKERS,
    ACTIONS 5.6); both jokers leave the game."""
    st, h = reach(S_jokers, joinery, "S_jokers")
    m0, rm0 = me(st)["money"], removed(st)
    visit_market(st, joinery)
    assert SELL_JOKERS in st.legal_actions()
    T.play(st, SELL_JOKERS)
    finish(st)
    seat = me(st)
    assert seat["money"] == m0 + 2
    assert seat["craftwork"]["joker"] == 0
    assert removed(st)["joker"] - rm0["joker"] == 2


def test_R105_removed_tokens_do_not_return_to_the_pile():
    """R-105/R-017: sold tokens are removed from the game, not returned to the supply: the next
    round's CRAFT_DRAW probabilities are proportional to total - path - held - removed as seen
    before the sale (SCENARIOS derived pile), with the sold tokens NOT added back."""
    st, h = reach(S_triple, False, "S_triple")
    sn = T.snap(st)
    totals = R.craft_totals()
    path_craft = [t for t in T.spots(sn).values() if t in CRAFT]
    pile = {
        k: totals[k]
        - path_craft.count(k)
        - sum(T.seat_of(sn, i)["craftwork"][k] for i in range(3))
        - sn["supply"]["craftwork_removed"][k]
        for k in R.CRAFT
    }
    rnd = sn["round"]
    x = _real_type(h)
    visit_market(st, False, sell(x, 3, 0))
    finish(st)
    rng = random.Random(0)
    for _ in range(20000):
        if st.is_chance_node():
            outs = dict(st.chance_outcomes())
            if H.chance_family(next(iter(outs)))[0] == "CRAFT_DRAW":
                break
            st.apply_action(H.sample_chance(st, rng))
            continue
        ctx = R.Ctx(st, rnd, H.phase_of(st), None, rng)
        st.apply_action(R.default_action(ctx))
    else:  # pragma: no cover
        pytest.fail("never reached the next CRAFT_DRAW")
    tot = sum(pile.values())
    assert tot > 0
    for k, name in enumerate(R.CRAFT):
        assert outs.get(H.CHANCE_BASE["CRAFT_DRAW"] + k, 0) == pytest.approx(pile[name] / tot)


# --------------------------------------------------------------------------- legality


LEGALITY_SHAPES = [
    S_single,
    S_one_joker,
    S_pair,
    S_triple,
    S_quad,
    S_real_joker,
    S_pair_joker,
    S_triple_joker,
    S_pair_2jokers,
    S_one_2jokers,
    S_jokers,
    S_two_pairs,
    S_example,
    S_quad_joker_extra,
]


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("shape", LEGALITY_SHAPES, ids=lambda f: f.__name__[2:])
def test_R105_legal_sells_match_the_holding(shape, joinery):
    """R-105/ACTIONS 5.6: on entering the Market the legal SELL_SET/SELL_SET_JOKERS actions are
    exactly those buildable from the holding: 2-4 tokens of one real type plus at most the held
    jokers (max 2), at least one real token, or exactly two jokers. Nothing else, so no single
    token and nothing above 4."""
    st, h = reach(shape, joinery, shape.__name__)
    visit_market(st, joinery)
    assert sell_ids(st) == oracle_sells(h)


@pytest.mark.parametrize("shape", [S_single, S_one_joker], ids=["token", "joker"])
def test_R105_single_token_cannot_be_sold(shape):
    """R-105: a single craftwork token (real or joker) cannot be sold; no SELL action is legal
    even though the seat can still shop at the Market."""
    st, h = reach(shape, False, shape.__name__)
    visit_market(st, False)
    assert sell_ids(st) == set()
    assert BUY_FOOD in st.legal_actions()


def test_R105_pair_offers_only_the_pair():
    """R-105: holding exactly 2 identical tokens, only the 2-set of that type is legal: no
    3-set, no 4-set, no joker-assisted set."""
    st, h = reach(S_pair, False, "S_pair")
    x = _real_type(h)
    visit_market(st, False)
    assert sell_ids(st) == {sell(x, 2, 0)}


def test_R105_five_tokens_cannot_be_sold_as_one_set():
    """R-105: a set has at most 4 tokens. Holding 4 identical + 1 joker, the best single sale is
    the 4-set for $6; the fifth token stays (the lone joker cannot then be sold)."""
    st, h = reach(S_quad_joker_extra, False, "S_quad_joker_extra")
    x = _real_type(h)
    m0 = me(st)["money"]
    visit_market(st, False)
    legal = sell_ids(st)
    assert sell(x, 4, 0) in legal and sell(x, 4, 1) in legal
    T.play(st, sell(x, 4, 0))
    assert sell_ids(st) == set()
    finish(st)
    seat = me(st)
    assert seat["money"] == m0 + 6
    assert seat["craftwork"]["joker"] == 1 and seat["craftwork"][TYPES[x]] == 0


def test_R105_example_from_the_spec():
    """R-105 example: 3 of one type, 1 of another, 1 joker. May sell the 3 (-> $4), the 3 + joker
    as a 4-set ($6), or 2 of the triple ($2); cannot sell the single alone; single + joker is a
    2-set ($2)."""
    st, h = reach(S_example, False, "S_example")
    x = next(i for i, t in enumerate(TYPES) if h[t] == 3)
    y = next(i for i, t in enumerate(TYPES) if h[t] == 1)
    m0 = me(st)["money"]
    visit_market(st, False)
    legal = sell_ids(st)
    assert {sell(x, 3, 0), sell(x, 4, 1), sell(x, 2, 0), sell(y, 2, 1)} <= legal
    assert sell(y, 2, 0) not in legal
    assert SELL_JOKERS not in legal
    T.play(st, sell(x, 4, 1))
    finish(st)
    assert me(st)["money"] == m0 + 6
    assert holding(st)[TYPES[y]] == 1 and holding(st)["joker"] == 0


def test_R105_seat_chooses_which_tokens_to_keep():
    """R-105: the seat chooses which tokens to sell and which to keep. From 3 identical + joker it
    may sell a pair and keep the third token and the joker, then (same visit) sell those as a
    joker-assisted pair: $2 + $2."""
    st, h = reach(S_triple_joker, False, "S_triple_joker")
    x = _real_type(h)
    m0 = me(st)["money"]
    visit_market(st, False, sell(x, 2, 0))
    # mid-visit no snapshot is possible (S-MIDTURN): the legal sets show what was kept, namely
    # exactly one real token and the joker (a joker-assisted pair and nothing else).
    assert sell_ids(st) == {sell(x, 2, 1)}
    T.play(st, sell(x, 2, 1))
    finish(st)
    assert me(st)["money"] == m0 + 4
    assert sum(holding(st).values()) == 0


def test_R105_several_sets_in_one_visit_and_a_sold_type_is_gone():
    """R-105/R-104: any number of sets may be sold in one visit: two pairs of different types give
    $2 each; after one pair is sold its type has no set left."""
    st, h = reach(S_two_pairs, False, "S_two_pairs")
    xs = [i for i, t in enumerate(TYPES) if h[t] == 2]
    m0 = me(st)["money"]
    visit_market(st, False)
    assert sell_ids(st) == {sell(xs[0], 2, 0), sell(xs[1], 2, 0)}
    T.play(st, sell(xs[0], 2, 0))
    assert sell_ids(st) == {sell(xs[1], 2, 0)}
    T.play(st, sell(xs[1], 2, 0))
    assert sell_ids(st) == set()
    finish(st)
    assert me(st)["money"] == m0 + 4


# --------------------------------------------------------------------------- R-104 mixing


def test_R104_sales_and_purchases_in_any_order_in_one_visit():
    """R-104: buy food, sell a pair, buy a saw, sell the other pair, buy a saw, all in one visit:
    money net +1 (-1 +2 -1 +2 -1), 2 saws, 1 food."""
    st, h = reach(S_two_pairs, False, "S_two_pairs")
    xs = [i for i, t in enumerate(TYPES) if h[t] == 2]
    m0 = me(st)["money"]
    visit_market(
        st,
        False,
        BUY_FOOD,
        sell(xs[0], 2, 0),
        BUY_SAW,
        sell(xs[1], 2, 0),
        BUY_SAW,
    )
    finish(st)
    seat = me(st)
    assert seat["money"] == m0 + 1
    assert seat["equipment"]["saw"] == 2 and seat["food"] == 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_zero_money_with_a_sellable_set_enters_and_buys_with_proceeds(joinery):
    """R-104/R-040 (spec example): P0 at $0 with both loans used cannot enter the Market with
    nothing to sell, but once it holds a pair it may: inside, no purchase is legal until it sells
    the pair for $2, and the proceeds then buy two saws in the same visit."""
    s = T.broke_p0(joinery)
    assert H.MOVE_TO(market(joinery)) not in s.legal_actions()
    s = broke_with("pair", joinery)
    seat = me(s)
    assert seat["money"] == 0 and seat["loans"] == 2
    assert H.MOVE_TO(market(joinery)) in s.legal_actions()
    T.play(s, H.MOVE_TO(market(joinery)))
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal and H.TAKE_LOAN not in legal
    (sale,) = sell_ids(s)
    T.play(s, sale)
    legal = set(s.legal_actions())
    assert BUY_SAW in legal and BUY_FOOD in legal
    T.play(s, BUY_SAW, BUY_SAW)
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal
    finish(s)
    seat = me(s)
    assert seat["money"] == 0 and seat["equipment"]["saw"] == 2


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_zero_money_with_a_single_token_cannot_enter(joinery):
    """R-104/R-105: at $0 with both loans used, one craftwork token is not 'something it can
    sell' (no single-token sale), so the Market is not a legal destination."""
    s = broke_with("single", joinery)
    seat = me(s)
    assert seat["money"] == 0 and seat["loans"] == 2
    assert sum(seat["craftwork"].values()) == 1
    assert H.MOVE_TO(market(joinery)) not in s.legal_actions()


# --------------------------------------------------------------------------- outside the Market


def test_R105_no_sell_action_outside_the_market():
    """R-105/R-104: holding a sellable pair, no SELL_SET/SELL_SET_JOKERS is legal at a move node,
    during a Bearers visit, or at any later node of the round (wood phases)."""
    st, h = reach(S_pair, False, "S_pair")
    assert T.at_move_node(st)
    assert sell_ids(st) == set()
    visit_locs = [
        loc
        for loc in T.move_locs(st)
        if T.kind_of(False, loc) in ("sawyers", "woodcutters", "bearers", "fodder", "tasks")
    ]
    assert visit_locs, "seed leaves no hiring location ahead of seat 0"
    T.play(st, H.MOVE_TO(visit_locs[0]))
    assert sell_ids(st) == set()
    T.play(st, next(a for a in st.legal_actions() if a != H.TAKE_LOAN))
    assert sell_ids(st) == set()
    finish(st)
    rng = random.Random(0)
    rnd = T.snap(st)["round"]
    seen_phases: set[str] = set()
    for _ in range(5000):
        if st.is_terminal():
            break
        if st.is_chance_node():
            st.apply_action(H.sample_chance(st, rng))
            continue
        ph = H.phase_of(st)
        seen_phases.add(ph)
        if ph == "TR" and T.snap(st)["round"] != rnd:
            break
        assert sell_ids(st) == set(), f"SELL legal in {ph}"
        st.apply_action(R.default_action(R.Ctx(st, rnd, ph, None, rng)))
    assert "W1" in seen_phases


# --------------------------------------------------------------------------- public area


def test_R042_R006_craftwork_area_is_public():
    """R-042/R-006/R-028: a craftwork token taken from a spot lands in the seat's craftwork area
    face up: the other seat's observation shows seat 0's craftwork counts. (Reads the observer's
    `P0 ... craft a,b,c,d,e` field, order board, shingle, stake, reed, joker.)"""
    import re

    st, h = reach(S_pair_joker, False, "S_pair_joker")
    obs = st.observation_string(1)
    m = re.search(r"P0 [^|]*? craft (\d),(\d),(\d),(\d),(\d)", obs)
    assert m is not None, "observer lacks a per-seat craft field"
    assert [int(g) for g in m.groups()] == [h[k] for k in CRAFT]
