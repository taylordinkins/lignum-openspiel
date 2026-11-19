"""PPO fine-tuning of the AZ net as a policy on top of the strategist (docs/PPO.md).

    uv run python -m tools.ppo_train run --init it1 --out ppo1 --iters 200
    uv run python -m tools.ppo_train eval --model data/bots/ppo/ppo1.npz --games 200

Each iteration plays ``--games`` games in a worker pool with the current policy sampling at its
strategic decisions (``lignum.bots.ppo.PPOBot``) against a mix of opponents, then runs a few PPO
epochs on the learning seats' decisions on the GPU and exports the net for the next iteration.
Reward: the seat's own final dollars (no discount). Advantages: GAE over the seat's own recorded
decisions with the net's value head. A KL penalty keeps the policy near the initial one (the
strategist plus the primed net). Evaluation plays greedily on seeds 9000+ (never trained on).

2 players, joinery side. Opponent spec ``snap`` is a frozen copy of the policy refreshed every
``--snap-every`` iterations (greedy). Outputs go to ``data/bots/ppo/`` (git-ignored).
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import statistics
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import pyspiel

import lignum.game  # noqa: F401  # pyright: ignore[reportUnusedImport]
from lignum.bots.az.search import is_strategic
from lignum.bots.ppo import DEFAULT_BONUS, PPOBot, Step
from lignum.game import LignumState

VALUE_SCALE = 100.0
LEARNER = "ppo"
_W_ROLLOUT = ["policy"]  # continuation of the learner seat in paired rollouts
_W_PAIR = [0.0, 2.0]  # (probability a recorded decision is paired, proposal temperature)

# ---------------------------------------------------------------------------- workers

_W: dict[str, Any] = {}


def _init(bonus: float) -> None:
    _W.clear()
    _W.update(bonus=bonus, ppo={}, fixed={})


def _ppo(path: str, greedy: bool) -> PPOBot:
    key = (path, os.stat(path).st_mtime_ns, greedy)  # the path is rewritten every iteration
    b = _W["ppo"].get(key)
    if b is None:
        if len(_W["ppo"]) > 6:
            _W["ppo"].clear()
        b = _W["ppo"][key] = PPOBot(path, bonus=_W["bonus"], greedy=greedy)
    return b


def _fixed(spec: str) -> Any:
    b = _W["fixed"].get(spec)
    if b is None:
        if spec == "strategist":
            from lignum.bots.strategist import StrategistBot

            b = StrategistBot()
        else:
            from server.bots import get_bot

            b = get_bot(spec)
        _W["fixed"][spec] = b
    return b


def play_game(job: dict[str, Any]) -> dict[str, Any]:
    """job: lineup, seed, rot, model, snap, train (sample + record the learner seats)."""
    lineup: list[str] = job["lineup"]
    n = len(lineup)
    seats = [lineup[(s + job["rot"]) % n] for s in range(n)]
    train = job["train"]
    bots: list[Any] = []
    for name in seats:
        if name == LEARNER:
            bots.append(_ppo(job["model"], greedy=not train))
        elif name == "snap":
            bots.append(_ppo(job["snap"], greedy=True))
        else:
            bots.append(_fixed(name))
    rec: list[Step] = []
    learners = [b for b, nm in zip(bots, seats, strict=True) if nm == LEARNER]
    for b in learners:
        b.record = rec if train else None
    game = pyspiel.load_game("python_lignum", {"players": n})
    rng = random.Random(job["seed"])
    st = game.new_initial_state()
    assert isinstance(st, LignumState)
    ledger = None
    apply = st.apply_action
    if job.get("ledger"):
        from tools.ledger import Ledger

        ledger = Ledger(st)
        apply = ledger.apply
    pair_p = job.get("pair_p", 0.0) if train else 0.0
    pairs: list[dict[str, Any]] = []
    rbots: list[Any] = []
    if pair_p > 0:
        prop = _ppo(job["model"], greedy=True)
        cont = prop if job.get("rollout", "policy") == "policy" else _fixed("strategist")
        rbots = [cont if nm == LEARNER else b for b, nm in zip(bots, seats, strict=True)]
    try:
        while not st.is_terminal():
            if st.is_chance_node():
                outs = st.chance_outcomes()
                apply(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
                continue
            p = st.current_player()
            if pair_p > 0 and seats[p] == LEARNER and is_strategic(st):
                n0 = len(rec)
                st0 = st.search_clone()
                a = bots[p].choose(st, rng)
                if len(rec) > n0 and rng.random() < pair_p:
                    pairs.append(
                        paired_sample(
                            st0, rec[-1], rbots, rng.randrange(1 << 30), job["pair_temp"], prop
                        )
                    )
                apply(a)
                continue
            apply(bots[p].choose(st, rng))
    finally:
        for b in learners:
            b.record = None
    out: dict[str, Any] = {"seats": seats, "final": list(st.final), "steps": rec, "pairs": pairs}
    if ledger is not None:
        bd = ledger.breakdown()
        fn = ledger.funnels()
        out["parts"] = [{**bd[s], **{f"f_{k}": v for k, v in fn[s].items()}} for s in range(n)]
    return out


def _crn_outcome(st: LignumState, seed: int, k: int) -> int:
    """The k-th chance node's outcome from a uniform keyed by (seed, k): both branches of a
    paired comparison see the same draws wherever their distributions agree."""
    u = random.Random(seed * 7919 + k).random()
    outs = st.chance_outcomes()
    acc = 0.0
    for o, pr in outs:
        acc += pr
        if u < acc:
            return o
    return outs[-1][0]


def rollout(st: LignumState, bots: list[Any], seed: int) -> tuple[int, ...]:
    rng = random.Random(seed)
    k = 0
    while not st.is_terminal():
        if st.is_chance_node():
            st.apply_action(_crn_outcome(st, seed, k))
            k += 1
            continue
        st.apply_action(bots[st.current_player()].choose(st, rng))
    return st.final


def paired_sample(
    st0: LignumState, step: Step, rbots: list[Any], seed: int, temp: float, prop: PPOBot
) -> dict[str, Any]:
    """Advantage of an alternative b over the strategist's move at ``st0``: both played out
    (greedy current policy for the learner, the game's opponents) on common random numbers.
    b is drawn from the policy over the other candidates at temperature ``temp``."""
    me = step.seat
    a_s = step.cands[step.sidx]
    p, _, _ = prop.policy(st0, step.cands, a_s)
    others = [i for i in range(len(step.cands)) if i != step.sidx]
    w = [max(p[i], 1e-12) ** (1.0 / temp) for i in others]
    bi = random.Random(seed).choices(others, w)[0]
    out = []
    for i in (step.sidx, bi):
        s = st0.search_clone()
        s.apply_action(step.cands[i])
        out.append(rollout(s, rbots, seed)[me])
    return {
        "x": step.x,
        "cands": step.cands,
        "sidx": step.sidx,
        "bidx": bi,
        "logp": float(np.log(max(p[bi], 1e-12))),
        "adv": float(out[1] - out[0]),
    }


def _jobs(
    lineups: list[list[str]], games: int, seed: int, model: str, snap: str, train: bool
) -> list[dict[str, Any]]:
    jobs = []
    for li, lineup in enumerate(lineups):
        for g in range(games):
            jobs.append(
                {
                    "lineup": lineup,
                    "seed": seed + g + (li * 100_000 if train else 0),
                    "rot": g % len(lineup),
                    "model": model,
                    "snap": snap,
                    "train": train,
                    "pair_p": _W_PAIR[0],
                    "pair_temp": _W_PAIR[1],
                    "rollout": _W_ROLLOUT[0],
                }
            )
    return jobs


def summarize(results: list[dict[str, Any]], who: str = LEARNER) -> dict[str, dict[str, float]]:
    """Per lineup: mean and se of ``who``'s dollars, the opponents' mean, win rate."""
    per: dict[str, dict[str, list[float]]] = {}
    for r in results:
        key = ",".join(sorted(r["seats"]))
        d = per.setdefault(key, {"me": [], "opp": [], "win": []})
        for s, nm in enumerate(r["seats"]):
            if nm != who:
                continue
            others = [f for t, f in enumerate(r["final"]) if t != s]
            d["me"].append(r["final"][s])
            d["opp"].append(statistics.mean(others))
            d["win"].append(
                1.0 if r["final"][s] > max(others) else 0.5 if r["final"][s] == max(others) else 0.0
            )
    out = {}
    for k, d in per.items():
        m = d["me"]
        out[k] = {
            "n": len(m),
            "me": statistics.mean(m),
            "se": statistics.stdev(m) / math.sqrt(len(m)) if len(m) > 1 else 0.0,
            "opp": statistics.mean(d["opp"]),
            "win": statistics.mean(d["win"]),
        }
    return out


# ---------------------------------------------------------------------------- learner


def batch_arrays(results: list[dict[str, Any]], lam: float) -> dict[str, np.ndarray]:
    """Flatten the learner steps; GAE(lambda) on own dollars, Monte Carlo value targets."""
    xs, cands, sidx, aidx, logp, adv, ret, vt = [], [], [], [], [], [], [], []
    for r in results:
        final = r["final"]
        n = len(final)
        by_seat: dict[int, list[Step]] = {}
        for s in r["steps"]:
            by_seat.setdefault(s.seat, []).append(s)
        for seat, steps in by_seat.items():
            vals = [s.value / VALUE_SCALE for s in steps] + [final[seat] / VALUE_SCALE]
            gae = 0.0
            advs = [0.0] * len(steps)
            for t in range(len(steps) - 1, -1, -1):
                delta = vals[t + 1] - vals[t]
                gae = delta + lam * gae
                advs[t] = gae
            target = [final[(seat + k) % n] / VALUE_SCALE for k in range(n)]
            for t, s in enumerate(steps):
                xs.append(s.x)
                cands.append(s.cands)
                sidx.append(s.sidx)
                aidx.append(s.aidx)
                logp.append(s.logp)
                adv.append(advs[t])
                ret.append(advs[t] + vals[t])
                vt.append(target)
    k = max(len(c) for c in cands)
    cm = np.full((len(cands), k), -1, np.int64)
    for i, c in enumerate(cands):
        cm[i, : len(c)] = c
    return {
        "x": np.stack(xs),
        "cands": cm,
        "sidx": np.array(sidx, np.int64),
        "aidx": np.array(aidx, np.int64),
        "logp": np.array(logp, np.float32),
        "adv": np.array(adv, np.float32),
        "ret": np.array(ret, np.float32),
        "vt": np.array(vt, np.float32),
    }


def pair_arrays(results: list[dict[str, Any]]) -> dict[str, np.ndarray] | None:
    ps = [p for r in results for p in r.get("pairs", [])]
    if not ps:
        return None
    k = max(len(p["cands"]) for p in ps)
    cm = np.full((len(ps), k), -1, np.int64)
    for i, p in enumerate(ps):
        cm[i, : len(p["cands"])] = p["cands"]
    return {
        "x": np.stack([p["x"] for p in ps]),
        "cands": cm,
        "sidx": np.array([p["sidx"] for p in ps], np.int64),
        "bidx": np.array([p["bidx"] for p in ps], np.int64),
        "logp": np.array([p["logp"] for p in ps], np.float32),
        "adv": np.array([p["adv"] for p in ps], np.float32),
    }


class Learner:
    def __init__(self, args: argparse.Namespace) -> None:
        import torch

        from tools.az_train import build_model

        self.torch = torch
        self.args = args
        self.dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        src = Path(args.init_dir) / f"{args.init}.pt"
        ck = torch.load(src, weights_only=False)
        self.ck_meta = {k: ck[k] for k in ("norm_mean", "norm_inv", "width", "blocks")}
        d = len(ck["norm_mean"])
        n_seats = ck["state"]["v2.bias"].shape[0]
        self.model = build_model(d, ck["width"], ck["blocks"], n_seats).to(self.dev)
        self.model.load_state_dict(ck["state"])
        self.ref = copy.deepcopy(self.model).eval()
        for p in self.ref.parameters():
            p.requires_grad_(False)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=args.lr, eps=1e-5)
        self.mean = torch.tensor(ck["norm_mean"], device=self.dev)
        self.inv = torch.tensor(ck["norm_inv"], device=self.dev)
        if args.resume:
            st = torch.load(Path(args.dir) / f"{args.out}.pt", weights_only=False)
            self.model.load_state_dict(st["state"])
            if "opt" in st:
                self.opt.load_state_dict(st["opt"])

    def _logp(self, logits: Any, cm: Any, sidx: Any) -> Any:
        torch = self.torch
        mask = cm >= 0
        g = torch.gather(logits, 1, cm.clamp(min=0))
        g = g + self.args.bonus * torch.nn.functional.one_hot(sidx, g.shape[1]).float()
        g = g.masked_fill(~mask, -1e9)
        return torch.log_softmax(g, 1), mask

    def update(
        self, data: dict[str, np.ndarray], pairs: dict[str, np.ndarray] | None = None
    ) -> dict[str, float]:
        """PPO epochs. Without ``pairs`` the policy samples are the recorded steps with GAE
        advantages (normalised); with ``pairs`` they are the paired alternatives with their
        dollar advantages over the strategist's move (scaled, not centred). The value loss
        always uses the recorded steps."""
        torch = self.torch
        a = self.args
        dev = self.dev
        n = len(data["aidx"])
        if pairs is None:
            adv = data["adv"]
            pol = {**data, "adv": (adv - adv.mean()) / (adv.std() + 1e-8)}
        else:
            adv = pairs["adv"]
            pol = {**pairs, "aidx": pairs["bidx"], "adv": adv / (adv.std() + 1e-8)}
        m = len(pol["aidx"])
        pb = a.batch if pairs is None else max(256, min(a.batch, m // 4))
        stats: dict[str, list[float]] = {
            k: [] for k in ("pl", "vl", "kl_ref", "kl_old", "clip", "ent")
        }
        rng = np.random.default_rng()
        self.model.train()

        def tens(d: dict[str, np.ndarray], key: str, ix: np.ndarray) -> Any:
            return torch.tensor(d[key][ix], device=dev)

        def feats(d: dict[str, np.ndarray], ix: np.ndarray) -> Any:
            x = torch.tensor(d["x"][ix].astype(np.float32), device=dev)
            return torch.clamp((x - self.mean) * self.inv, -5, 5)

        for _ in range(a.epochs):
            order = rng.permutation(m)
            for s in range(0, m, pb):
                ix = order[s : s + pb]
                x = feats(pol, ix)
                cm, sidx = tens(pol, "cands", ix), tens(pol, "sidx", ix)
                aidx, old = tens(pol, "aidx", ix), tens(pol, "logp", ix)
                advb = tens(pol, "adv", ix)
                logits, v = self.model(x)
                logp, mask = self._logp(logits, cm, sidx)
                lp = logp.gather(1, aidx[:, None])[:, 0]
                ratio = torch.exp(lp - old)
                pl = -torch.min(
                    ratio * advb, torch.clamp(ratio, 1 - a.clip, 1 + a.clip) * advb
                ).mean()
                with torch.no_grad():
                    rl, _ = self.ref(x)
                    rlogp, _ = self._logp(rl, cm, sidx)
                p = logp.exp()
                kl_ref = (p * (logp - rlogp)).masked_fill(~mask, 0).sum(1).mean()
                ent = -(p * logp).masked_fill(~mask, 0).sum(1).mean()
                if pairs is not None:  # value minibatch from the recorded steps
                    vix = rng.choice(n, min(n, a.batch), replace=False)
                    _, v = self.model(feats(data, vix))
                else:
                    vix = ix
                vt, ret = tens(data, "vt", vix), tens(data, "ret", vix)
                # value: own head on the GAE return, the others on final dollars
                vl = ((v[:, 0] - ret) ** 2).mean() + ((v[:, 1:] - vt[:, 1:]) ** 2).mean()
                loss = pl + a.vw * vl + a.kl * kl_ref - a.ent * ent
                self.opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), a.max_grad)
                self.opt.step()  # pyright: ignore[reportUnknownMemberType]
                with torch.no_grad():
                    stats["pl"].append(pl.item())
                    stats["vl"].append(vl.item())
                    stats["kl_ref"].append(kl_ref.item())
                    stats["kl_old"].append((old - lp).mean().item())
                    stats["clip"].append(((ratio - 1).abs() > a.clip).float().mean().item())
                    stats["ent"].append(ent.item())
        return {k: float(np.mean(v)) for k, v in stats.items()}

    def export(self, path: Path, with_opt: bool = True) -> None:
        torch = self.torch
        state = {k: v.detach().cpu() for k, v in self.model.state_dict().items()}
        ck: dict[str, Any] = {"state": state, **self.ck_meta}
        if with_opt:
            ck["opt"] = self.opt.state_dict()
        torch.save(ck, path.with_suffix(".pt"))
        arrays = {k: v.numpy() for k, v in state.items()}
        arrays["norm_mean"] = self.ck_meta["norm_mean"]
        arrays["norm_inv"] = self.ck_meta["norm_inv"]
        arrays["meta_blocks"] = np.array([self.ck_meta["blocks"]])
        np.savez(path.with_suffix(".npz"), **arrays)


# ---------------------------------------------------------------------------- commands


def _fmt(summary: dict[str, dict[str, float]]) -> str:
    return " | ".join(
        f"{k}: ${d['me']:.1f}±{d['se']:.1f} opp ${d['opp']:.1f} win {d['win']:.2f}"
        f" (n={int(d['n'])})"
        for k, d in sorted(summary.items())
    )


def evaluate(pool: Any, model: str, games: int, seed: int, opponents: list[str]) -> dict[str, Any]:
    lineups = [[LEARNER, o] for o in opponents]
    jobs = _jobs(lineups, games, seed, model, model, train=False)
    res = list(pool.imap_unordered(play_game, jobs, chunksize=2))
    return summarize(res)


def cmd_run(args: argparse.Namespace) -> None:
    _W_PAIR[:] = [args.pair_p, args.pair_temp]
    outdir = Path(args.dir)
    outdir.mkdir(parents=True, exist_ok=True)
    learner = Learner(args)
    cur = outdir / f"{args.out}_cur"
    learner.export(cur, with_opt=False)
    snap = outdir / f"{args.out}_snap"
    learner.export(snap, with_opt=False)
    lineups = [ln.split(",") for ln in args.lineups]
    log = (outdir / f"{args.out}.log.jsonl").open("a")
    start = args.start_iter
    with Pool(args.procs, initializer=_init, initargs=(args.bonus,)) as pool:
        if args.eval_every and start == 0:
            ev = evaluate(pool, str(cur.with_suffix(".npz")), args.eval_games, 9000, args.eval_opps)
            print(f"eval it0: {_fmt(ev)}", flush=True)
            log.write(json.dumps({"iter": 0, "eval": ev}) + "\n")
        for it in range(start + 1, start + args.iters + 1):
            t0 = time.time()
            jobs = _jobs(
                lineups,
                args.games // len(lineups),
                args.seed + it * 1_000_000,
                str(cur.with_suffix(".npz")),
                str(snap.with_suffix(".npz")),
                train=True,
            )
            res = list(pool.imap_unordered(play_game, jobs, chunksize=2))
            t_play = time.time() - t0
            data = batch_arrays(res, args.lam)
            dev_rate = float((data["aidx"] != data["sidx"]).mean())
            n_games = sum(1 for r in res for nm in r["seats"] if nm == LEARNER)
            t1 = time.time()
            pairs = pair_arrays(res) if args.pair_p > 0 else None
            st = learner.update(data, pairs)
            if pairs is not None:
                pa = pairs["adv"]
                st["pairs"] = float(len(pa))
                st["pair_adv"] = float(pa.mean())
                st["pair_pos"] = float((pa > 0).mean())
            learner.export(cur, with_opt=False)
            if it % args.snap_every == 0:
                learner.export(snap, with_opt=False)
            if it % args.save_every == 0:
                learner.export(outdir / args.out)
                learner.export(outdir / f"{args.out}_it{it}", with_opt=False)
            summ = summarize(res)
            print(
                f"it {it}: {len(data['aidx'])} steps,"
                f" dev/game {dev_rate * len(data['aidx']) / n_games:.1f}"
                f" | play {t_play:.0f}s learn {time.time() - t1:.0f}s"
                f" | pl {st['pl']:.4f} v$rmse {math.sqrt(st['vl']) * VALUE_SCALE:.1f}"
                f" kl_ref {st['kl_ref']:.4f} kl_old {st['kl_old']:.4f} clip {st['clip']:.3f}"
                f" ent {st['ent']:.3f}"
                + (
                    f" | pairs {int(st['pairs'])} adv ${st['pair_adv']:.2f}"
                    f" pos {st['pair_pos']:.2f}"
                    if "pairs" in st
                    else ""
                )
                + f" | {_fmt(summ)}",
                flush=True,
            )
            row: dict[str, Any] = {"iter": it, "train": summ, "stats": st, "dev_rate": dev_rate}
            if args.eval_every and it % args.eval_every == 0:
                ev = evaluate(
                    pool, str(cur.with_suffix(".npz")), args.eval_games, 9000, args.eval_opps
                )
                print(f"eval it{it}: {_fmt(ev)}", flush=True)
                row["eval"] = ev
            log.write(json.dumps(row) + "\n")
            log.flush()
    learner.export(outdir / args.out)


# ---------------------------------------------------------------------------- API


def save_pairs(path: Path, pairs: dict[str, np.ndarray]) -> None:
    np.savez(path, **{k: (v.astype(np.float16) if k == "x" else v) for k, v in pairs.items()})


def load_pairs(paths: list[Path]) -> dict[str, np.ndarray]:
    parts = [dict(np.load(p)) for p in paths]
    k = max(d["cands"].shape[1] for d in parts)
    for d in parts:
        c = d["cands"]
        if c.shape[1] < k:
            d["cands"] = np.pad(c, ((0, 0), (0, k - c.shape[1])), constant_values=-1)
    return {key: np.concatenate([d[key] for d in parts]) for key in parts[0]}


def fit_advantage(
    args: argparse.Namespace, data: dict[str, np.ndarray], out: Path
) -> dict[str, float]:
    """Regression of logit(b) - logit(strategist) on the paired dollar advantage / ``dpl``
    (Huber), starting from the init net; the other candidates' logit gaps are held near the
    init net's (``reg``). The policy then deviates where the predicted gain exceeds
    ``bonus * dpl`` dollars."""
    import torch

    from tools.az_train import build_model

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(Path(args.init_dir) / f"{args.init}.pt", weights_only=False)
    d_in = len(ck["norm_mean"])
    n_seats = ck["state"]["v2.bias"].shape[0]
    model = build_model(d_in, ck["width"], ck["blocks"], n_seats).to(dev)
    model.load_state_dict(ck["state"])
    ref = copy.deepcopy(model).eval()
    mean = torch.tensor(ck["norm_mean"], device=dev)
    inv = torch.tensor(ck["norm_inv"], device=dev)
    n = len(data["adv"])
    perm = np.random.default_rng(args.seed).permutation(n)
    n_val = max(200, n // 10)
    val, tr = perm[:n_val], perm[n_val:]
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    def gaps(m: Any, ix: np.ndarray) -> tuple[Any, Any, Any, Any]:
        x = torch.tensor(data["x"][ix].astype(np.float32), device=dev)
        x = torch.clamp((x - mean) * inv, -5, 5)
        cm = torch.tensor(data["cands"][ix], device=dev)
        sidx = torch.tensor(data["sidx"][ix], device=dev)
        logits, _ = m(x)
        g = torch.gather(logits, 1, cm.clamp(min=0))
        g = g - g.gather(1, sidx[:, None])
        return g, cm >= 0, x, cm

    def loss_on(ix: np.ndarray) -> tuple[Any, Any]:
        g, mask, x, cm = gaps(model, ix)
        with torch.no_grad():
            rl, _ = ref(x)
            rg = torch.gather(rl, 1, cm.clamp(min=0))
            sidx = torch.tensor(data["sidx"][ix], device=dev)
            rg = rg - rg.gather(1, sidx[:, None])
        bidx = torch.tensor(data["bidx"][ix], device=dev)
        t = torch.tensor(data["adv"][ix] / args.dpl, device=dev)
        pred = g.gather(1, bidx[:, None])[:, 0]
        fit = torch.nn.functional.huber_loss(pred, t, delta=args.huber)
        other = mask.clone()
        other.scatter_(1, bidx[:, None], False)
        reg = (((g - rg) ** 2) * other).sum() / other.sum().clamp(min=1)
        return fit + args.reg * reg, pred

    steps = 0
    for _ in range(args.fit_epochs):
        model.train()
        order = np.random.default_rng(args.seed + steps).permutation(tr)
        for s in range(0, len(order), args.batch):
            loss, _ = loss_on(order[s : s + args.batch])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()  # pyright: ignore[reportUnknownMemberType]
            steps += 1
    model.eval()
    with torch.no_grad():
        _, pred = loss_on(val)
    pv = pred.cpu().numpy() * args.dpl
    av = data["adv"][val]
    sel = pv > args.bonus * args.dpl
    st = {
        "n": float(n),
        "val_corr": float(np.corrcoef(pv, av)[0, 1]),
        "val_sel_frac": float(sel.mean()),
        "val_sel_adv": float(av[sel].mean()) if sel.any() else float("nan"),
        "val_top10_adv": float(av[np.argsort(-pv)[: max(1, len(pv) // 10)]].mean()),
    }
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save(
        {"state": state, **{k: ck[k] for k in ("norm_mean", "norm_inv", "width", "blocks")}},
        out.with_suffix(".pt"),
    )
    arrays = {k: v.numpy() for k, v in state.items()}
    arrays["norm_mean"] = ck["norm_mean"]
    arrays["norm_inv"] = ck["norm_inv"]
    arrays["meta_blocks"] = np.array([ck["blocks"]])
    np.savez(out.with_suffix(".npz"), **arrays)
    return st


def cmd_api(args: argparse.Namespace) -> None:
    """Approximate policy iteration: collect paired advantages with the current policy, fit
    the advantage regression on the last ``window`` shards, evaluate greedily, repeat."""
    outdir = Path(args.dir)
    outdir.mkdir(parents=True, exist_ok=True)
    cur = outdir / f"{args.out}_cur.npz"
    if not cur.exists():
        src = Path(args.init_dir) / f"{args.init}.npz"
        cur.write_bytes(src.read_bytes())
    lineups = [ln.split(",") for ln in args.lineups]
    log = (outdir / f"{args.out}.log.jsonl").open("a")
    with Pool(args.procs, initializer=_init, initargs=(args.bonus,)) as pool:
        for it in range(args.start_iter + 1, args.start_iter + args.iters + 1):
            shard = outdir / f"{args.out}_pairs{it}.npz"
            t0 = time.time()
            if not shard.exists():
                _W_PAIR[:] = [args.pair_p, args.pair_temp]
                pol_cont = args.rollout == "policy" or (args.rollout == "first" and it > 1)
                _W_ROLLOUT[0] = "policy" if pol_cont else "strategist"
                jobs = _jobs(
                    lineups,
                    args.games // len(lineups),
                    args.seed + it * 1_000_000,
                    str(cur),
                    str(cur),
                    train=True,
                )
                res = list(pool.imap_unordered(play_game, jobs, chunksize=1))
                pairs = pair_arrays(res)
                assert pairs is not None
                save_pairs(shard, pairs)
            t_play = time.time() - t0
            first = max(1, it - args.window + 1)
            data = load_pairs([outdir / f"{args.out}_pairs{i}.npz" for i in range(first, it + 1)])
            fit = fit_advantage(args, data, outdir / f"{args.out}_it{it}")
            cur.write_bytes((outdir / f"{args.out}_it{it}.npz").read_bytes())
            a = data["adv"]
            print(
                f"it {it}: {len(a)} pairs (mean ${a.mean():.2f}, pos {(a > 0).mean():.2f})"
                f" play {t_play:.0f}s | fit corr {fit['val_corr']:.3f}"
                f" sel {fit['val_sel_frac']:.3f} sel_adv ${fit['val_sel_adv']:.2f}"
                f" top10 ${fit['val_top10_adv']:.2f}",
                flush=True,
            )
            ev = evaluate(pool, str(cur), args.eval_games, 9000, args.eval_opps)
            print(f"eval it{it}: {_fmt(ev)}", flush=True)
            log.write(json.dumps({"iter": it, "fit": fit, "eval": ev}) + "\n")
            log.flush()


def cmd_eval(args: argparse.Namespace) -> None:
    with Pool(args.procs, initializer=_init, initargs=(args.bonus,)) as pool:
        lineups = [[args.who, o] for o in args.opps]
        jobs = _jobs(lineups, args.games, args.seed, args.model, args.model, train=False)
        for j in jobs:
            j["ledger"] = args.ledger
        res = list(pool.imap_unordered(play_game, jobs, chunksize=2))
    print(_fmt(summarize(res, args.who)))
    if args.ledger:
        keys = [k for k in res[0]["parts"][0] if not k.startswith("f_")] + [
            "f_tasks_completed",
            "f_tasks_incomplete",
        ]
        mine = [r["parts"][r["seats"].index(args.who)] for r in res]
        print(" ".join(f"{k} {statistics.mean(p.get(k, 0) for p in mine):.1f}" for k in keys))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--init", default="it1")
    r.add_argument("--init-dir", default="data/bots/az")
    r.add_argument("--dir", default="data/bots/ppo")
    r.add_argument("--out", default="ppo")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--start-iter", type=int, default=0)
    r.add_argument("--iters", type=int, default=100)
    r.add_argument("--games", type=int, default=480)
    r.add_argument(
        "--lineups",
        nargs="+",
        default=["ppo,heuristic-v6", "ppo,strategist", "ppo,snap", "ppo,ppo"],
    )
    r.add_argument("--seed", type=int, default=50_000_000)
    r.add_argument("--bonus", type=float, default=DEFAULT_BONUS)
    r.add_argument("--lam", type=float, default=0.95)
    r.add_argument("--lr", type=float, default=3e-5)
    r.add_argument("--clip", type=float, default=0.2)
    r.add_argument("--epochs", type=int, default=3)
    r.add_argument("--batch", type=int, default=4096)
    r.add_argument("--vw", type=float, default=1.0)
    r.add_argument("--kl", type=float, default=0.05)
    r.add_argument("--ent", type=float, default=0.0)
    r.add_argument("--max-grad", type=float, default=1.0)
    r.add_argument("--snap-every", type=int, default=10)
    r.add_argument("--save-every", type=int, default=10)
    r.add_argument("--eval-every", type=int, default=10)
    r.add_argument("--eval-games", type=int, default=100)
    r.add_argument("--eval-opps", nargs="+", default=["heuristic-v6", "strategist"])
    r.add_argument("--pair-p", type=float, default=0.0, help="paired advantages (0 = GAE PPO)")
    r.add_argument("--pair-temp", type=float, default=2.0)
    r.add_argument("--procs", type=int, default=12)
    r.set_defaults(fn=cmd_run)
    q = sub.add_parser("api")
    q.add_argument("--init", default="it1")
    q.add_argument("--init-dir", default="data/bots/az")
    q.add_argument("--dir", default="data/bots/ppo")
    q.add_argument("--out", default="api")
    q.add_argument("--start-iter", type=int, default=0)
    q.add_argument("--iters", type=int, default=5)
    q.add_argument("--games", type=int, default=480)
    q.add_argument(
        "--lineups", nargs="+", default=["ppo,heuristic-v6", "ppo,strategist", "ppo,ppo"]
    )
    q.add_argument("--seed", type=int, default=70_000_000)
    q.add_argument("--bonus", type=float, default=DEFAULT_BONUS)
    q.add_argument("--pair-p", type=float, default=0.15)
    q.add_argument("--pair-temp", type=float, default=2.0)
    q.add_argument(
        "--rollout",
        choices=["strategist", "policy", "first"],
        default="strategist",
        help="learner continuation in paired rollouts (first: strategist at iteration 1 only)",
    )
    q.add_argument("--window", type=int, default=3)
    q.add_argument("--dpl", type=float, default=1.0, help="dollars per logit")
    q.add_argument("--huber", type=float, default=10.0)
    q.add_argument("--reg", type=float, default=0.1)
    q.add_argument("--lr", type=float, default=3e-4)
    q.add_argument("--fit-epochs", type=int, default=8)
    q.add_argument("--batch", type=int, default=512)
    q.add_argument("--eval-games", type=int, default=200)
    q.add_argument("--eval-opps", nargs="+", default=["heuristic-v6", "strategist"])
    q.add_argument("--procs", type=int, default=12)
    q.set_defaults(fn=cmd_api)
    e = sub.add_parser("eval")
    e.add_argument("--model", required=True)
    e.add_argument("--who", default=LEARNER, help="ppo, or a fixed bot spec to evaluate instead")
    e.add_argument("--opps", nargs="+", default=["heuristic-v6", "strategist"])
    e.add_argument("--games", type=int, default=100)
    e.add_argument("--seed", type=int, default=9000)
    e.add_argument("--bonus", type=float, default=DEFAULT_BONUS)
    e.add_argument("--ledger", action="store_true")
    e.add_argument("--procs", type=int, default=12)
    e.set_defaults(fn=cmd_eval)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
