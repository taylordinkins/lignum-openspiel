"""Self-play tuning of the strategist's weights (a simple evolution strategy, CMA-lite).

    uv run python -m tools.tune_strategist --iters 20 --pop 8 --games 120 --procs 12 \
        --opponents strategist,heuristic-v6 --out data/bots/strategist_tuned.json

Each candidate is a multiplicative perturbation of the current mean weights (log-normal, step
``--sigma``). Fitness is the candidate's mean final dollars over ``--games`` games split across
the opponents, seats rotated, with common random numbers (the same seeds for every candidate in an
iteration), minus a small penalty on the opponents' dollars when ``--margin`` > 0. The mean moves
to the fitness-weighted average of the best half (in log space), so it can resume from ``--init``.
The best weights seen are written to ``--out`` (JSON: weights and fitness history); load them with
``StrategistBot(weights=json.load(...)["weights"])`` or the ``strategist-tuned`` seat.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from multiprocessing import Pool
from typing import Any

import pyspiel

import lignum.game  # noqa: F401  # pyright: ignore[reportUnusedImport]  (registers the game)
from lignum.bots.strategist import DEFAULT_WEIGHTS, StrategistBot
from lignum.game import LignumState

# Weights that are probabilities or exponents stay in (0, 1].
_UNIT = {k for k in DEFAULT_WEIGHTS if k.startswith("keep_")} | {"area_contest", "contest_clearing"}


def _make(name: str, weights: dict[str, float] | None) -> Any:
    if name == "strategist":
        return StrategistBot(weights=weights)
    from server.bots import get_bot

    return get_bot(name)


def play_one(
    args: tuple[dict[str, float], str, dict[str, float] | None, int, int],
) -> tuple[float, float]:
    """One 2-player game: candidate weights vs opponent; returns (candidate $, opponent $)."""
    cand_w, opp_name, opp_w, seed, seat = args
    cand = StrategistBot(weights=cand_w)
    opp = _make(opp_name, opp_w)
    bots = [cand, opp] if seat == 0 else [opp, cand]
    game = pyspiel.load_game("python_lignum", {"players": 2})
    rng = random.Random(seed)
    st = game.new_initial_state()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            a = rng.choices([x for x, _ in outs], [p for _, p in outs])[0]
        else:
            a = bots[st.current_player()].choose(st, rng)
        st.apply_action(a)
    assert isinstance(st, LignumState)
    return float(st.final[seat]), float(st.final[1 - seat])


def evaluate(
    pool: Any,
    weights: list[dict[str, float]],
    opponents: list[str],
    base: dict[str, float],
    games: int,
    seed0: int,
    margin: float,
) -> list[float]:
    jobs: list[tuple[dict[str, float], str, dict[str, float] | None, int, int]] = []
    for w in weights:
        for g in range(games):
            opp = opponents[g % len(opponents)]
            jobs.append((w, opp, base if opp == "strategist" else None, seed0 + g, g % 2))
    res = pool.map(play_one, jobs, chunksize=4)
    out: list[float] = []
    for i in range(len(weights)):
        chunk = res[i * games : (i + 1) * games]
        mine = statistics.mean(r[0] for r in chunk)
        theirs = statistics.mean(r[1] for r in chunk)
        out.append(mine - margin * theirs)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--pop", type=int, default=8)
    ap.add_argument("--games", type=int, default=120)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--opponents", default="strategist,heuristic-v6")
    ap.add_argument("--keys", default="", help="comma list of weights to tune (default: all)")
    ap.add_argument("--init", default="", help="JSON file with starting weights")
    ap.add_argument("--out", default="data/bots/strategist_tuned.json")
    ap.add_argument("--seed", type=int, default=5000)
    args = ap.parse_args()

    mean = dict(DEFAULT_WEIGHTS)
    if args.init:
        with open(args.init) as f:
            mean.update(json.load(f)["weights"])
    keys = [k for k in (args.keys.split(",") if args.keys else mean) if k]
    opponents = args.opponents.split(",")
    rng = random.Random(args.seed)
    history: list[dict[str, Any]] = []
    best_w, best_f = dict(mean), -math.inf
    with Pool(args.procs) as pool:
        for it in range(args.iters):
            seed0 = args.seed + 1000 * it
            cands = [dict(mean)]
            for _ in range(args.pop - 1):
                w = dict(mean)
                for k in keys:
                    v = mean[k] * math.exp(rng.gauss(0, args.sigma))
                    w[k] = min(v, 1.0) if k in _UNIT else v
                cands.append(w)
            fit = evaluate(pool, cands, opponents, mean, args.games, seed0, args.margin)
            order = sorted(range(len(cands)), key=lambda i: -fit[i])
            elite = order[: max(2, len(cands) // 2)]
            ranks = [math.log(len(elite) + 0.5) - math.log(r + 1) for r in range(len(elite))]
            tot = sum(ranks)
            new = dict(mean)
            for k in keys:
                new[k] = math.exp(
                    sum(ranks[r] * math.log(cands[i][k]) for r, i in enumerate(elite)) / tot
                )
                if k in _UNIT:
                    new[k] = min(new[k], 1.0)
            if fit[order[0]] > best_f:
                best_f, best_w = fit[order[0]], cands[order[0]]
            history.append({"iter": it, "mean_fit": fit[0], "best_fit": fit[order[0]]})
            print(
                f"iter {it}: incumbent {fit[0]:.2f} best {fit[order[0]]:.2f} (seeds {seed0}+)",
                flush=True,
            )
            mean = new
            with open(args.out, "w") as f:
                json.dump(
                    {"weights": best_w, "fitness": best_f, "mean": mean, "history": history},
                    f,
                    indent=1,
                    sort_keys=True,
                )


if __name__ == "__main__":
    main()
