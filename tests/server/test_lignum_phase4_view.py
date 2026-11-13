"""Phase 4 unit 14: public R-028 items in the lignum view, Phase 4 labels, Phase 3 label fixes.

Never reads another seat's hidden pick: views are rendered with the adapter's per-seat ``view``.
"""

from __future__ import annotations

import json
import pathlib
import random
from typing import Any

from lignum import actions as A
from lignum.components import load_components
from tests import harness as H


def _adapter() -> Any:
    from server.adapters.lignum import LignumAdapter

    return LignumAdapter()


def _game(n: int = 2, joinery: bool = True) -> Any:
    return _adapter().load({"num_players": n, "joinery": joinery})


def _sim(n: int, joinery: bool, seed: int, cap: int = 4000):
    """Yield (state) at every decision node of a random game (bias towards non-DONE moves)."""
    game = _game(n, joinery)
    rng = random.Random(seed)
    s = game.new_initial_state()
    for _ in range(cap):
        if s.is_terminal():
            return
        if s.is_chance_node():
            yield s
            s.apply_action(H.sample_chance(s, rng))
            continue
        yield s
        legal = s.legal_actions()
        s.apply_action(rng.choice(legal))


# ---------------------------------------------------------------- B. labels cover every id


def test_every_decision_and_chance_id_has_a_formatter() -> None:
    from server.adapters import lignum as L

    dec = {name for name, _, _ in A._DECISIONS}
    ch = {name for name, _, _ in A._CHANCES}
    assert dec <= set(L._ACTION_FMT), dec - set(L._ACTION_FMT)
    assert ch <= set(L._CHANCE_FMT), ch - set(L._CHANCE_FMT)


def test_every_decision_id_label_is_specific_on_a_fresh_state() -> None:
    ad = _adapter()
    s = _game().new_initial_state()
    for a in range(A.NUM_DISTINCT_ACTIONS):
        name = A.decode(a).name
        lab = ad.action_meta(s, a)["label"]
        assert lab.strip() and lab != name and "_" not in lab, (a, name, lab)


def test_phase4_labels_in_simulated_games() -> None:
    """Every legal action in simulated full games has a readable label; Phase 4 families seen."""
    ad = _adapter()
    seen: set[str] = set()
    for seed in range(6):
        for s in _sim(3, True, seed):
            if s.is_chance_node():
                for a, _p in s.chance_outcomes():
                    assert ad.chance_label(s, a).strip()
                continue
            for a in s.legal_actions():
                meta = ad.action_meta(s, a)
                seen.add(meta["kind"])
                assert meta["label"].strip() and "_" not in meta["label"], meta
    for fam in ("PLAN_WORK", "CHOOSE_BUILDING", "TAKE_TASK"):
        assert fam in seen, fam


def test_take_task_card_is_described_in_view() -> None:
    """The 'Take task NN' label stays stable; the view's task cards say what each card is, and
    the web action list appends that text (plugin.actionLabel)."""
    ad = _adapter()
    comp = load_components()
    for s in _sim(2, False, 1):
        if s.is_chance_node():
            continue
        for a in s.legal_actions():
            if A.decode(a).name == "TAKE_TASK":
                k = A.decode(a).params[0]
                lab = ad.action_meta(s, a)["label"]
                card = next(c for c in ad.view(s, 0)["tasks"]["cards"] if c["index"] == k)
                assert lab == f"Take {card['id']}"
                assert card["reward"] == comp.tasks[k].reward
                assert card["requirements"][0]["text"].startswith(
                    comp.tasks[k].requirements[0].kind
                )
                return
    raise AssertionError("no TAKE_TASK offered")


def test_build_hut_label_uses_hut_effect_slots() -> None:
    ad = _adapter()
    s = _game().new_initial_state()
    slots = load_components().setup.sawmill.hut_effect_slots
    assert f"({slots} tokens)" in ad.action_meta(s, A.encode("BUILD_HUT", 0))["label"]
    assert f"({slots - 1} tokens)" in ad.action_meta(s, A.encode("BUILD_HUT", 1))["label"]


# ---------------------------------------------------------------- A. view carries public items


def test_view_has_public_phase4_items_and_matches_state() -> None:
    ad = _adapter()
    comp = load_components()
    checked = 0
    for s in _sim(3, True, 2):
        st: Any = s
        if st.round < 3 or st.is_chance_node() or st.is_terminal():
            continue
        v = ad.view(s, 0)
        json.dumps(v)
        assert v["fodder_values"] == list(comp.setup.sawmill.fodder_slot_values)
        assert v["pw"]["row"] == list(st.draws.pw)
        assert v["buildings"]["supply"] == list(st.bld_supply)
        assert v["huts"]["built"] == st.hut_built and v["huts"]["spent"] == st.hut_spent
        for i, sv in enumerate(v["seats"]):
            assert sv["fodder"] == [st.fodder3[i], st.fodder2[i]]
            assert sv["buildings"] == list(st.held_buildings[i])
            assert sv["huts"] == dict(zip(("drying", "food", "worker"), st.huts[i], strict=True))
            assert [p["card"] for p in sv["plans"]] == [q[1] for q in st.plans if q[0] == i]
            assert "kind" in sv["small_storage"]
        for c in v["tasks"]["cards"]:
            t = comp.tasks[c["index"]]
            assert c["reward"] == t.reward and len(c["requirements"]) == len(t.requirements)
        checked += 1
        if checked > 50:
            break
    assert checked


def test_view_task_cards_cover_row_and_held() -> None:
    ad = _adapter()
    for s in _sim(2, False, 3):
        st: Any = s
        if st.is_chance_node() or st.is_terminal():
            continue
        v = ad.view(s, 1)
        have = {c["index"] for c in v["tasks"]["cards"]}
        assert set(st.task_row) <= have
        assert all(set(h) <= have for h in st.held_tasks)


def test_view_does_not_leak_other_seats_pick() -> None:
    """Two states differing only in P1's hidden pick give P0 identical views (new keys incl.)."""
    from tests.server.test_lignum_adapter import _after, _pk_state

    ad = _adapter()
    base = _pk_state(3)
    a = _after(base, [0])
    b = _after(base, [1])
    # P0 picked 0 vs 1 differs for P0 itself; compare P2's view of P0's pick instead.
    assert json.dumps(ad.view(a, 2), sort_keys=True) == json.dumps(ad.view(b, 2), sort_keys=True)


# ---------------------------------------------------------------- C. Phase 3 label fixes


def test_picks_round_label() -> None:
    """Revealed picks are labelled with the round they belong to (0 = setup)."""
    ad = _adapter()
    seen: dict[tuple[int, str], int] = {}
    for s in _sim(2, False, 4):
        st: Any = s
        if st.is_chance_node() or st.is_terminal():
            continue
        v = ad.view(s, 0)
        seen[(v["round"], v["phase"])] = v["log"][0]["round"]
    for (rnd, ph), lab in seen.items():
        if rnd == 1:
            assert lab == 0, (rnd, ph, lab)
        else:
            base = rnd - 1 if ph in ("RS", "PK") else rnd
            while base in (4, 8):  # winter rounds have no picks of their own
                base -= 1
            assert lab == base, (rnd, ph, lab)
    assert (2, "TR") in seen and seen[(2, "TR")] == 2


def test_winter_due_is_money_not_food() -> None:
    src = pathlib.Path("web/src/games/lignum/TextBoard.tsx").read_text()
    assert "Sawmill food due" not in src and "Shortfall money due" in src
