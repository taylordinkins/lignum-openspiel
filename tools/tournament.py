"""Bot tournament: head-to-head or round-robin, seat rotation, fixed seeds, win rate with CI.

    uv run python -m tools.tournament --players 2 --games 20 --seed 1 --bots heuristic,random
    uv run python -m tools.tournament --players 2 --games 10 --bots random,heuristic,mcts-fast \
        --mode round-robin --json out.json

Bots are the kinds registered in server/bots.py. Head-to-head needs exactly --players bots; game g
seats bot ``(seat + g) % players``, so each bot plays each seat equally often when --games is a
multiple of --players. Round-robin plays one head-to-head block (--games games) for every
combination of --players distinct list entries. Game g derives its chance and bot RNGs from
the string ``"{seed}:{g}"`` (round-robin prefixes the lineup), so a run is deterministic.

Winner: the seat(s) with the highest engine return. Tied top seats split one win equally (a
2-way tie is half a win each). Win rate is wins/games (fractional wins allowed) with a 95% Wilson
interval. Pairwise table (round-robin): for each pair of bots sharing a game, the row bot scores 1
if its return is higher, 0.5 if equal, 0 if lower.

Reproducibility: MCTS seats (`mcts`, `mcts-fast`, `mcts:SIMS`) carry wall-clock caps, so their moves
depend on CPU load. `--no-time-cap` drops the caps (sim counts only); then a run is exactly
repeatable from its seed. Reports also give each bot's mean final dollars split by component
(wood sales, tasks, joinery, Office, craftwork, winter, loans, other; `tools/ledger.py`) and
ms/move (mean and p90 of the time to choose an action, over every decision incl. forced ones).
Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TextIO, cast

import pyspiel

from lignum.bots.heuristic import HeuristicBot
from lignum.bots.weights import load_profile
from server.bots import BOTS, bot_rng, parse_bot_spec
from tools.ledger import COMPONENTS, OTHER, Ledger
from tools.replay import Replay, ReplayError, load_game
from tools.wood_flow import aggregate, format_flow

Z95 = 1.959963984540054
MODES = ("head-to-head", "round-robin")


def wilson(wins: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion (wins may be fractional)."""
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


_BOT_CACHE: dict[tuple[str, bool], Any] = {}


def _thaw(x: Any) -> Any:
    if isinstance(x, Mapping):
        return {k: _thaw(v) for k, v in cast("Mapping[str, Any]", x).items()}
    if isinstance(x, tuple):
        return [_thaw(v) for v in cast("tuple[Any, ...]", x)]
    return x


def _literal(text: str) -> int | float | str:
    for conv in (int, float):
        try:
            return conv(text)
        except ValueError:
            pass
    return text


def parse_overrides(spec: str) -> tuple[str, dict[str, int | float | str]]:
    """Split ``heuristic-v4:max_sawyers=2;saw_target=3`` into the profile name and its profile-key
    overrides (``,`` also separates pairs; dotted keys reach nested sections, ``value.heat_w=2``).
    A spec without ``:`` returns (spec, {}). ValueError on a malformed pair."""
    name, _, rest = spec.partition(":")
    out: dict[str, int | float | str] = {}
    for pair in rest.replace(",", ";").split(";") if rest else []:
        key, eq, val = pair.partition("=")
        if not eq or not key.strip() or not val.strip():
            raise ValueError(f"bad override {pair!r} in {spec!r} (want key=value)")
        out[key.strip()] = _literal(val.strip())
    return name, out


def make_bot(spec: str, time_cap: bool = True) -> Any:
    """``parse_bot_spec`` plus profile-key overrides for the heuristic-* profiles (not mcts:...)."""
    name, over = parse_overrides(spec) if spec.startswith("heuristic") else (spec, {})
    if not over:
        return parse_bot_spec(spec, time_cap)
    if name != "heuristic" and not name.startswith("heuristic-") or name not in BOTS:
        raise ValueError(f"overrides need a heuristic profile, got {spec!r}")
    weights: dict[str, Any] = _thaw(load_profile(name))
    for key, val in over.items():
        node: Any = weights
        *path, leaf = key.split(".")
        for part in path:
            if not isinstance(node, dict) or part not in node:
                raise ValueError(f"unknown profile key {key!r} in {spec!r}")
            node = cast("dict[str, Any]", node)[part]
        if not isinstance(node, dict) or leaf not in node:
            raise ValueError(f"unknown profile key {key!r} in {spec!r}")
        node[leaf] = val
    return HeuristicBot(weights=weights)


