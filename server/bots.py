"""Bot seats: a registry of seat type -> Bot. Later phases register heuristic/MCTS here."""

from __future__ import annotations

import copy
import random

from lignum.bots.az.seat import AZSeat
from lignum.bots.base import Bot, RandomBot, bot_candidates
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.mcts import ISMCTSBot
from lignum.bots.strategist import StrategistBot

__all__ = [
    "BOTS",
    "HUMAN",
    "SEAT_TYPE_PATTERN",
    "Bot",
    "RandomBot",
    "bot_candidates",
    "bot_rng",
    "get_bot",
    "is_valid_seat_type",
    "parse_bot_spec",
]

# Heuristic-policy rollouts cut off after this many plies and scored by the value function; random
# rollouts never reach a solvent winter and were much weaker (docs/bot-tournament.md).
ROLLOUT_DEPTH = 40

# MCTS bots carry a per-move wall-clock cap (seconds); at the cap they play the most-visited
# action so far, or the heuristic move if no simulation finished.
BOTS: dict[str, Bot] = {
    "random": RandomBot(),
    "heuristic": HeuristicBot(),
    "heuristic-v1": HeuristicBot(profile="heuristic-v1"),  # frozen Phase 6 weights (D35)
    "heuristic-v2": HeuristicBot(profile="heuristic-v2"),  # working Phase 7 policy (D36)
    "heuristic-v3": HeuristicBot(profile="heuristic-v3"),  # not adopted (D38)
    "heuristic-v4": HeuristicBot(profile="heuristic-v4"),  # Phase 7 unit 1g working profile (D39)
    "heuristic-v5": HeuristicBot(profile="heuristic-v5"),  # v4 + fitted value (unit 3b)
    "heuristic-v6": HeuristicBot(profile="heuristic-v6"),  # v4 + own-turn solver (unit 5b)
    "heuristic-v7": HeuristicBot(profile="heuristic-v7"),  # v6 + long-term task planner (unit 6)
    # Plan-driven scripted policy distilled from the rules and Opus game 0 (docs/STRATEGIST.md).
    "strategist": StrategistBot(),
    # Plan-level search over AlphaZero-style search on a strategist-primed net (docs/AZ.md);
    # 2 players on the joinery side, the strategist otherwise.
    "az": AZSeat(),
    "mcts": ISMCTSBot(
        simulations=1000, time_budget=10.0, rollout="heuristic", rollout_depth=ROLLOUT_DEPTH
    ),
    "mcts-fast": ISMCTSBot(
        simulations=60, time_budget=2.0, rollout="heuristic", rollout_depth=ROLLOUT_DEPTH
    ),
}

HUMAN = "human"
# Keep in sync with the seat types accepted by is_valid_seat_type().
SEAT_TYPE_PATTERN = (
    r"^(human|random|heuristic|heuristic-v1|heuristic-v2|heuristic-v3|heuristic-v4|heuristic-v5|heuristic-v6|heuristic-v7"
    r"|strategist|az|mcts|mcts-fast)$"
)


def is_valid_seat_type(seat_type: str) -> bool:
    return seat_type == HUMAN or seat_type in BOTS


def get_bot(seat_type: str) -> Bot:
    """Resolve a bot seat type to a Bot (KeyError if unknown)."""
    return BOTS[seat_type]


def parse_bot_spec(spec: str, time_cap: bool = True) -> Bot:
    """Tournament/CLI seat strings: a registered kind, or ``mcts:SIMS[:ROLLOUT[:DEPTH]]`` (e.g.
    ``mcts:200`` or ``mcts:100:heuristic:30``; ROLLOUT random|heuristic, DEPTH int or ``none``).
    Not accepted by the server (is_valid_seat_type: registered kinds only). ValueError if bad.
    ``time_cap=False`` drops the wall-clock cap of MCTS seats (sim count only), so results do not
    depend on CPU load; the registered ``BOTS`` used for live play are never changed."""
    if spec in BOTS:
        bot = BOTS[spec]
        if not time_cap and isinstance(bot, ISMCTSBot):
            return _uncapped(bot)
        return bot
    kind, _, rest = spec.partition(":")
    parts = rest.split(":") if rest else []
    if kind in ("mcts-fast", "mcts-solver") and len(parts) == 1 and parts[0].isdigit():
        if int(parts[0]) < 1:
            raise ValueError(f"unknown bot {spec!r}")
        return mcts_fast(int(parts[0]), time_cap, solver=kind == "mcts-solver")
    if spec == "mcts-solver":
        return mcts_fast(60, time_cap, solver=True)
    if kind != "mcts" or not 1 <= len(parts) <= 3 or not parts[0].isdigit() or int(parts[0]) < 1:
        raise ValueError(f"unknown bot {spec!r}")
    rollout = parts[1] if len(parts) > 1 else "random"
    if rollout not in ("random", "heuristic"):
        raise ValueError(f"bad rollout in {spec!r}")
    depth: int | None = 15
    if len(parts) > 2:
        if parts[2] == "none":
            depth = None
        elif parts[2].isdigit():
            depth = int(parts[2])
        else:
            raise ValueError(f"bad depth in {spec!r}")
    return ISMCTSBot(
        simulations=int(parts[0]),
        time_budget=10.0 if time_cap else None,
        rollout=rollout,  # type: ignore[arg-type]
        rollout_depth=depth,
    )


# Solver settings of the rollout policy of ``mcts-solver`` (full v6: beam 8, node_cap 150).
SOLVER_ROLLOUT = {"beam": 3, "node_cap": 40}


def mcts_fast(sims: int, time_cap: bool = True, solver: bool = False) -> ISMCTSBot:
    """``mcts-fast`` settings at ``sims`` simulations; ``solver`` adds the unit 5c knobs: v6 policy
    in rollouts (cheaper solver) and as the tree prior. Tournament/CLI only (``mcts-solver[:SIMS]``,
    ``mcts-fast:SIMS``); not a server seat until unit 6."""
    extra: dict[str, object] = (
        dict(
            policy_profile="heuristic-v6",
            solver_rollout=True,
            solver_tree=True,
            rollout_solver=SOLVER_ROLLOUT,
        )
        if solver
        else {}
    )
    return ISMCTSBot(
        simulations=sims,
        time_budget=2.0 if time_cap else None,
        rollout="heuristic",
        rollout_depth=ROLLOUT_DEPTH,
        **extra,  # type: ignore[arg-type]
    )


def _uncapped(bot: ISMCTSBot) -> ISMCTSBot:
    """A copy of ``bot`` with no time budget (the search object holds only settings, no
    per-search state, so a shallow copy is safe)."""
    clone = copy.copy(bot)
    clone.time_budget = None
    return clone


def bot_rng(seed: int, history_length: int, salt: str = "") -> random.Random:
    """Reproducible from (seed, secret salt, position in history); distinct from chance RNG."""
    return random.Random(
        f"{seed}:{salt}:bot:{history_length}" if salt else f"{seed}:bot:{history_length}"
    )
