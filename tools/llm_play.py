"""Let an LLM play Lignum against a heuristic bot through a stateless CLI (one process per command).

    uv run python -m tools.llm_play start  --run opus1 --game 0     # new game
    uv run python -m tools.llm_play show   --run opus1 --game 0     # current decision again
    uv run python -m tools.llm_play act    --run opus1 --game 0 12 --note "why" # play action id(s)
    uv run python -m tools.llm_play baseline --run opus1 --games 25 # v6 mirror, same seeds
    uv run python -m tools.llm_play report --run opus1              # running performance table

Layout (``data/llm_games/<run>/``, git-ignored):
    g00/session.json      seed, LLM seat, full action history (chance and bot moves included)
    g00/trajectory.jsonl  one row per LLM decision: observation, legal actions, chosen id, note
    results.jsonl         one line per finished game (returns, final $, breakdown, funnels)
    baseline.jsonl        heuristic-v6 vs heuristic-v6 on the same seeds and seats
    playbook.md           lessons the LLM carries between games (written by the LLM)

Game g: seed ``SEED_BASE + g``, the LLM sits in seat ``g % 2``, 2 players, joinery side, win_loss
returns, standard winter, opponent ``heuristic-v6`` (``start --opponent SPEC`` sets another bot
seat for that game; it is stored in session.json). Chance and bot moves are derived per step from
the seed, so a session is rebuilt exactly by replaying its history. The LLM sees only
``observation_string(seat)`` (the engine hides the opponent's unrevealed pick); forced single-action
nodes are applied automatically. Exit codes: 0 ok, 2 bad input or illegal action.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, TextIO

import pyspiel

from lignum import actions as A
from lignum.game import PHASE_PK
from server.adapters.lignum import LignumAdapter
from server.bots import bot_rng
from tools.ledger import Ledger
from tools.replay import Replay, load_game
from tools.tournament import _bot, hash_seed, play_game_record, wilson  # pyright: ignore

ROOT = Path("data/llm_games")
SEED_BASE = 400  # 101-199 are held-out; 200-299 collect_games; 400+ is for LLM runs
OPPONENT = "heuristic-v6"
ADAPTER = LignumAdapter()
PARAMS = {"players": 2, "joinery": True, "returns": "win_loss", "easy_winter": False}


def seed_of(game_no: int) -> int:
    return SEED_BASE + game_no


def llm_seat(game_no: int) -> int:
    return game_no % 2


def new_game() -> pyspiel.Game:
    return load_game(Replay(game="lignum", params=dict(PARAMS)))


def gdir(run: str, game_no: int) -> Path:
    return ROOT / run / f"g{game_no:02d}"


def _chance(state: Any, seed: int, step: int) -> int:
    actions, probs = zip(*state.chance_outcomes(), strict=True)
    return random.Random(f"{seed}:chance:{step}").choices(actions, weights=probs)[0]


def _hidden(state: Any, seat: int, action: int) -> bool:
    """R-038: another seat's pick stays hidden until the reveal."""
    return state.phase == PHASE_PK and A.decode(action).name == "PICK_AREA"


def advance(
    state: Any, history: list[int], seed: int, seat: int, log: list[str], opponent: str = OPPONENT
) -> None:
    """Apply chance nodes, bot moves and the LLM's forced moves until the LLM must choose."""
    bot = _bot(opponent, False)
    while not state.is_terminal():
        step = len(history)
        if state.is_chance_node():
            action = _chance(state, seed, step)
        else:
            who = state.current_player()
            if who == seat:
                if len(state.legal_actions()) > 1:
                    return
                action = state.legal_actions()[0]
                log.append(f"(forced) {state.action_to_string(who, action)}")
            else:
                action = bot.choose(state.clone(), bot_rng(hash_seed(str(seed)), step))
                text = (
                    "picked a cutting area (hidden)"
                    if _hidden(state, who, action)
                    else (state.action_to_string(who, action))
                )
                log.append(f"P{who}: {text}")
        state.apply_action(action)
        history.append(action)


def load_session(run: str, game_no: int) -> tuple[Any, dict[str, Any], list[str]]:
    sess = json.loads((gdir(run, game_no) / "session.json").read_text())
    state: Any = new_game().new_initial_state()
    for a in sess["history"]:
        state.apply_action(a)
    return state, sess, []


def save_session(run: str, game_no: int, sess: dict[str, Any]) -> None:
    (gdir(run, game_no) / "session.json").write_text(json.dumps(sess))