def split_bots(text: str) -> list[str]:
    """Split a ``--bots`` list on commas; a piece with ``=`` and no ``:`` continues the previous
    seat's override list (``heuristic-v4:max_sawyers=2,saw_target=3,heuristic-v2``)."""
    out: list[str] = []
    for piece in (p.strip() for p in text.split(",")):
        if not piece:
            continue
        if "=" in piece and ":" not in piece and out and ":" in out[-1]:
            out[-1] += ";" + piece
        else:
            out.append(piece)
    return out


def _bot(spec: str, time_cap: bool = True) -> Any:
    if (spec, time_cap) not in _BOT_CACHE:
        _BOT_CACHE[spec, time_cap] = make_bot(spec, time_cap)
    return _BOT_CACHE[spec, time_cap]


@dataclass
class GameRecord:
    returns: list[float]
    final: list[float]  # each seat's final dollars (R-083)
    breakdown: list[dict[str, int]]  # per seat: component -> dollars, sums to ``final``
    history: list[int]  # every applied action, chance outcomes included
    move_ms: list[list[float]]  # per seat: wall time (ms) of each bot decision
    detail: list[dict[str, dict[str, int]]] = field(default_factory=lambda: [])  # Ledger.detail()
    funnels: list[dict[str, int]] = field(default_factory=lambda: [])  # Ledger.funnels()
    # Ledger.completion_rounds(): per seat, the round of each completed task
    completions: list[list[int]] = field(default_factory=lambda: [])
    wood: list[dict[str, Any]] = field(default_factory=lambda: [])  # Ledger.wood_flow()


def play_game(game: pyspiel.Game, seats: list[str], seed: str) -> list[float]:
    """Play one game headlessly; seats[i] is the bot kind at seat i. Returns engine returns."""
    return play_game_scores(game, seats, seed)[0]


def play_game_scores(
    game: pyspiel.Game, seats: list[str], seed: str, time_cap: bool = True
) -> tuple[list[float], list[float]]:
    """Like play_game, also returning each seat's final dollars (R-083)."""
    rec = play_game_record(game, seats, seed, time_cap)
    return rec.returns, rec.final


def play_game_record(
    game: pyspiel.Game,
    seats: list[str],
    seed: str,
    time_cap: bool = True,
    observer: Callable[[Any, Ledger, int, int], None] | None = None,
) -> GameRecord:
    """Play one game headlessly and record dollars by component, history and decision times.
    ``observer(state, ledger, seat, step)`` is called read-only before every bot decision
    (tools/collect_games.py); it must not mutate the state or draw from the game's RNGs."""
    chance_rng = random.Random(f"{seed}:chance")
    state: Any = game.new_initial_state()
    ledger = Ledger(state)
    history: list[int] = []
    move_ms: list[list[float]] = [[] for _ in seats]
    steps = 0
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            action = chance_rng.choices(actions, weights=probs)[0]
        else:
            seat: int = state.current_player()
            bot = _bot(seats[seat], time_cap)
            if observer is not None:
                observer(state, ledger, seat, steps)
            clone = state.clone()
            rng = bot_rng(hash_seed(seed), steps)
            t0 = time.perf_counter()
            action = bot.choose(clone, rng)
            move_ms[seat].append((time.perf_counter() - t0) * 1000)
        ledger.apply(action)
        history.append(action)
        steps += 1
    return GameRecord(
        list(state.returns()),
        [float(x) for x in state.final],
        ledger.breakdown(),
        history,
        move_ms,
        ledger.detail(),
        ledger.funnels(),
        ledger.completion_rounds(),
        ledger.wood_flow(),
    )


def hash_seed(seed: str) -> int:
    return random.Random(seed).getrandbits(48)


def winner_shares(returns: list[float]) -> list[float]:
    """One win split equally among the seats tied for the highest return."""
    top = max(returns)
    tied = [i for i, r in enumerate(returns) if r == top]
    return [1 / len(tied) if i in tied else 0.0 for i in range(len(returns))]


@dataclass
class Stats:
    games: int = 0
    wins: float = 0.0
    returns: float = 0.0
    dollars: list[float] = field(default_factory=lambda: [])
    margins: list[float] = field(default_factory=lambda: [])  # own dollars - mean of others
    pair: dict[str, list[float]] = field(default_factory=lambda: {})  # opponent -> [score, games]
    parts: dict[str, list[float]] = field(default_factory=lambda: {c: [] for c in COMPONENTS})
    move_ms: list[float] = field(default_factory=lambda: [])
    detail: dict[str, dict[str, list[float]]] = field(default_factory=lambda: {})
    funnels: dict[str, list[float]] = field(default_factory=lambda: {})
    completions: list[int] = field(default_factory=lambda: [])  # round of every completed task
    wood: list[dict[str, Any]] = field(default_factory=lambda: [])  # one Ledger.wood_flow() entry


