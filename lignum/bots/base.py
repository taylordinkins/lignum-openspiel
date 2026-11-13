"""Bot interface, the legal-candidate filter and the random bot (shared by server and tools)."""

from __future__ import annotations

import random
from typing import Protocol

import pyspiel

from lignum import actions as A
from lignum.game import PHASE_SF, LignumState


class Bot(Protocol):
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        """Return a legal action id for the current player of `state`.

        Bots get the same information a player has: they must not read other seats' unrevealed
        picks from `state` (the server passes a full-information clone). Phase 6 IS-MCTS needs a
        resampler for hidden picks; see docs/OPENSPIEL_NOTES.md.
        """
        ...


def bot_candidates(state: pyspiel.State) -> list[int]:
    """Actions a random bot may pick (humans keep every legal action; the engine is unchanged).

    In Lignum TAKE_LOAN is legal almost everywhere (R-076), so uniform play takes pointless
    loans. A bot may take one only when it is the sole legal action, in the winter shortfall
    (R-073), or when it newly enables some other action (a paid action it could not afford).
    """
    legal = list(state.legal_actions())
    if (
        A.TAKE_LOAN not in legal
        or len(legal) == 1
        or not isinstance(state, LignumState)
        or state.phase == PHASE_SF
    ):
        return legal
    after = state.search_clone()
    after.apply_action(A.TAKE_LOAN)
    enabled: set[int] = set()
    if not (after.is_terminal() or after.is_chance_node()):
        enabled = set(after.legal_actions()) - {A.TAKE_LOAN}
    if enabled - set(legal):
        return legal
    return [a for a in legal if a != A.TAKE_LOAN]


class RandomBot:
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        return rng.choice(bot_candidates(state))
