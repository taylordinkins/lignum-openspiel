"""Collect bot-game training data for the value fit (Phase 7 unit 2; format: docs/BOT_DATA.md).

    uv run python -m tools.collect_games --matchups "heuristic-v4,heuristic-v4:300" \\
        "heuristic-v4,heuristic-v2:100" "heuristic-v4,mcts-fast:20" --workers 6

A matchup is ``SEAT0,SEAT1:COUNT`` (seat strings as tools/tournament.py accepts them, including
profile overrides ``heuristic-v4:max_sawyers=2;saw_target=3``; the trailing ``:COUNT`` is required).
Games take consecutive seeds from ``--seed-start`` across the matchups in order; the seats are
swapped on odd seeds. Seeds 101-199 are reserved for held-out evaluation and refused. One game is
one ``<seed>.jsonl.gz`` file (header, one row per recorded decision, footer); existing files are
skipped, so a run can be resumed. Collecting only reads the state: a game is played exactly as
``tools.tournament.play_game_record`` plays it for the same seed string (``str(seed)``).
Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyspiel

from lignum.bots.features import FEATURE_NAMES, features
from lignum.bots.fitted import ROOT
from lignum.bots.value import value_parts
from lignum.bots.weights import profile_path, value_weights
from tools.ledger import COMPONENTS, Ledger
from tools.replay import Replay, ReplayError, load_game
from tools.tournament import make_bot, play_game_record, split_bots, winner_shares

SCHEMA_VERSION = 1
RESERVED_SEEDS = range(101, 200)  # held-out evaluation seeds (PLAN.md Phase 7)
DEFAULT_OUT = Path("data/bot_games")
DEFAULT_VALUE_PROFILE = "heuristic-v4"
PLAYERS = 2

PART_NAMES = (
    "money",
    "loan",
    "wood",
    "joinery",
    "tasks",
    "office",
    "craft",
    "plans",
    "buildings",
    "income",
    "winter",
)


@dataclass(frozen=True)
class Job:
    index: int  # position in the schedule
    seed: int
    matchup: int
    seats: tuple[str, str]  # seat strings by seat (already rotated)
    path: str


def parse_matchup(text: str) -> tuple[list[str], int]:
    """``'heuristic-v4,mcts-fast:20'`` -> (['heuristic-v4', 'mcts-fast'], 20). ValueError if bad."""
    m = re.fullmatch(r"(.*):(\d+)", text.strip())
    if m is None:
        raise ValueError(f"matchup {text!r} needs a trailing :COUNT")
    seats, count = split_bots(m.group(1)), int(m.group(2))
    if len(seats) != PLAYERS:
        raise ValueError(f"matchup {text!r} needs exactly {PLAYERS} seats, got {len(seats)}")
    if count < 1:
        raise ValueError(f"matchup {text!r}: count must be >= 1")
    return seats, count


def schedule(
    matchups: Sequence[str], seed_start: int, out: Path, games_cap: int | None = None
) -> list[Job]:
    """Jobs in order: matchup after matchup, consecutive seeds, seats swapped on odd seeds.
    ValueError on a bad matchup or a seed in the reserved held-out range."""
    jobs: list[Job] = []
    seed = seed_start
    for mi, text in enumerate(matchups):
        seats, count = parse_matchup(text)
        for spec in seats:
            make_bot(spec)  # ValueError on an unknown bot
        if games_cap is not None:
            count = min(count, games_cap)
        for _ in range(count):
            if seed in RESERVED_SEEDS:
                raise ValueError(
                    f"seed {seed} is reserved for held-out evaluation "
                    f"({RESERVED_SEEDS.start}-{RESERVED_SEEDS.stop - 1})"
                )
            order = (seats[0], seats[1]) if seed % 2 == 0 else (seats[1], seats[0])
            jobs.append(Job(len(jobs), seed, mi, order, str(out / f"{seed}.jsonl.gz")))
            seed += 1
    return jobs


def _parts(state: Any, seat: int, vw: Any) -> list[float | int]:
    parts = value_parts(state, seat, vw)
    return [_num(parts[k]) for k in PART_NAMES]


def _num(x: float) -> float | int:
    return int(x) if float(x).is_integer() else round(float(x), 4)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def bot_hashes(seats: Sequence[str]) -> dict[str, str]:
    """Short sha256 of each heuristic profile's YAML used by the seat strings."""
    out: dict[str, str] = {}
    for spec in seats:
        name = spec.partition(":")[0]
        if name.startswith("heuristic"):
            out[name] = sha256(profile_path(name))
            fit = value_weights(name).get("value_fit")
            if fit is not None:
                fp = Path(fit)
                out[f"{name}:value_fit"] = sha256(fp if fp.is_absolute() else ROOT / fp)
    return out


