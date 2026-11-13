"""Random-game statistics over the parameter grid (PLAN.md section 6 item 3).

    uv run python -m tools.sim_stats --games 200 [--players 2 3] [--seed S] [--jobs K]
                                     [--invariants] [--json PATH] [--violations PATH]

Plays ``--games`` uniformly random games per configuration (all 24 combinations of players, path
side, returns mode and winter mode unless ``--players`` narrows it). Game seeds derive from
``--seed``, so results do not depend on ``--jobs``. With ``--invariants`` the invariant checker
runs after every action; the first offending action history is written to ``--violations``.
Exit code 1 if any violation was found, else 0.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from lignum.invariants import check_invariants
from tools.sim_common import (
    COMBOS,
    PHASE4_ACTIONS,
    Combo,
    action_counts,
    combo_id,
    combo_params,
    load,
    random_playout,
)

Result = dict[str, Any]


def game_seed(base: int, combo_index: int, i: int) -> int:
    return base + 1_000_003 * combo_index + i


class _Violation(Exception):
    """Raised inside the playout to stop at the first violation."""


def play_one(task: tuple[int, int, int, bool]) -> Result:
    """Play one game (combo index into COMBOS, game index, base seed, check invariants)."""
    ci, i, base, check = task
    game = load(COMBOS[ci])
    seed = game_seed(base, ci, i)
    result: Result = {"combo": ci, "seed": seed, "violations": []}

    def step(state: Any) -> None:
        found = check_invariants(state)
        if found:
            result["violations"] = found
            result["history"] = [int(a) for a in state.history()]
            raise _Violation

    try:
        state: Any = random_playout(game, seed, step if check else None)
    except _Violation:
        return result
    result.update(
        steps=sum(1 for pa in state.full_history() if pa.player >= 0),
        loans=int(sum(state.loans)),
        dollars=[int(x) for x in state.final],
        returns=[float(r) for r in state.returns()],
        actions=dict(action_counts(state)),
    )
    return result


def summarize(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"min": 0, "mean": 0, "max": 0, "stdev": 0}
    return {
        "min": min(xs),
        "mean": statistics.fmean(xs),
        "max": max(xs),
        "stdev": statistics.pstdev(xs),
    }


def report(results: list[Result], combos: list[int], invariants: bool = False) -> dict[str, Any]:
    ok = [r for r in results if "steps" in r]
    bad = [r for r in results if r["violations"]]
    by_players: dict[str, Any] = {}
    for n in sorted({COMBOS[c][0] for c in combos}):
        rs = [r for r in ok if COMBOS[r["combo"]][0] == n]
        dollars = [d for r in rs for d in r["dollars"]]
        loans = Counter(r["loans"] for r in rs)
        winners: Counter[str] = Counter()
        for r in rs:
            top = max(r["dollars"])  # R-084: ties are by final dollars, not clipped returns
            leaders = [s for s, x in enumerate(r["dollars"]) if x == top]
            winners["tie" if len(leaders) > 1 else f"P{leaders[0]}"] += 1
        by_players[str(n)] = {
            "games": len(rs),
            "dollars": summarize(dollars),
            "steps": summarize([r["steps"] for r in rs]),
            "loans_mean": statistics.fmean([r["loans"] for r in rs]) if rs else 0,
            "loans_distribution": {str(k): v for k, v in sorted(loans.items())},
            "winners": dict(sorted(winners.items())),
            "tie_rate": winners["tie"] / len(rs) if rs else 0,
        }
    coverage: Counter[str] = Counter()
    for r in ok:
        for name, n in r["actions"].items():
            coverage[name] += n
    return {
        "action_coverage": {k: coverage[k] for k in PHASE4_ACTIONS},
        "games": len(results),
        "configurations": len(combos),
        "invariants_checked": invariants,
        "violations": len(bad),
        "by_players": by_players,
    }


def print_report(rep: dict[str, Any], elapsed: float, out: Any = sys.stdout) -> None:

    def p(text: str = "") -> None:
        print(text, file=out)

    p(f"games: {rep['games']} over {rep['configurations']} configurations")
    p(f"invariants checked: {'yes' if rep['invariants_checked'] else 'no (--invariants off)'}")
    p(f"invariant violations: {rep['violations']}")
    for n, d in rep["by_players"].items():
        dl, st = d["dollars"], d["steps"]
        p(f"\n{n} players ({d['games']} games)")
        p(
            f"  final dollars: min {dl['min']:.0f} mean {dl['mean']:.2f} max {dl['max']:.0f}"
            f" stdev {dl['stdev']:.2f}"
        )
        p(f"  decision steps: min {st['min']:.0f} mean {st['mean']:.1f} max {st['max']:.0f}")
        p(f"  loans per game: mean {d['loans_mean']:.2f} distribution {d['loans_distribution']}")
        p(f"  winners: {d['winners']} (tie rate {d['tie_rate']:.1%})")
    cov = rep["action_coverage"]
    p(f"\nPhase 4 action counts: {cov}")
    p(f"never played: {[k for k, v in cov.items() if v == 0] or 'none'}")
    if elapsed > 0:
        p(f"\n{rep['games'] / elapsed:.1f} games/s ({elapsed:.1f}s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Random-game statistics.")
    parser.add_argument("--games", type=int, default=100, help="games per configuration")
    parser.add_argument("--players", type=int, nargs="+", choices=(2, 3, 4), default=[2, 3, 4])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--invariants", action="store_true", help="check invariants every action")
    parser.add_argument("--json", type=Path, help="also write the report here")
    parser.add_argument("--violations", type=Path, default=Path("sim_violation.json"))
    args = parser.parse_args(argv)

    combos = [i for i, c in enumerate(COMBOS) if c[0] in args.players]
    tasks = [(ci, i, args.seed, args.invariants) for ci in combos for i in range(args.games)]
    start = time.perf_counter()
    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            results = pool.map(play_one, tasks, chunksize=max(1, len(tasks) // (args.jobs * 8)))
    else:
        results = [play_one(t) for t in tasks]
    elapsed = time.perf_counter() - start

    rep = report(results, combos, args.invariants)
    first = next((r for r in results if r["violations"]), None)
    if first is not None:
        combo: Combo = COMBOS[int(first["combo"])]
        args.violations.write_text(
            json.dumps(
                {
                    "game": "lignum",
                    "params": combo_params(combo),
                    "config": combo_id(combo),
                    "seed": first["seed"],
                    "violations": first["violations"],
                    "history": first["history"],
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        rep["first_violation_file"] = str(args.violations)
    print_report(rep, elapsed)
    if first is not None:
        print(f"first violation history saved to {args.violations}")
    if args.json:
        args.json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    return 1 if first is not None else 0


if __name__ == "__main__":
    sys.exit(main())
