"""Server random bots take TAKE_LOAN only when forced or when it enables a purchase.

Bot-only policy (playtest 20261106T213551-e2d38f): the engine and humans keep TAKE_LOAN legal
at almost every node (R-076); the bot candidate set drops it unless it is the sole action, the
winter shortfall (R-073), or it newly enables another action.
"""

from __future__ import annotations

import random
from typing import Any

from server.adapters import default_adapters
from server.bots import RandomBot, bot_candidates
from server.sessions import CHANCE, SessionStore
from tests import harness as H
from tests.support import winter as V

LOAN = H.TAKE_LOAN
SF = 21  # lignum.game.PHASE_SF


def _enables(state: Any) -> bool:
    after = state.clone()
    after.apply_action(LOAN)
    return bool(set(after.legal_actions()) - {LOAN} - set(state.legal_actions()))


def _walk(seed: int) -> Any:
    """Yield (state, candidates) at every decision node of one filtered-random 2-seat game."""
    rng = random.Random(seed)
    s = H.load_game(players=2).new_initial_state()
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        c = bot_candidates(s)
        yield s, c
        s.apply_action(rng.choice(c))


def _find(want_loan: bool) -> Any:
    for seed in range(40):
        for s, c in _walk(seed):
            legal = s.legal_actions()
            if LOAN in legal and len(legal) > 1 and s.phase != SF and (LOAN in c) == want_loan:
                return s.clone()
    raise AssertionError("no such node found")


def test_loan_is_candidate_when_it_enables_a_purchase() -> None:
    s = _find(True)
    assert _enables(s)
    assert LOAN in bot_candidates(s)
    assert set(bot_candidates(s)) == set(s.legal_actions())


def test_loan_not_candidate_when_nothing_is_newly_enabled() -> None:
    s = _find(False)
    assert not _enables(s)
    c = bot_candidates(s)
    assert LOAN not in c and c
    assert set(c) == set(s.legal_actions()) - {LOAN}


def test_shortfall_loan_still_taken_by_bot() -> None:
    s = V.to_shortfall(None, seat=0)
    assert LOAN in s.legal_actions()
    assert LOAN in bot_candidates(s)
    if s.legal_actions() == [LOAN]:
        assert RandomBot().choose(s, random.Random(1)) == LOAN


def test_sole_legal_loan_is_candidate() -> None:
    for seed in range(40):
        for s, _ in _walk(seed):
            if s.legal_actions() == [LOAN]:
                assert bot_candidates(s) == [LOAN]
                return
    # The shortfall forced loan is the sole-action case.
    s = V.to_shortfall(None, seat=0)
    assert s.legal_actions() == [LOAN] and bot_candidates(s) == [LOAN]


def test_choice_is_deterministic_for_same_rng_key() -> None:
    s = _find(False)
    bot = RandomBot()
    assert bot.choose(s, random.Random("k")) == bot.choose(s, random.Random("k"))


def test_real_game_bots_take_no_pointless_loans_and_human_keeps_loan() -> None:
    store = SessionStore(default_adapters(), inline_bots=True)
    sess = store.create("lignum", {"num_players": 4}, ["human", "random", "random", "random"], 11)
    rng = random.Random(5)
    human_saw_loan = False
    for _ in range(150):
        if sess.state.is_terminal():
            break
        legal = sess.state.legal_actions()
        human_saw_loan |= LOAN in legal
        pick = [a for a in legal if a != LOAN] or legal
        sess.apply(rng.choice(pick))
    assert human_saw_loan  # humans still see TAKE_LOAN as legal
    state = sess.adapter.initial_state(sess.game, sess.scenario)
    bot_actions = 0
    for a, actor in zip(sess.history, sess.actors, strict=True):
        if actor != CHANCE and sess.seats[actor] != "human":
            bot_actions += 1
            if a == LOAN:
                legal = state.legal_actions()
                assert len(legal) == 1 or state.phase == SF or _enables(state)
        state.apply_action(a)
    assert bot_actions > 50