def render(state: Any, sess: dict[str, Any], log: list[str], out: TextIO) -> None:
    seat = sess["seat"]
    if log:
        print("--- since your last action ---", file=out)
        for line in log[-60:]:
            print(line, file=out)
    if state.is_terminal():
        print(f"\n=== GAME OVER ===\n{state.observation_string(seat)}", file=out)
        print(
            f"returns (you are P{seat}): {state.returns()}  final $: {list(state.final)}", file=out
        )
        return
    view = ADAPTER.view(state, seat)
    view.pop("legal_actions", None)
    if len(sess["history"]) > 60:  # static tables were shown in the first view of the game
        for key in ("equip_slots", "kind_names", "craft_order", "loan_repayment"):
            view.pop(key, None)
    print("\nSTATE (json, your seat's view):", file=out)
    print(json.dumps(view, separators=(",", ":")), file=out)
    print(f"You are P{seat}. Legal actions:", file=out)
    for a in state.legal_actions():
        print(f"  {a:4d}  {state.action_to_string(seat, a)}", file=out)


def finish(run: str, game_no: int, state: Any, sess: dict[str, Any]) -> dict[str, Any]:
    """Replay the history through a Ledger, write results.jsonl once per game."""
    fresh: Any = new_game().new_initial_state()
    ledger = Ledger(fresh)
    for a in sess["history"]:
        ledger.apply(a)
    seat = sess["seat"]
    traj = gdir(run, game_no) / "trajectory.jsonl"
    decisions = sum(1 for _ in traj.open()) if traj.exists() else 0
    row = {
        "game": game_no,
        "seed": sess["seed"],
        "seat": seat,
        "opponent": sess.get("opponent", OPPONENT),
        "returns": list(state.returns()),
        "final": [float(x) for x in state.final],
        "win": 1.0
        if state.returns()[seat] > state.returns()[1 - seat]
        else (0.5 if state.returns()[seat] == state.returns()[1 - seat] else 0.0),
        "breakdown": ledger.breakdown(),
        "funnels": ledger.funnels(),
        "completions": ledger.completion_rounds(),
        "decisions": decisions,
        "history_len": len(sess["history"]),
    }
    path = ROOT / run / "results.jsonl"
    done = [json.loads(x)["game"] for x in path.open()] if path.exists() else []
    if game_no not in done:
        with path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    return row


def cmd_start(args: argparse.Namespace, out: TextIO) -> int:
    d = gdir(args.run, args.game)
    if (d / "session.json").exists():
        print(f"game {args.game} of run {args.run} already started; use show", file=sys.stderr)
        return 2
    d.mkdir(parents=True, exist_ok=True)
    seed = seed_of(args.game)
    sess: dict[str, Any] = {
        "seed": seed,
        "seat": llm_seat(args.game),
        "opponent": args.opponent,
        "history": [],
    }
    state: Any = new_game().new_initial_state()
    log: list[str] = []
    advance(state, sess["history"], seed, sess["seat"], log, args.opponent)
    save_session(args.run, args.game, sess)
    render(state, sess, log, out)
    return 0


def cmd_show(args: argparse.Namespace, out: TextIO) -> int:
    state, sess, log = load_session(args.run, args.game)
    render(state, sess, log, out)
    return 0


def cmd_act(args: argparse.Namespace, out: TextIO) -> int:
    state, sess, log = load_session(args.run, args.game)
    seat, history, seed = sess["seat"], sess["history"], sess["seed"]
    traj = gdir(args.run, args.game) / "trajectory.jsonl"
    queue: list[tuple[str, str]] = [(str(i), "") for i in args.ids]
    for item in (args.plan or "").replace("\n", ";").split(";"):
        text, _, why = item.partition("#")
        if text.strip():
            queue.append((text.strip(), why.strip()))
    applied = 0
    start_round = state.round
    stop = ""
    while queue:
        if state.is_terminal() or state.current_player() != seat:
            stop = "the turn passed to the opponent"
            break
        if state.round != start_round:
            stop = "a new round started (new chance draws are visible)"
            break
        token, why = queue.pop(0)
        legal = state.legal_actions()
        names = {state.action_to_string(seat, x).replace(" ", ""): x for x in legal}
        a = int(token) if token.lstrip("-").isdigit() else names.get(token.replace(" ", ""), -1)
        if a not in legal:
            stop = f"{token!r} is not legal now; legal: " + ", ".join(
                f"{x}={state.action_to_string(seat, x)}" for x in legal
            )
            queue.insert(0, (token, why))
            break
        row = {
            "step": len(history),
            "round": state.round,
            "phase": state.phase,
            "seat": seat,
            "obs": state.observation_string(seat),
            "legal": {str(x): state.action_to_string(seat, x) for x in legal},
            "chosen": a,
            "name": state.action_to_string(seat, a),
            "note": why or (args.note if applied == 0 else ""),
        }
        with traj.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        state.apply_action(a)
        history.append(a)
        applied += 1
        advance(state, history, seed, seat, log, sess.get("opponent", OPPONENT))
    save_session(args.run, args.game, sess)
    if applied == 0:
        print(f"nothing played: {stop}", file=sys.stderr)
        return 2
    if queue:
        print(f"(played {applied}; stopped with {len(queue)} unplayed: {stop})", file=out)
    render(state, sess, log, out)
    if state.is_terminal():
        row = finish(args.run, args.game, state, sess)
        print(f"\nRESULT game {args.game}: win={row['win']} you ${row['final'][seat]:.0f} vs "
              f"opp ${row['final'][1 - seat]:.0f}", file=out)  # fmt: skip
    return 0