def p90(values: list[float]) -> float:
    """90th percentile, nearest rank."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def run_block(
    game: pyspiel.Game,
    lineup: list[str],
    games: int,
    seed: int,
    stats: dict[str, Stats],
    label: str = "",
    out: TextIO | None = None,
    time_cap: bool = True,
) -> None:
    n = len(lineup)
    for g in range(games):
        seats = [lineup[(s + g) % n] for s in range(n)]
        rec = play_game_record(game, seats, f"{seed}:{label}{g}", time_cap)
        returns, final = rec.returns, rec.final
        shares = winner_shares(returns)
        for s, kind in enumerate(seats):
            st = stats.setdefault(kind, Stats())
            st.games += 1
            st.wins += shares[s]
            st.returns += returns[s]
            st.dollars.append(final[s])
            for comp in COMPONENTS:
                st.parts[comp].append(rec.breakdown[s][comp])
            st.move_ms.extend(rec.move_ms[s])
            for group, items in rec.detail[s].items():
                for key, value in items.items():
                    st.detail.setdefault(group, {}).setdefault(key, []).append(value)
            st.completions.extend(rec.completions[s])
            st.wood.append(rec.wood[s])
            for key, value in rec.funnels[s].items():
                st.funnels.setdefault(key, []).append(value)
            st.margins.append(final[s] - (sum(final) - final[s]) / (n - 1))
            for t, other in enumerate(seats):
                if t == s:
                    continue
                cell = st.pair.setdefault(other, [0.0, 0])
                cell[0] += (
                    1.0 if returns[s] > returns[t] else 0.5 if returns[s] == returns[t] else 0.0
                )
                cell[1] += 1
        if out is not None:
            print(f"game {label}{g}: seats={seats} returns={returns} dollars={final}", file=out)


def summarize(stats: dict[str, Stats], timings: bool = False) -> dict[str, Any]:
    bots: dict[str, Any] = {}
    for kind, st in sorted(stats.items()):
        lo, hi = wilson(st.wins, st.games)
        bots[kind] = {
            "games": st.games,
            "wins": st.wins,
            "win_rate": st.wins / st.games if st.games else 0.0,
            "ci95": [lo, hi],
            "mean_return": st.returns / st.games if st.games else 0.0,
            "mean_dollars": statistics.fmean(st.dollars) if st.dollars else 0.0,
            "median_dollars": statistics.median(st.dollars) if st.dollars else 0.0,
            "mean_margin": statistics.fmean(st.margins) if st.margins else 0.0,
            # mean of each component of the final dollars; the components sum to mean_dollars
            "mean_breakdown": {c: statistics.fmean(v) if v else 0.0 for c, v in st.parts.items()},
            # sub-components: winter and spending groups sum to their parent in mean_breakdown;
            # winter_info is memo (units, forgiven $, forced loans/sales), not part of any sum
            "mean_detail": {
                g: {k: statistics.fmean(v) if v else 0.0 for k, v in items.items()}
                for g, items in st.detail.items()
            },
            "mean_funnel": {k: statistics.fmean(v) if v else 0.0 for k, v in st.funnels.items()},
            # additive: tasks completed per game and the round each was completed in
            # additive: mean wood-flow funnel per game and per round (tools/ledger.py)
            "wood_flow": aggregate(st.wood) if st.wood else {},
            "task_completion": {
                "per_game": len(st.completions) / st.games if st.games else 0.0,
                "mean_round": statistics.fmean(st.completions) if st.completions else 0.0,
                "histogram": {
                    str(r): st.completions.count(r) / st.games for r in sorted(set(st.completions))
                },
            },
        }
        if timings:  # wall-clock numbers vary run to run, so they are opt-in for the API
            bots[kind]["ms_per_move"] = {
                "moves": len(st.move_ms),
                "mean": statistics.fmean(st.move_ms) if st.move_ms else 0.0,
                "p90": p90(st.move_ms),
            }
    pairwise = {
        kind: {o: c[0] / c[1] for o, c in sorted(st.pair.items()) if c[1]}
        for kind, st in sorted(stats.items())
    }
    return {"bots": bots, "pairwise": pairwise}


def run_tournament(
    bots: list[str],
    players: int,
    games: int,
    seed: int,
    mode: str = "head-to-head",
    side: str = "joinery",
    returns: str = "win_loss",
    easy_winter: bool = False,
    out: TextIO | None = None,
    time_cap: bool = True,
    timings: bool = False,
) -> dict[str, Any]:
    if not 2 <= players <= 4:
        raise ValueError("--players must be 2..4")
    if games < 1:
        raise ValueError("--games must be >= 1")
    for b in bots:
        make_bot(b, time_cap)  # ValueError on an unknown bot
    if mode == "head-to-head":
        if len(bots) != players:
            raise ValueError(f"head-to-head needs exactly {players} bots, got {len(bots)}")
        lineups = [bots]
    else:
        if len(bots) < players or len(set(bots)) != len(bots):
            raise ValueError(f"round-robin needs at least {players} distinct bots")
        lineups = [list(c) for c in itertools.combinations(bots, players)]
    game = load_game(
        Replay(
            game="lignum",
            params={
                "players": players,
                "joinery": side == "joinery",
                "returns": returns,
                "easy_winter": easy_winter,
            },
        )
    )
    stats: dict[str, Stats] = {}
    for lineup in lineups:
        label = "-".join(lineup) + ":" if mode == "round-robin" else ""
        run_block(game, lineup, games, seed, stats, label, out, time_cap)
    result = summarize(stats, timings)
    result.update(
        mode=mode,
        players=players,
        games_per_block=games,
        seed=seed,
        lineups=lineups,
        time_cap=time_cap,
    )
    return result


def format_report(result: dict[str, Any]) -> str:
    lines = [
        f"{result['mode']}, {result['players']} players, {result['games_per_block']} games/block, "
        f"seed {result['seed']}",
        f"{'bot':<12}{'games':>6}{'wins':>8}{'win rate':>10}{'95% CI':>20}{'mean ret':>10}"
        f"{'mean $':>9}{'med $':>8}{'margin':>9}",
    ]
    for kind, b in result["bots"].items():
        lo, hi = b["ci95"]
        lines.append(
            f"{kind:<12}{b['games']:>6}{b['wins']:>8.1f}{b['win_rate']:>10.3f}"
            f"{f'[{lo:.3f}, {hi:.3f}]':>20}{b['mean_return']:>10.3f}"
            f"{b['mean_dollars']:>9.1f}{b['median_dollars']:>8.1f}{b['mean_margin']:>9.1f}"
        )
    lines.append("\nmean final $ by component (loans = proceeds - repayment; other = start money,")
    lines.append("spending on workers/fodder/plans/etc. and small incomes; sums to mean $):")
    lines.append(
        f"{'bot':<12}{'wood':>8}{'tasks':>8}{'joinery':>9}{'office':>8}{'craft':>8}"
        f"{'winter':>8}{'loans':>8}{'other':>8}{'total':>8}"
    )
    for kind, b in result["bots"].items():
        c = b["mean_breakdown"]
        loans = c["loan_proceeds"] + c["loan_repayment"]
        other = sum(c[k] for k in OTHER)
        lines.append(
            f"{kind:<12}{c['wood_sales']:>8.1f}{c['tasks']:>8.1f}{c['joinery']:>9.1f}"
            f"{c['office']:>8.1f}{c['craftwork']:>8.1f}{c['winter']:>8.1f}{loans:>8.1f}"
            f"{other:>8.1f}{b['mean_dollars']:>8.1f}"
        )
    lines.extend(format_detail(result["bots"]))
    for kind, b in result["bots"].items():
        if b.get("wood_flow"):
            lines.append("")
            lines.extend(format_flow(kind, b["wood_flow"]))
    if all("ms_per_move" in b for b in result["bots"].values()):
        lines.append("\nms per move (wall time to choose, every decision):")
        lines.append(f"{'bot':<12}{'moves':>8}{'mean':>10}{'p90':>10}")
        for kind, b in result["bots"].items():
            m = b["ms_per_move"]
            lines.append(f"{kind:<12}{m['moves']:>8}{m['mean']:>10.2f}{m['p90']:>10.2f}")
    if result["mode"] == "round-robin":
        kinds = list(result["bots"])
        lines.append("\npairwise score of row vs column (1 win, 0.5 tie):")
        lines.append(f"{'':<12}" + "".join(f"{k:>12}" for k in kinds))
        for k in kinds:
            cells = result["pairwise"][k]
            lines.append(
                f"{k:<12}"
                + "".join(f"{cells[o]:>12.3f}" if o in cells else f"{'-':>12}" for o in kinds)
            )
    return "\n".join(lines)


def format_detail(bots: dict[str, Any]) -> list[str]:
    """Text tables for the winter/spending sub-components and the task/joinery funnels, one row
    per bot (or per seat label), means per game."""
    lines: list[str] = []
    cols = [
        ("winter", "feed_shortfall", "feed$"),
        ("winter", "heat_shortfall", "heat$"),
        ("spending", "hire_bearer", "bear"),
        ("spending", "hire_woodcutter", "wcut"),
        ("spending", "hire_sawyer", "sawy"),
        ("spending", "fodder", "fodder"),
        ("spending", "saws", "saws"),
        ("spending", "planned_work", "plans"),
        ("spending", "food", "food"),
        ("spending", "tasks_bought", "tasks"),
        ("spending", "cut_token", "token"),
        ("spending", "other", "other"),
    ]
    lines.append("\nmean winter and spending sub-components ($; each group sums to its parent):")
    lines.append(f"{'bot':<12}" + "".join(f"{c[2]:>8}" for c in cols))
    for kind, b in bots.items():
        d = b.get("mean_detail", {})
        lines.append(
            f"{kind:<12}" + "".join(f"{d.get(g, {}).get(k, 0.0):>8.2f}" for g, k, _ in cols)
        )
    info = [
        ("feed_missing_units", "feedMiss"),
        ("heat_missing_units", "heatMiss"),
        ("forgiven_dollars", "forgiven"),
        ("forced_loans", "fLoans"),
        ("forced_sales", "fSales"),
    ]
    lines.append("winter memo (units / count per game; forgiven $ is not money):")
    lines.append(f"{'bot':<12}" + "".join(f"{c[1]:>10}" for c in info))
    for kind, b in bots.items():
        w = b.get("mean_detail", {}).get("winter_info", {})
        lines.append(f"{kind:<12}" + "".join(f"{w.get(k, 0.0):>10.2f}" for k, _ in info))
    fcols = [
        ("tasks_taken", "taken"),
        ("task_pieces", "pieces"),
        ("tasks_completed", "done"),
        ("tasks_incomplete", "incompl"),
        ("incomplete_slots_filled", "incFill"),
        ("incomplete_slots_total", "incSlots"),
        ("joiners_hired", "joiners"),
        ("joinery_placed", "jPlaced"),
        ("joinery_sold", "jSold"),
    ]
    lines.append("funnels (mean per game): tasks taken -> pieces on tasks -> completed; joinery")
    lines.append(f"{'bot':<12}" + "".join(f"{c[1]:>9}" for c in fcols))
    for kind, b in bots.items():
        f = b.get("mean_funnel", {})
        lines.append(f"{kind:<12}" + "".join(f"{f.get(k, 0.0):>9.2f}" for k, _ in fcols))
    lines.append("tasks completed per game, mean completion round, and per game by round:")
    lines.append(f"{'bot':<12}{'per game':>9}{'mean rnd':>9}  rounds")
    for kind, b in bots.items():
        tc = b.get("task_completion", {"per_game": 0.0, "mean_round": 0.0, "histogram": {}})
        hist = " ".join(f"r{r}:{n:.2f}" for r, n in tc["histogram"].items())
        lines.append(f"{kind:<12}{tc['per_game']:>9.2f}{tc['mean_round']:>9.2f}  {hist}")
    return lines


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(description="Run a Lignum bot tournament.")
    parser.add_argument("--players", type=int, default=2)
    parser.add_argument("--games", type=int, default=10, help="games per lineup")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bots", default="heuristic,random", help="comma-separated bot kinds")
    parser.add_argument("--mode", choices=MODES, default="head-to-head")
    parser.add_argument("--side", choices=("joinery", "base"), default="joinery")
    parser.add_argument("--returns", choices=("win_loss", "margin"), default="win_loss")
    parser.add_argument("--easy-winter", action="store_true")
    parser.add_argument(
        "--no-time-cap",
        action="store_true",
        help="drop the wall-clock cap of mcts, mcts-fast and mcts:SIMS seats (sim count only), "
        "so a run is exactly reproducible from --seed whatever the CPU load",
    )
    parser.add_argument("--json", default=None, help="write the full result to this file")
    parser.add_argument("--verbose", action="store_true", help="print every game")
    args = parser.parse_args(argv)
    try:
        result = run_tournament(
            split_bots(args.bots),
            args.players,
            args.games,
            args.seed,
            args.mode,
            args.side,
            args.returns,
            args.easy_winter,
            out if args.verbose else None,
            time_cap=not args.no_time_cap,
            timings=True,
        )
    except (ValueError, ReplayError, pyspiel.SpielError) as error:
        print(f"tournament: {error}", file=sys.stderr)
        return 2
    print(format_report(result), file=out)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