def run_game(job: Job, every: int, value_profile: str, time_cap: bool) -> dict[str, Any]:
    """Play one game and write its file (atomically). Returns a manifest entry."""
    t0 = time.perf_counter()
    game = load_game(
        Replay(
            game="lignum",
            params={
                "players": PLAYERS,
                "joinery": True,
                "returns": "win_loss",
                "easy_winter": False,
            },
        )
    )
    vw = value_weights(value_profile)
    seed_str = str(job.seed)
    rows: list[str] = []
    counters = {"decision": 0, "recorded": 0}
    obs_time = [0.0]

    def observer(state: Any, ledger: Ledger, seat: int, step: int) -> None:
        if len(state.legal_actions()) < 2:  # forced move: nothing was decided
            return
        idx = counters["decision"]
        counters["decision"] += 1
        if idx % every:
            return
        o0 = time.perf_counter()
        counters["recorded"] += 1
        rows.append(
            json.dumps(
                {
                    "type": "row",
                    "d": idx,
                    "step": step,
                    "round": state.round,
                    "phase": state.phase,
                    "p": seat,
                    "f": [[_num(x) for x in features(state, s, vw)] for s in range(PLAYERS)],
                    "v": [_parts(state, s, vw) for s in range(PLAYERS)],
                    "acc": [[ledger.parts[s][c] for c in COMPONENTS] for s in range(PLAYERS)],
                },
                separators=(",", ":"),
            )
        )
        obs_time[0] += time.perf_counter() - o0

    rec = play_game_record(game, list(job.seats), seed_str, time_cap, observer)
    header = {
        "type": "header",
        "schema": SCHEMA_VERSION,
        "seed": job.seed,
        "matchup": job.matchup,
        "seats": list(job.seats),
        "every": every,
        "value_profile": value_profile,
        "feature_names": FEATURE_NAMES,
        "part_names": PART_NAMES,
        "components": COMPONENTS,
    }
    shares = winner_shares(rec.returns)
    footer = {
        "type": "footer",
        "seed": job.seed,
        "decisions": counters["decision"],
        "rows": counters["recorded"],
        "actions": len(rec.history),
        "returns": rec.returns,
        "final": rec.final,
        "winner": [i for i, s in enumerate(shares) if s > 0],
        "breakdown": [[b[c] for c in COMPONENTS] for b in rec.breakdown],
    }
    path = Path(job.path)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        f.write(json.dumps(header, separators=(",", ":")) + "\n")
        for r in rows:
            f.write(r + "\n")
        f.write(json.dumps(footer, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return {
        "seed": job.seed,
        "matchup": job.matchup,
        "seats": list(job.seats),
        "file": path.name,
        "bytes": path.stat().st_size,
        "rows": counters["recorded"],
        "decisions": counters["decision"],
        "seconds": round(time.perf_counter() - t0, 3),
        "observer_seconds": round(obs_time[0], 3),
        "final": rec.final,
    }


def _worker(args: tuple[Job, int, str, bool]) -> dict[str, Any]:
    return run_game(*args)


def git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def collect(
    matchups: Sequence[str],
    out: Path,
    seed_start: int = 200,
    every: int = 1,
    workers: int = 6,
    games_cap: int | None = None,
    value_profile: str = DEFAULT_VALUE_PROFILE,
    time_cap: bool = True,
) -> dict[str, Any]:
    """Play the schedule (skipping games whose file exists), write the manifest, return it."""
    if every < 1:
        raise ValueError("--every must be >= 1")
    jobs = schedule(matchups, seed_start, out, games_cap)
    value_weights(value_profile)  # FileNotFoundError for an unknown profile
    out.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not Path(j.path).exists()]
    t0 = time.perf_counter()
    args = [(j, every, value_profile, time_cap) for j in todo]
    if workers <= 1 or len(args) <= 1:
        done = [_worker(a) for a in args]
    else:
        with multiprocessing.Pool(min(workers, len(args))) as pool:
            done = list(pool.imap_unordered(_worker, args))
    done.sort(key=lambda e: e["seed"])
    seats = sorted({s for j in jobs for s in j.seats})
    manifest = {
        "schema": SCHEMA_VERSION,
        "git_sha": git_sha(),
        "matchups": list(matchups),
        "seed_start": seed_start,
        "games_cap": games_cap,
        "every": every,
        "value_profile": value_profile,
        "time_cap": time_cap,
        "bot_yaml_sha256": bot_hashes(seats),
        "games_scheduled": len(jobs),
        "games_new": len(done),
        "games_skipped": len(jobs) - len(done),
        "seconds": round(time.perf_counter() - t0, 3),
        "games": done,
    }
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    return manifest


def read_game(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """(header, rows, footer) of a game file."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        recs = [json.loads(line) for line in f]
    return recs[0], recs[1:-1], recs[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect bot-game training data.")
    parser.add_argument("--matchups", nargs="+", required=True, help="'SEAT0,SEAT1:COUNT' ...")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed-start", type=int, default=200)
    parser.add_argument("--every", type=int, default=1, help="record every Nth decision")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--games", type=int, default=None, help="cap games per matchup (smoke)")
    parser.add_argument("--value-profile", default=DEFAULT_VALUE_PROFILE)
    parser.add_argument("--no-time-cap", action="store_true", help="drop MCTS wall-clock caps")
    parser.add_argument("--dry-run", action="store_true", help="print the schedule and exit")
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            for j in schedule(args.matchups, args.seed_start, args.out, args.games):
                state = "exists" if Path(j.path).exists() else "todo"
                print(f"seed {j.seed} {list(j.seats)} {state}")
            return 0
        m = collect(
            args.matchups,
            args.out,
            args.seed_start,
            args.every,
            args.workers,
            args.games,
            args.value_profile,
            not args.no_time_cap,
        )
    except (ValueError, ReplayError, pyspiel.SpielError, FileNotFoundError) as error:
        print(f"collect_games: {error}", file=sys.stderr)
        return 2
    print(
        f"{m['games_new']} new, {m['games_skipped']} skipped games in {m['seconds']}s -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
