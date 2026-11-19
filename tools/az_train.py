"""AZ pipeline: generate games (strategist priming data or AZ self-play), train, evaluate.

The recipe behind data/bots/az/current.npz (it1; docs/AZ.md), seeds as used:

    P="uv run python -m tools.az_train"
    # 1. priming: strategist decisions (one-hot policy targets) and final dollars
    $P play --lineups strategist,strategist strategist,heuristic-v6 --games 3000 \
        --seed 100000 --record strategist --keep 0.5 --out data/bots/az/shards/bc
    $P train --shards 'data/bots/az/shards/bc_*' --out bc0 --epochs 6
    # 2. counterfactual value data: rare strategic deviations drawn from the net prior
    $P play --lineups strategist,strategist strategist,heuristic-v6 --games 4000 \
        --seed 200000 --record strategist --keep 0.35 --explore 0.04 \
        --model data/bots/az/bc0.npz --out data/bots/az/shards/ex
    $P train --shards 'data/bots/az/shards/bc_*' 'data/bots/az/shards/ex_*' --out bc1
    $P play ... --games 6000 --seed 300000 --keep 0.18 --explore 0.06 \
        --model data/bots/az/bc1.npz --out data/bots/az/shards/ex2 --shard-games 400
    $P train --shards ...bc_* ...ex_* ...ex2_* --max-samples 2700000 --out bc2
    # 3. AZ iteration: search games, visit-count policy targets (it1 listed twice = weight 2)
    $P play --lineups az,heuristic-v6 az,strategist --games 500 --seed 400000 \
        --model data/bots/az/bc2.npz --sims 64 --prior-mix 0.5 --leaf-steps 150 \
        --skip-conf 0.97 --dirichlet 0.25 --record az --out data/bots/az/shards/it1
    $P train --shards ...bc_* ...ex_* ...ex2_* ...it1_* ...it1_* --max-samples 2700000 \
        --init bc2 --out it1 --epochs 3 --lr 7e-4
    # evaluation (100 games, seeds 9000+, with a dollar breakdown)
    $P play --lineups az,heuristic-v6 --games 100 --seed 9000 --model data/bots/az/it1.npz \
        --sims 64 --prior-mix 0.5 --leaf-steps 150 --skip-conf 0.97 --ledger

2 players, joinery side (the strategist's benchmark setting). Game g of a lineup seats its
entries rotated by g, seeds ``seed + g``. Policy targets are stored sparsely over the candidate
actions; value targets are every seat's final dollars, recording seat first. Shards and .pt
checkpoints are git-ignored; only the runtime model data/bots/az/current.npz is committed.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import statistics
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any, cast

# One BLAS thread per worker process (12 workers would oversubscribe the cores otherwise).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import pyspiel

import lignum.game  # noqa: F401  # pyright: ignore[reportUnusedImport]
from lignum.bots.az.features import Encoder
from lignum.bots.az.search import SearchConfig, is_strategic
from lignum.bots.base import bot_candidates
from lignum.game import LignumState

N_ACTIONS = 440

# ---------------------------------------------------------------------------- playing

_W: dict[str, Any] = {}


def _bot(spec: str) -> Any:
    b = _W["bots"].get(spec)
    if b is not None:
        return b
    if spec.startswith("plan"):
        from lignum.bots.plan_search import PlanConfig, PlanSearchBot

        executor = None
        if spec == "plan-az":
            from lignum.bots.az.bot import AZBot

            executor = AZBot(_W["model"], SearchConfig(**_W["cfg"]))
        b = PlanSearchBot(executor, PlanConfig(**_W["opts"]["plan"]))
    elif spec.startswith("az"):
        from lignum.bots.az.bot import AZBot

        cfg = SearchConfig(**_W["cfg"])
        model = _W["model"]
        if ":" in spec:  # az:path/to/model.npz
            model = spec.split(":", 1)[1]
        b = AZBot(model, cfg)
    elif spec == "strategist":
        from lignum.bots.strategist import StrategistBot

        b = StrategistBot()
    else:
        from server.bots import get_bot

        b = get_bot(spec)
    _W["bots"][spec] = b
    return b


def _init(model: str, cfg: dict[str, Any], opts: dict[str, Any]) -> None:
    _W.clear()
    _W.update(bots={}, model=model, cfg=cfg, opts=opts)


def _explore_move(st: LignumState, cands: list[int], a: int, rng: random.Random) -> int:
    """An alternative to ``a`` drawn from the net prior at temperature 2 (uniform without one)."""
    others = [c for c in cands if c != a]
    if not others:
        return a
    if _W.get("prior_net") is None:
        from lignum.bots.az.net import NumpyNet

        _W["prior_net"] = NumpyNet(_W["model"]) if Path(_W["model"]).exists() else False
        _W["prior_enc"] = {}
    net = _W["prior_net"]
    if not net:
        return rng.choice(others)
    encs = cast(dict[int, Encoder], _W["prior_enc"])
    enc = encs.get(st.n) or encs.setdefault(st.n, Encoder(st.get_game()))
    logits, _ = net.forward(enc.encode(st, st.current_player())[None, :])
    lg = logits[0, others] / 2.0
    w = np.exp(lg - lg.max())
    return rng.choices(others, list(w))[0]


def play_game(job: tuple[list[str], int, int]) -> dict[str, Any]:
    lineup, seed, rot = job
    opts = _W["opts"]
    n = len(lineup)
    seats = [lineup[(s + rot) % n] for s in range(n)]
    bots = [_bot(x) for x in seats]
    game = pyspiel.load_game("python_lignum", {"players": n})
    enc = Encoder(game)
    rng = random.Random(seed)
    st = game.new_initial_state()
    assert isinstance(st, LignumState)
    rec = set(opts["record"])
    ledger = None
    apply = st.apply_action
    if opts.get("ledger"):
        from tools.ledger import Ledger

        ledger = Ledger(st)
        apply = ledger.apply
    xs: list[np.ndarray] = []
    seat_of: list[int] = []
    pol: list[tuple[list[int], list[float]]] = []
    full_sims = _W["cfg"].get("sims", 64)
    t0 = time.time()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            a = rng.choices([x for x, _ in outs], [p for _, p in outs])[0]
            apply(a)
            continue
        p = st.current_player()
        bot = bots[p]
        name = seats[p]
        is_az = name.startswith("az")
        # plan-az: the executor's search settings follow the AZ options
        ctl = bot.executor if name == "plan-az" else bot
        full = True
        if is_az or name == "plan-az":
            full = rng.random() < opts["full_frac"]
            ctl.cfg.sims = full_sims if full else opts["fast_sims"]
            ctl.cfg.dirichlet = opts["dirichlet"] if (full and rec) else 0.0
            ctl.temperature = (
                opts["temperature"] if (rec and st.round <= opts["temp_rounds"]) else 0
            )
        want = (name.split(":")[0] in rec) and full and rng.random() < opts["keep"]
        explore = opts["explore"] > 0 and name in rec and is_strategic(st)
        if want or explore:
            cands = bot_candidates(st)
            if len(cands) > 1:
                x = enc.encode(st, p)
                a = bot.choose(st, rng)
                if explore and rng.random() < opts["explore"]:
                    # counterfactual coverage for the value net; the policy target stays ``a``
                    played = _explore_move(st, cands, a, rng)
                else:
                    played = a
                if not want:
                    apply(played)
                    continue
                if is_az and bot.last is not None:
                    cs, pr = bot.last
                    pol.append((list(cs), [float(v) for v in pr]))
                else:
                    pol.append((cands, [1.0 if c == a else 0.0 for c in cands]))
                xs.append(x.astype(np.float16))
                seat_of.append(p)
                apply(played)
                continue
        apply(bot.choose(st, rng))
    final = list(st.final)
    vals = [[final[(s + k) % n] for k in range(n)] for s in seat_of]
    extra: dict[str, Any] = {}
    if ledger is not None:
        bd = ledger.breakdown()
        fn = ledger.funnels()
        extra = {"parts": [{**bd[s], **{f"f_{k}": v for k, v in fn[s].items()}} for s in range(n)]}
    return {
        **extra,
        "seats": seats,
        "final": final,
        "x": np.stack(xs) if xs else None,
        "pol": pol,
        "v": np.array(vals, np.float32) if vals else None,
        "secs": time.time() - t0,
    }


def save_shard(path: Path, results: list[dict[str, Any]]) -> int:
    xs = [r["x"] for r in results if r["x"] is not None]
    if not xs:
        return 0
    x = np.concatenate(xs)
    v = np.concatenate([r["v"] for r in results if r["v"] is not None])
    pols = [p for r in results for p in r["pol"]]
    k = max(len(c) for c, _ in pols)
    idx = np.full((len(pols), k), -1, np.int16)
    prob = np.zeros((len(pols), k), np.float16)
    for i, (c, pr) in enumerate(pols):
        idx[i, : len(c)] = c
        prob[i, : len(c)] = pr
    np.savez(path, x=x, v=v, idx=idx, prob=prob)
    return len(x)


def cmd_play(args: argparse.Namespace) -> None:
    cfg = dict(
        sims=args.sims,
        c_puct=args.c_puct,
        q_scale=args.q_scale,
        fpu=args.fpu,
        margin=args.margin,
        prior_mix=args.prior_mix,
        macro=not args.micro,
        leaf_steps=args.leaf_steps,
        skip_conf=args.skip_conf,
        key_mult=args.key_mult,
        opp_default=args.opp_default,
    )
    opts = dict(
        record=args.record.split(",") if args.record else [],
        keep=args.keep,
        full_frac=args.full_frac,
        fast_sims=args.fast_sims,
        dirichlet=args.dirichlet,
        temperature=args.temperature,
        temp_rounds=args.temp_rounds,
        explore=args.explore,
        ledger=args.ledger,
        plan=dict(
            playouts=args.plan_playouts,
            areas=args.plan_areas,
            tasks=args.plan_tasks,
            keep=args.plan_keep,
            ahead=args.plan_ahead,
            commit_bonus=args.plan_commit,
            reserve=args.plan_reserve,
        ),
    )
    jobs: list[tuple[list[str], int, int]] = []
    lineups = [ln.split(",") for ln in args.lineups]
    for li, lineup in enumerate(lineups):
        for g in range(args.games):
            jobs.append((lineup, args.seed + g, g % len(lineup)))
        del li
    random.Random(args.seed).shuffle(jobs) if args.record else None
    out = Path(args.out) if args.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
    scores: dict[str, list[float]] = {}
    per_lineup: dict[str, dict[str, list[float]]] = {}
    buf: list[dict[str, Any]] = []
    parts: dict[str, dict[str, list[float]]] = {}
    shard = 0
    total = 0
    t0 = time.time()
    with Pool(args.procs, initializer=_init, initargs=(args.model, cfg, opts)) as pool:
        for i, r in enumerate(pool.imap_unordered(play_game, jobs, chunksize=1)):
            key = ",".join(sorted(r["seats"]))
            for s, name in enumerate(r["seats"]):
                scores.setdefault(name, []).append(r["final"][s])
                for k, v in r.get("parts", [{}] * len(r["seats"]))[s].items():
                    parts.setdefault(name, {}).setdefault(k, []).append(v)
                per_lineup.setdefault(key, {}).setdefault(name, []).append(r["final"][s])
            if out is not None and r["x"] is not None:
                buf.append(r)
                if len(buf) >= args.shard_games:
                    total += save_shard(Path(f"{out}_{shard:03d}.npz"), buf)
                    shard += 1
                    buf = []
            if (i + 1) % max(1, len(jobs) // 10) == 0:
                el = time.time() - t0
                summ = " ".join(f"{k}={statistics.mean(v):.1f}" for k, v in scores.items())
                print(f"[{i + 1}/{len(jobs)}] {el:.0f}s {summ}", flush=True)
    if out is not None and buf:
        total += save_shard(Path(f"{out}_{shard:03d}.npz"), buf)
    report: dict[str, Any] = {}
    for key, d in per_lineup.items():
        for name, v in d.items():
            sd = statistics.pstdev(v) if len(v) > 1 else 0.0
            report[f"{key} :: {name}"] = {
                "mean": round(statistics.mean(v), 2),
                "se": round(sd / math.sqrt(len(v)), 2),
                "n": len(v),
            }
    for name, d in parts.items():
        print(name, " ".join(f"{k}={statistics.mean(v):.2f}" for k, v in d.items() if any(v)))
    print(json.dumps(report, indent=1))
    if out is not None:
        print(f"recorded {total} samples")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1))


# ---------------------------------------------------------------------------- training


def load_shards(patterns: list[str], max_samples: int) -> dict[str, np.ndarray]:
    """Load shards (newest first up to ``max_samples``) into preallocated arrays."""
    files: list[str] = []
    for pat in patterns:
        files += sorted(glob.glob(pat))
    files = files[::-1]
    sizes: list[tuple[str, int, int, int, int]] = []
    n = kmax = 0
    for f in files:
        with np.load(f) as z:
            v = z["v"]
            k = z["idx"].shape[1]
            d = z["x"].shape[1] if not sizes else sizes[0][3]
        sizes.append((f, len(v), k, d, v.shape[1]))
        n += len(v)
        kmax = max(kmax, k)
        if n >= max_samples:
            break
    d, nv = sizes[0][3], sizes[0][4]
    out = {
        "x": np.empty((n, d), np.float16),
        "v": np.empty((n, nv), np.float32),
        "idx": np.full((n, kmax), -1, np.int16),
        "prob": np.zeros((n, kmax), np.float16),
    }
    i = 0
    for f, m, k, _, _ in sizes:
        with np.load(f) as z:
            out["x"][i : i + m] = z["x"]
            out["v"][i : i + m] = z["v"]
            out["idx"][i : i + m, :k] = z["idx"]
            out["prob"][i : i + m, :k] = z["prob"]
        i += m
    print(f"loaded {n} samples from {len(sizes)} shards", flush=True)
    return out


def build_model(d_in: int, width: int, blocks: int, n_seats: int) -> Any:
    import torch
    from torch import nn

    class Block(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.ln1 = nn.LayerNorm(width)
            self.fc1 = nn.Linear(width, width)
            self.fc2 = nn.Linear(width, width)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            return h + self.fc2(torch.relu(self.fc1(self.ln1(h))))

    class Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = nn.Linear(d_in, width)
            self.blocks = nn.ModuleList([Block() for _ in range(blocks)])
            self.ln = nn.LayerNorm(width)
            self.pi = nn.Linear(width, N_ACTIONS)
            self.v1 = nn.Linear(width, 256)
            self.v2 = nn.Linear(256, n_seats)

        def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            h = self.stem(x)
            for b in self.blocks:
                h = b(h)
            h = torch.relu(self.ln(h))
            return self.pi(h), self.v2(torch.relu(self.v1(h)))

    return Net()


def cmd_train(args: argparse.Namespace) -> None:
    import torch

    from lignum.bots.az.net import VALUE_SCALE

    torch.manual_seed(args.seed)  # pyright: ignore[reportUnknownMemberType]
    data = load_shards(args.shards, args.max_samples)
    x_all = data["x"]
    n, d = x_all.shape
    n_seats = data["v"].shape[1]
    outdir = Path(args.dir)
    outdir.mkdir(parents=True, exist_ok=True)
    if args.init:
        ck = torch.load(outdir / f"{args.init}.pt", weights_only=False)
        mean, inv = ck["norm_mean"], ck["norm_inv"]
        width, blocks = ck["width"], ck["blocks"]
    else:
        xs = x_all[np.random.default_rng(0).choice(n, min(n, 200_000), replace=False)]
        xs = xs.astype(np.float32)
        mean = xs.mean(0)
        sd = xs.std(0)
        inv = np.where(sd > 1e-6, 1.0 / np.maximum(sd, 0.05), 0.0).astype(np.float32)
        width, blocks = args.width, args.blocks
        ck = None
    model = build_model(d, width, blocks, n_seats)
    if ck is not None:
        model.load_state_dict(ck["state"])
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(dev)
    perm = np.random.default_rng(args.seed).permutation(n)
    n_val = min(20_000, n // 20)
    val_i, tr_i = perm[:n_val], perm[n_val:]
    mean_t = torch.tensor(mean, device=dev)
    inv_t = torch.tensor(inv, device=dev)

    def batch(ix: np.ndarray) -> tuple[torch.Tensor, ...]:
        x = torch.tensor(x_all[ix].astype(np.float32), device=dev)
        x = torch.clamp((x - mean_t) * inv_t, -5, 5)
        v = torch.tensor(data["v"][ix] / VALUE_SCALE, device=dev)
        idx = torch.tensor(data["idx"][ix].astype(np.int64), device=dev)
        prob = torch.tensor(data["prob"][ix].astype(np.float32), device=dev)
        return x, v, idx, prob

    def losses(xb: torch.Tensor, vb: torch.Tensor, ib: torch.Tensor, pb: torch.Tensor) -> Any:
        logits, v = model(xb)
        mask = ib >= 0
        g = torch.gather(logits, 1, ib.clamp(min=0))
        g = g.masked_fill(~mask, -1e9)
        logp = torch.log_softmax(g, 1)
        pl = -(pb * logp).sum(1).mean()
        acc = (g.argmax(1) == pb.argmax(1)).float().mean()
        vl = ((v - vb) ** 2).mean()
        return pl, vl, acc

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps_per_epoch = max(1, len(tr_i) // args.batch)
    total_steps = steps_per_epoch * args.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=total_steps)
    rng = np.random.default_rng(args.seed)
    for ep in range(args.epochs):
        model.train()
        order = rng.permutation(tr_i)
        tl = [0.0, 0.0, 0.0]
        for s in range(steps_per_epoch):
            ix = np.sort(order[s * args.batch : (s + 1) * args.batch])
            pl, vl, acc = losses(*batch(ix))
            loss = pl + args.vw * vl
            opt.zero_grad()
            loss.backward()
            opt.step()  # pyright: ignore[reportUnknownMemberType]
            sched.step()
            tl[0] += pl.item()
            tl[1] += vl.item()
            tl[2] += acc.item()
        model.eval()
        with torch.no_grad():
            vs = [0.0, 0.0, 0.0]
            nb = 0
            for s in range(0, n_val, 4096):
                pl, vl, acc = losses(*batch(np.sort(val_i[s : s + 4096])))
                vs[0] += float(pl)
                vs[1] += float(vl)
                vs[2] += float(acc)
                nb += 1
        k = steps_per_epoch
        print(
            f"epoch {ep}: train pi {tl[0] / k:.3f} v$rmse {math.sqrt(tl[1] / k) * VALUE_SCALE:.2f}"
            f" acc {tl[2] / k:.3f} | val pi {vs[0] / nb:.3f}"
            f" v$rmse {math.sqrt(vs[1] / nb) * VALUE_SCALE:.2f} acc {vs[2] / nb:.3f}",
            flush=True,
        )
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save(
        {"state": state, "norm_mean": mean, "norm_inv": inv, "width": width, "blocks": blocks},
        outdir / f"{args.out}.pt",
    )
    arrays = {k: v.numpy() for k, v in state.items()}
    arrays["norm_mean"] = mean
    arrays["norm_inv"] = inv
    arrays["meta_blocks"] = np.array([blocks])
    np.savez(outdir / f"{args.out}.npz", **arrays)
    print(f"wrote {outdir / args.out}.npz")


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--lineups", nargs="+", required=True)
    p.add_argument("--games", type=int, default=100, help="games per lineup")
    p.add_argument("--seed", type=int, default=2000)
    p.add_argument("--procs", type=int, default=11)
    p.add_argument("--model", default="data/bots/az/current.npz")
    p.add_argument("--record", default="")
    p.add_argument("--out", default="")
    p.add_argument("--shard-games", type=int, default=200)
    p.add_argument("--keep", type=float, default=1.0)
    p.add_argument("--sims", type=int, default=64)
    p.add_argument("--fast-sims", type=int, default=0)
    p.add_argument("--full-frac", type=float, default=1.0)
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--q-scale", type=float, default=10.0)
    p.add_argument("--fpu", type=float, default=2.0)
    p.add_argument("--margin", type=float, default=0.0)
    p.add_argument("--prior-mix", type=float, default=0.0)
    p.add_argument("--dirichlet", type=float, default=0.0)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--temp-rounds", type=int, default=0)
    p.add_argument("--explore", type=float, default=0.0, help="random strategic deviations")
    p.add_argument("--micro", action="store_true", help="search every decision, not macro")
    p.add_argument("--leaf-steps", type=int, default=0)
    p.add_argument("--skip-conf", type=float, default=1.1)
    p.add_argument("--key-mult", type=float, default=1.0)
    p.add_argument("--opp-default", action="store_true")
    p.add_argument("--plan-playouts", type=int, default=8)
    p.add_argument("--plan-areas", type=int, default=2)
    p.add_argument("--plan-tasks", type=int, default=3)
    p.add_argument("--plan-keep", type=int, default=3)
    p.add_argument("--plan-ahead", type=int, default=0, help="two-round plans (next-round tasks)")
    p.add_argument("--plan-reserve", action="store_true", help="wood for scheduled tasks")
    p.add_argument("--plan-commit", type=float, default=0.0, help="$ bonus for the scheduled task")
    p.add_argument("--ledger", action="store_true", help="dollar components per seat")
    p.add_argument("--json", default="")
    t = sub.add_parser("train")
    t.add_argument("--shards", nargs="+", required=True)
    t.add_argument("--max-samples", type=int, default=1_500_000)
    t.add_argument("--dir", default="data/bots/az")
    t.add_argument("--out", required=True)
    t.add_argument("--init", default="")
    t.add_argument("--width", type=int, default=512)
    t.add_argument("--blocks", type=int, default=3)
    t.add_argument("--epochs", type=int, default=8)
    t.add_argument("--batch", type=int, default=1024)
    t.add_argument("--lr", type=float, default=2e-3)
    t.add_argument("--vw", type=float, default=4.0)
    t.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.cmd == "play":
        cmd_play(args)
    else:
        cmd_train(args)


if __name__ == "__main__":
    main()