def cmd_baseline(args: argparse.Namespace, out: TextIO) -> int:
    path = ROOT / args.run / "baseline.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    have: set[int] = {json.loads(x)["game"] for x in path.open()} if path.exists() else set()
    game = new_game()
    for g in range(args.games):
        if g in have:
            continue
        rec = play_game_record(game, [OPPONENT, OPPONENT], f"base{seed_of(g)}", False)
        row = {"game": g, "final": rec.final, "returns": rec.returns,
               "breakdown": rec.breakdown, "funnels": rec.funnels}  # fmt: skip
        with path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    print(f"baseline: {args.games} games in {path}", file=out)
    return 0


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.open()] if path.exists() else []


def cmd_report(args: argparse.Namespace, out: TextIO) -> int:
    rows = sorted(_rows(ROOT / args.run / "results.jsonl"), key=lambda r: r["game"])
    base = {r["game"]: r for r in _rows(ROOT / args.run / "baseline.jsonl")}
    if not rows:
        print("no finished games", file=out)
        return 0
    print(
        "game seat  win  you$ opp$ margin | v6mirror margin(seat-matched) | tasks joinery", file=out
    )
    margins: list[float] = []
    bmargins: list[float] = []
    for r in rows:
        s = r["seat"]
        m = r["final"][s] - r["final"][1 - s]
        margins.append(m)
        b = base.get(r["game"])
        bm = (b["final"][s] - b["final"][1 - s]) if b else float("nan")
        if b:
            bmargins.append(bm)
        fn = r["funnels"][s]
        print(f"{r['game']:4d} P{s}   {r['win']:.1f} {r['final'][s]:5.0f} {r['final'][1-s]:4.0f} "
              f"{m:+6.0f} | {bm:+6.0f} | {fn.get('tasks_completed', fn.get('completed', '?'))}",
              file=out)  # fmt: skip
    n = len(rows)
    wins = sum(r["win"] for r in rows)
    lo, hi = wilson(wins, n)
    print(f"\ngames {n}  win rate {wins / n:.3f} [{lo:.3f}, {hi:.3f}]  "
          f"mean you$ {statistics.mean(r['final'][r['seat']] for r in rows):.1f}  "
          f"mean margin {statistics.mean(margins):+.1f}", file=out)  # fmt: skip
    half = n // 2
    if n >= 4:
        a, b2 = margins[:half], margins[half:]
        wa = sum(r["win"] for r in rows[:half]) / half
        wb = sum(r["win"] for r in rows[half:]) / (n - half)
        print(f"first half: win {wa:.2f} margin {statistics.mean(a):+.1f}   "
              f"second half: win {wb:.2f} margin {statistics.mean(b2):+.1f}", file=out)  # fmt: skip
    if bmargins:
        print(
            f"v6 mirror mean margin on same seeds/seats: {statistics.mean(bmargins):+.1f}", file=out
        )
    comp: dict[str, list[float]] = {}
    for r in rows:
        for k, v in r["breakdown"][r["seat"]].items():
            comp.setdefault(k, []).append(v)
    print("mean $ by component (LLM): " + ", ".join(
        f"{k} {statistics.mean(v):.1f}" for k, v in comp.items() if any(v)), file=out)  # fmt: skip
    return 0


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("start", "show", "act"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--game", type=int, required=True)
        if name == "start":
            s.add_argument(
                "--opponent",
                default=OPPONENT,
                help="bot seat for the other seat (stored in session.json), e.g. strategist, az",
            )
        if name == "act":
            s.add_argument("--note", default="", help="one line of reasoning, saved to trajectory")
            s.add_argument("ids", type=int, nargs="*", help="action ids, played in order")
            s.add_argument(
                "--plan",
                default="",
                help='segment script: "MOVE_TO(14) # why; TAKE_TASK(11); 5" (names or ids, ";" or '
                "newline separated). Stops at the first illegal action, when the turn passes, or "
                "at a round change, and prints why.",
            )
    s = sub.add_parser("baseline")
    s.add_argument("--run", required=True)
    s.add_argument("--games", type=int, default=25)
    s = sub.add_parser("report")
    s.add_argument("--run", required=True)
    args = p.parse_args(argv)
    try:
        return {"start": cmd_start, "show": cmd_show, "act": cmd_act,
                "baseline": cmd_baseline, "report": cmd_report}[args.cmd](args, out)  # fmt: skip
    except (FileNotFoundError, pyspiel.SpielError) as e:
        print(f"llm_play: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
