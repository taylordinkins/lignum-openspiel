"""Sawing / tasks / selling / drying helpers for unit-8 tests (R-054..R-059, R-063, R-082).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, on top of tests/support/woodwork.py.
Everything goes through the public API; there is no scenario loader in the harness, so every
state is reached by scripted play (`Steps`) from the seeded setup.

Fixed facts used (all from the spec / data files)
  * Seed 1 (2 players, both sides) lays out task_05 and task_10 face up (checked from the setup
    dump when this file was written; tests assert it again through the TAKE_TASK legality).
  * task_10 = [hardwood milled +0, firewood milled +0, firewood milled +1] (cards.yaml).
  * Every task card needs hardwood, which does not exist before round 2, so round-1/3 task tests
    place only the non-hardwood slots (partial completion, R-055).
  * Id formulas: ACTIONS 2/5: SAW(k,n) 214.., PLACE_TASK(s,r) = 231+3s+r, PLACE_JOINERY(k,q) =
    375+3k+q, SELL(z,p) = 396+6z+p, DRY_ENTER(p) = 432+p; piece p: 0 fw disk, 1 fw log, 2 sw disk,
    3 sw log, 4 hw disk, 5 hw log.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

from tests import harness as H
from tests.support import rounds as R
from tests.support import woodwork as W

SEED = 1
FW_DISK, FW_LOG, SW_DISK, SW_LOG, HW_DISK, HW_LOG = range(6)
PLACE_TASK_IDS = range(231, 375)
PLACE_JOINERY_IDS = range(375, 384)
SAW_IDS = range(214, 227)
SELL_IDS = range(396, 432)
DRY_IDS = range(432, 438)


def saw(k: int, n: int) -> int:
    """SAW(k, n): disk of kind k, n logs to the firewood storage (ACTIONS 5.3)."""
    off = n if k == 0 else (7 + n if k == 1 else 11 + n)
    return 214 + off


def place_task(slot: int, src: int = 0) -> int:
    return 231 + 3 * slot + src


def place_joinery(kind: int, q: int) -> int:
    return 375 + 3 * kind + q


def sell(zone: int, piece: int) -> int:
    return 396 + 6 * zone + piece


def dry_enter(piece: int) -> int:
    return 432 + piece


def _tasks() -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", R._yaml("cards.yaml")["tasks"])  # pyright: ignore[reportPrivateUsage]


def slot(task_id: str, req: int) -> int:
    """Flat requirement-slot index (ACTIONS 1.5): all earlier cards' requirements, then req."""
    base = 0
    for t in _tasks():
        if t["id"] == task_id:
            return base + req
        base += len(t["requirements"])
    raise KeyError(task_id)


def take_task(task_id: str) -> int:
    return R.TAKE_TASK0 + R.task_ids().index(task_id)


TASK = "task_10"
S_HW0, S_FW0, S_FW1 = slot(TASK, 0), slot(TASK, 1), slot(TASK, 2)  # hardwood+0, firewood+0, +1


# --------------------------------------------------------------------------- script builders


def r1_steps(
    n: int,
    j: bool,
    *,
    bearers: int = 0,
    woodcutters: int = 0,
    sawyers: int = 0,
    saws: int = 0,
    task: str | None = None,
    cuts: tuple[int, ...] = (),
    carries: tuple[int, ...] = (),
    sawing: tuple[tuple[int, int, int], ...] = (),
    seed: int = SEED,
    steps: W.Steps | None = None,
) -> W.Steps:
    """Round-1 script for seat 0: travel, W1 cuts (worker source per cut), W3 carries (0 sawing,
    1 sale), W4 sawing as (source, kind, n logs to storage)."""
    st = steps or W.Steps()
    visits: list[tuple[int, list[Any]]] = []
    for i in range(saws):
        visits.append((W.spot_loc(n, j, seed, "saw", i), []))
    if bearers:
        visits.append((R.loc(j, "bearers"), [R.HIRE_BEARER] * bearers + [H.DONE]))
    if woodcutters:
        visits.append((R.loc(j, "woodcutters"), [R.HIRE_WOODCUTTER] * woodcutters + [H.DONE]))
    if sawyers:
        visits.append((R.loc(j, "sawyers"), [R.HIRE_SAWYER] * sawyers + [H.DONE]))
    if task:
        visits.append((R.loc(j, "tasks"), [take_task(task)]))
    visits.sort(key=lambda v: v[0])
    plan: list[Any] = []
    for loc, acts in visits:
        plan += [H.MOVE_TO(loc), *acts]
    plan.append(R.MOVE_CLEARING)
    st.add(1, "TR", 0, *plan)
    for src in cuts:
        st.add(1, "W1", 0, W.Opt(W.assign(src)), W.first_take(W.FW))
    for dest in carries:
        st.add(1, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, dest))
    for src, k, nlogs in sawing:
        st.add(1, "W4", 0, W.Opt(W.assign(src)), saw(k, nlogs))
    return st


