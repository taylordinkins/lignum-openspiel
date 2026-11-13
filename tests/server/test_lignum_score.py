"""Terminal ``score`` breakdown in the Lignum view (R-081..R-086)."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest
import yaml

from lignum import actions as A
from lignum import game as G
from server.adapters.lignum import LignumAdapter
from tests import harness as H

_ROOT = Path(__file__).resolve().parents[2] / "data" / "components"
_SETUP = yaml.safe_load((_ROOT / "setup.yaml").read_text())
_BIDS = [b["id"] for b in yaml.safe_load((_ROOT / "buildings.yaml").read_text())["buildings"]]
_KINDS = ["firewood", "softwood", "hardwood"]
_UNM = [_SETUP["wood_prices"][k]["unmilled"] for k in _KINDS]
_MIL = [_SETUP["wood_prices"][k]["milled"] for k in _KINDS]
_DB = _SETUP["drying_bonuses"]
_BON = [_DB["sale_area"], _DB["drying_1"], _DB["drying_2"], _DB["drying_3"]]
_REPAY = {0: 0, **{int(k): v for k, v in _SETUP["loans"]["repayment"].items()}}
_LOAN_AMT = _SETUP["loans"]["amount_each"]


def _round8_n3_to_n4(self: Any) -> bool:
    return self.phase == G.PHASE_N4 and self.round == 8


def _fuzz(self: Any) -> None:
    """Randomise the state the final sale reads (keyed on history so a replay reproduces it)."""
    rng = random.Random(str(tuple(self.history())))
    n = self.n
    r3 = lambda m: tuple(rng.randint(0, m) for _ in range(3))  # noqa: E731
    self.money = tuple(rng.choice([0, 0, rng.randint(0, 40)]) for _ in range(n))
    self.loans = tuple(rng.randint(0, 2) for _ in range(n))
    self.sale = tuple(r3(rng.choice([0, 0, 2])) for _ in range(n))
    self.sale_logs = tuple(r3(rng.choice([0, 0, 2])) for _ in range(n))
    self.dry = tuple(
        tuple(tuple(rng.randint(0, rng.choice([0, 0, 0, 2])) for _ in range(6)) for _ in range(3))
        for _ in range(n)
    )
    self.river = tuple(
        tuple(rng.choice([0, 0, rng.randint(1, 3)]) for _ in range(3)) for _ in range(n)
    )
    if self.get_game().joinery:
        self.joiners = tuple(rng.randint(0, 3) for _ in range(n))
        self.joinery_wood = tuple(
            tuple(rng.choice([G.NO_SLOT, 0, 1, 2]) for _ in range(3)) for _ in range(n)
        )
        pool = [_BIDS.index("office"), _BIDS.index("small_joinery")]
        seen: set[int] = set()
        held = []
        for _ in range(n):
            mine = tuple(b for b in pool if b not in seen and rng.random() < 0.4)
            seen.update(mine)
            held.append(mine)
        self.held_buildings = tuple(held)
    ids = list(range(len(self.filled)))
    rng.shuffle(ids)
    ht = []
    for _ in range(n):
        k = rng.randint(0, 3)
        ht.append(tuple(ids[:k]))
        ids = ids[k:]
    self.held_tasks = tuple(ht)
    filled = list(self.filled)
    for h in ht:
        for tk in h:
            full = (1 << len(G._components().tasks[tk].requirements)) - 1
            filled[tk] = full if rng.random() < 0.5 else rng.randint(0, full)
    self.filled = tuple(filled)


def _clear(self: Any) -> None:
    """Empty every zone the final sale reads and hold no tasks."""
    n = self.n
    z3 = (0, 0, 0)
    self.sale = self.sale_logs = self.river = (z3,) * n
    self.dry = (((0,) * 6,) * 3,) * n
    self.joinery_wood = ((G.NO_SLOT,) * 3,) * n
    self.held_tasks = ((),) * n
    self.held_buildings = ((),) * n


@pytest.fixture
def hooks(monkeypatch: pytest.MonkeyPatch):
    """Install the round-8 N3->N4 hook and the entry snapshot; yields the snapshot dict."""
    snaps: dict[tuple[int, ...], dict[str, Any]] = {}
    state: dict[str, Any] = {"n3_hook": _fuzz, "entry_hook": None}
    orig_next = G.LignumState._next_winter_turn
    orig_begin = G.LignumState._begin_final_sale

    def nwt(self: Any) -> None:
        before = self.phase
        orig_next(self)
        if before == G.PHASE_N3 and _round8_n3_to_n4(self):
            state["n3_hook"](self)

    def begin(self: Any) -> None:
        if state["entry_hook"]:
            state["entry_hook"](self)
        snaps[tuple(self.history())] = {
            k: getattr(self, a)
            for k, a in dict(
                money="money",
                loans="loans",
                sale="sale",
                sale_logs="sale_logs",
                dry="dry",
                river="river",
                joiners="joiners",
                joinery_wood="joinery_wood",
                hb="held_buildings",
                ht="held_tasks",
                filled="filled",
            ).items()
        }
        orig_begin(self)

    monkeypatch.setattr(G.LignumState, "_next_winter_turn", nwt)
    monkeypatch.setattr(G.LignumState, "_begin_final_sale", begin)
    return snaps, state


def _oracle(snap: dict[str, Any], n: int, fs: list[tuple[int, int]]) -> list[dict[str, Any]]:
    comps = G._components()
    loans = list(snap["loans"])
    extra = [0] * n
    choice: dict[int, int] = {}
    for seat, a in fs:
        d = A.decode(a)
        if d.name == "TAKE_LOAN":
            loans[seat] += 1
            extra[seat] += _LOAN_AMT
        else:
            choice[seat] = d.params[0]
    sj, office = _BIDS.index("small_joinery"), _BIDS.index("office")
    out = []
    for s in range(n):
        wood = 0
        for k in range(3):
            if _UNM[k] is not None:
                wood += snap["sale"][s][k] * (_UNM[k] + _BON[0])
            wood += snap["sale_logs"][s][k] * (_MIL[k] + _BON[0])
            for z in range(3):
                if _UNM[k] is not None:
                    wood += snap["dry"][s][z][k] * (_UNM[k] + _BON[z + 1])
                wood += snap["dry"][s][z][3 + k] * (_MIL[k] + _BON[z + 1])
        rv = snap["river"][s]
        if rv[0] and rv[1]:
            river = rv[choice[s]] * _UNM[choice[s]]
        else:
            assert s not in choice
            river = rv[0] * _UNM[0] + rv[1] * _UNM[1]
        bonus = 4 if sj in snap["hb"][s] else _SETUP["joinery_bonus"]
        jo = sum(
            _MIL[k] + bonus
            for slot, k in enumerate(snap["joinery_wood"][s])
            if k != G.NO_SLOT and slot < snap["joiners"][s]
        )
        off = len(snap["ht"][s]) if office in snap["hb"][s] else 0
        tasks = sum(
            comps.tasks[tk].reward
            for tk in snap["ht"][s]
            if snap["filled"][tk] == (1 << len(comps.tasks[tk].requirements)) - 1
        )
        money = snap["money"][s] + extra[s]
        rep = _REPAY[loans[s]]
        out.append(
            {
                "money": money,
                "wood_sale": wood,
                "river_sale": river,
                "joinery_sale": jo,
                "office": off,
                "tasks": tasks,
                "loans": loans[s],
                "loan_repay": -rep,
                "final": money + wood + river + jo + off + tasks - rep,
            }
        )
    return out


def _play(game: Any, rng: random.Random) -> tuple[Any, list[tuple[int, int]]]:
    s = game.new_initial_state()
    fs: list[tuple[int, int]] = []
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        la = s.legal_actions()
        if s.phase == G.PHASE_FS:
            loan = [x for x in la if x == A.TAKE_LOAN]
            a = loan[0] if loan and rng.random() < 0.4 else rng.choice(la)
            fs.append((s.current_player(), a))
        else:
            nl = [x for x in la if x != A.TAKE_LOAN] or la
            done = [x for x in nl if A.decode(x).name == "DONE"]
            a = rng.choice(done) if done and rng.random() < 0.5 else rng.choice(nl)
        s.apply_action(a)
    return s, fs


@pytest.mark.slow
def test_score_matches_yaml_oracle_on_fuzzed_final_sale(hooks: Any) -> None:
    snaps, _ = hooks
    stats = {"choosers": 0, "fsloan": 0, "wood": 0, "joinery": 0, "tasks": 0}
    for g in range(200):
        rng = random.Random(1000 + g)
        n = rng.choice([2, 3, 4])
        ad = LignumAdapter()
        game = ad.load(
            {
                "num_players": n,
                "joinery": rng.random() < 0.7,
                "returns": rng.choice(["win_loss", "margin"]),
            }
        )
        s, fs = _play(game, rng)
        hist = tuple(s.history())
        keys = [k for k in snaps if hist[: len(k)] == k]
        assert keys, "final sale not entered"
        snap = snaps[max(keys, key=len)]
        snaps.clear()
        want = _oracle(snap, n, fs)
        v = ad.view(s, 0)
        for seat in range(n):
            assert {k: v["score"][seat][k] for k in want[seat]} == want[seat], (g, seat)
            assert want[seat]["final"] == s.final[seat] == v["final"][seat]
        top = max(w["final"] for w in want)
        assert v["winners"] == [i for i in range(n) if want[i]["final"] == top]
        assert v["returns"] == list(s.returns())
        stats["choosers"] += sum(1 for _, a in fs if A.decode(a).name != "TAKE_LOAN")
        stats["fsloan"] += sum(1 for _, a in fs if A.decode(a).name == "TAKE_LOAN")
        stats["wood"] += sum(1 for w in want if w["wood_sale"])
        stats["joinery"] += sum(1 for w in want if w["joinery_sale"])
        stats["tasks"] += sum(1 for w in want if w["tasks"])
    assert all(stats.values()), stats  # every component was exercised


@pytest.mark.parametrize(
    "money,loans,final,winners,win_loss,margin",
    [
        # sole winner, different loan counts: 70, 50-7, 10-16
        ((70, 50, 10), (0, 1, 2), [70, 43, -6], [0], [1.0, -0.5, -0.5], [0.0, 0.0, 0.0]),
        # partial tie: P0 50 with no loan, P1 57-7 = 50, P2 10
        ((50, 57, 10), (0, 1, 0), [50, 50, 10], [0, 1], [0.25, 0.25, -0.5], [0.4, 0.4, -0.8]),
    ],
)
def test_scripted_winner_and_tie(
    hooks: Any, money: Any, loans: Any, final: Any, winners: Any, win_loss: Any, margin: Any
) -> None:
    _, state = hooks
    state["n3_hook"] = _clear

    def entry(self: Any) -> None:
        self.money, self.loans = money, loans

    state["entry_hook"] = entry
    for mode, want_ret in (("win_loss", win_loss), ("margin", margin)):
        ad = LignumAdapter()
        game = ad.load({"num_players": 3, "joinery": True, "returns": mode})
        s, fs = _play(game, random.Random(5))
        assert not fs
        v = ad.view(s, 0)
        assert v["final"] == final
        assert v["winners"] == winners
        if mode == "margin" and final == [70, 43, -6]:
            want_ret = [max(-1.0, min(1.0, (x - (sum(final) - x) / 2) / 50)) for x in final]
        assert v["returns"] == pytest.approx(want_ret)
        assert [c["final"] for c in v["score"]] == final


def test_score_none_before_terminal_incl_final_sale_decision(hooks: Any) -> None:
    _, state = hooks
    seen_fs = False
    for seed in range(40):
        rng = random.Random(seed)
        ad = LignumAdapter()
        s = ad.load({"num_players": 3, "joinery": True}).new_initial_state()
        while not s.is_terminal():
            if s.phase == G.PHASE_FS:
                seen_fs = True
                v = ad.view(s, 0)
                assert v["score"] is None and v["final"] is None and v["winners"] is None
            elif s.round == 8 and rng.random() < 0.2:
                assert ad.view(s, 0)["score"] is None
            if s.is_chance_node():
                s.apply_action(H.sample_chance(s, rng))
            else:
                s.apply_action(rng.choice(s.legal_actions()))
        if seen_fs:
            break
    assert seen_fs


def test_score_absent_before_terminal() -> None:
    ad = LignumAdapter()
    s = ad.load({"num_players": 3, "joinery": True}).new_initial_state()
    assert ad.view(s, 0)["score"] is None


def test_winter_card_sprite_ids_parallel_cards() -> None:
    ad = LignumAdapter()
    s = ad.load({"num_players": 3, "joinery": True}).new_initial_state()
    rng = random.Random(0)
    while s.is_chance_node():
        s.apply_action(H.sample_chance(s, rng))
    w = ad.view(s, 0)["winter"]
    assert len(w["card_ids"]) == len(w["cards"])
    assert all(
        i.startswith(f"winter-{c['year']}-") for i, c in zip(w["card_ids"], w["cards"], strict=True)
    )
