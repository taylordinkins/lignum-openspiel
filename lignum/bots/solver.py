"""Own-turn solver (Phase 7 unit 5b): search one seat's wood-work turn as a sequence of actions.

A wood-work turn (W1..W7) has no chance node and no other seat's decision (unit 5a). It ends when
the seat plays DONE, or the state reaches a terminal / chance node, or ``(phase, w_turn)`` changes
(W2 auto-end, a following seat's turn); never on a ``current_player()`` change alone, since the
same seat can start back-to-back turns. Search is level by level over the seat's own actions with
transposition merging: while no level exceeds ``beam`` states and the ``node_cap`` holds, every
sequence is covered (``Plan.exhaustive``); otherwise the ``beam`` best states by the leaf score
survive each level. Deterministic: actions come in the order ``expand`` returns (the heuristic
sorts them), ties keep the shorter plan, then the earlier one. Scores and caps come from the
profile (``solver:`` in the bot YAML); no card values here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lignum import actions as A
from lignum.game import PHASE_W1, PHASE_W7, LignumState

WOOD_WORK_PHASES = frozenset(range(PHASE_W1, PHASE_W7 + 1))


@dataclass(frozen=True)
class Plan:
    actions: tuple[int, ...]  # the best own-turn action sequence (first entry is the move)
    score: float
    nodes: int  # actions applied during the search (<= node_cap)
    exhaustive: bool  # no pruning and the cap never bit: the result is the true optimum


def turn_over(state: LignumState, action: int, seat: int, key: tuple[int, int]) -> bool:
    """Whether ``state`` (reached by ``action`` from a position of ``seat`` with ``key`` =
    ``(phase, w_turn)``) is past the seat's turn."""
    return (
        action == A.DONE
        or state.is_terminal()
        or state.is_chance_node()
        or state.current_player() != seat
        or (state.phase, state.w_turn) != key
    )


def solve_turn(
    state: LignumState,
    seat: int,
    expand: Callable[[LignumState], list[int]],
    score: Callable[[LignumState], float],
    beam: int,
    node_cap: int,
    max_depth: int,
) -> Plan | None:
    """Best own-turn sequence from ``state`` (None if ``expand`` offers nothing)."""
    key = (state.phase, state.w_turn)
    frontier: list[tuple[LignumState, tuple[int, ...], float]] = [(state, (), 0.0)]
    best: tuple[float, int, tuple[int, ...]] | None = None  # (score, -len, seq) maximised
    nodes = 0
    exhaustive = True

    def consider(s: float, seq: tuple[int, ...]) -> None:
        nonlocal best
        if not seq:
            return
        if best is None or (s, -len(seq)) > (best[0], best[1]):
            best = (s, -len(seq), seq)

    for depth in range(max_depth):
        nxt: list[tuple[LignumState, tuple[int, ...], float]] = []
        seen: set[str] = set()
        for fi, (node, seq, _) in enumerate(frontier):
            for a in expand(node):
                if nodes >= node_cap:
                    exhaustive = False
                    for _, useq, us in frontier[fi:]:  # not (fully) expanded: score where it stands
                        consider(us, useq)
                    break
                nodes += 1
                child = node.search_clone()
                child.fast_apply = True
                child.apply_action(a)
                s = score(child)
                cseq = (*seq, a)
                if turn_over(child, a, seat, key):
                    consider(s, cseq)
                    continue
                k = str(child)
                if k in seen:
                    continue
                seen.add(k)
                nxt.append((child, cseq, s))
            else:
                continue
            break
        if len(nxt) > beam:
            exhaustive = False
            nxt = sorted(nxt, key=lambda x: -x[2])[:beam]  # stable: earlier action wins ties
        if not nxt:
            break
        frontier = nxt
        if depth == max_depth - 1 or nodes >= node_cap:
            exhaustive = False  # nxt is non-empty here: a frontier is left unexpanded
            for _, seq, s in nxt:  # unfinished turns are scored where they stand
                consider(s, seq)
            break
    if best is None:
        return None
    return Plan(best[2], best[0], nodes, exhaustive)