def one_disk_steps(j: bool, with_task: bool = False, nlogs: int = 0) -> W.Steps:
    """P0: 1 bearer, 1 free sawyer, the saw token; the mill worker cuts 1 firewood disk, the
    bearer takes it to the sawing area and the sawyer mills it (nlogs to storage, rest to sale)."""
    return r1_steps(
        2,
        j,
        bearers=1,
        sawyers=1,
        saws=1,
        task=TASK if with_task else None,
        cuts=(1,),
        carries=(0,),
        sawing=((0, 0, nlogs),),
    )


def two_pieces_steps(j: bool, nlogs: int = 0) -> W.Steps:
    """P0: 2 bearers, 1 woodcutter, free sawyer, saw token, task_10 not taken. Two firewood
    disks are cut (woodcutter, mill worker); one goes to the sawing area and is milled (nlogs to
    storage, rest to sale), the other goes unmilled to the sale area."""
    return r1_steps(
        2,
        j,
        bearers=2,
        woodcutters=1,
        sawyers=1,
        saws=1,
        cuts=(0, 1),
        carries=(0, 1),
        sawing=((0, 0, nlogs),),
    )


def chain_steps(
    j: bool,
    *,
    r2_place: bool = False,
    r2_sell: int = 0,
    joiner: bool = False,
    joinery_q: int | None = None,
) -> W.Steps:
    """Three-round chain with one firewood disk milled in round 1 into 4 logs in the sale area.

    R1 W7: 2 logs -> drying 1 (2 stay in the sale area).  R2 W5: optional task placement of a
    stage-0 slot from drying 1.  R2 W6: sell `r2_sell` logs from the sale area.  R2 TR: optional
    Joiner visit.  R3 W5: optional joinery placement (kind firewood, slot `joinery_q`).
    Holds task_10 from round 1."""
    st = one_disk_steps(j, with_task=True)
    st.add(1, "W7", 0, dry_enter(FW_LOG), dry_enter(FW_LOG))
    if joiner:
        st.add(2, "TR", 0, H.MOVE_TO(R.loc(j, "joiner")), R.MOVE_CLEARING)
    if r2_place:
        st.add(2, "W5", 0, place_task(S_FW0, 1))
    for _ in range(r2_sell):
        st.add(2, "W6", 0, sell(0, FW_LOG))
    if joinery_q is not None:
        st.add(3, "W5", 0, place_joinery(W.FW, joinery_q))
    return st


# --------------------------------------------------------------------------- reaching / reading

_N = {"n": 0}


def reach(
    steps: W.Steps,
    stop: tuple[int, str, int],
    key: Any,
    n: int = 2,
    j: bool = False,
    seed: int = SEED,
) -> Any:
    return W.reach(n, j, seed, steps, stop, key=key)


def p0(s: Any) -> dict[str, Any]:
    return W.me(s, 0)


def zone(s: Any, name: str) -> Counter[str]:
    return W.zone(W.snap(s), 0, name)


def drying(s: Any) -> list[Counter[str]]:
    d = cast("list[Any]", p0(s)["drying"])
    return [W.pm(x) for x in d]


def tasks(s: Any) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", p0(s)["tasks"])


def money(s: Any) -> int:
    return cast("int", p0(s)["money"])


def logs(kind: str, n: int) -> Counter[str]:
    return Counter({f"{kind}_log": n}) if n else Counter()


def legal_in(s: Any, rng: range) -> list[int]:
    return W.ids(s.legal_actions(), rng)


def finish_turn(s: Any) -> None:
    """DONE, then read results at the next turn boundary."""
    W.end_turn(s)
