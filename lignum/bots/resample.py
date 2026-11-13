"""Hidden-pick resampler for IS-MCTS (Phase 6 unit 5; R-029, R-038).

Cutting-area picks are made in seat order and stay hidden until the whole run is done (R-038).
For ``player`` the unrevealed picks of the other seats are unknown, so a sample redraws each one
uniformly over the six areas (R-038: any area may be chosen). Everything else, including the
player's own pick and the public pick log, is kept, so the information-state string is unchanged.
"""

from __future__ import annotations

import random

from lignum.game import NUM_AREAS, LignumState


def resample(state: LignumState, player: int, rng: random.Random | None = None) -> LignumState:
    """Implements R-029: a clone with other seats' unrevealed picks redrawn uniformly.

    Usable as an ``ISMCTSBot.set_resampler`` callback (``cb(state, player)``). The draw reads
    only which seats are hidden, never the true hidden picks.
    """
    rng = rng if rng is not None else random.Random()
    sample = state.search_clone()
    if sample.pk:
        sample.pk = tuple(
            area if seat == player else rng.randrange(NUM_AREAS)
            for seat, area in enumerate(sample.pk)
        )
    return sample
