"""State encoding for the AZ net, from the point of view of one seat (2-4 players).

The engine's single-player observer tensor (R-028..R-030: only the seat's own hidden pick), with
every seat-indexed field rotated so the encoding seat comes first, plus a few strategist planning
quantities per seat (food and heat shortfalls, hardwood and softwood supply, open task slots) and
the strategist's value of each laid-out task. No hidden information is read.
"""

from __future__ import annotations

import numpy as np
import pyspiel

from lignum.bots.strategist import (
    DEFAULT_WEIGHTS,
    FW,
    HW,
    SW,
    Ctx,
    hw_certain,
    hw_committed,
    hw_supply,
    r8_kit,
    sw_supply_logs,
    task_value,
)
from lignum.game import LignumGame, LignumState
from lignum.observer import LignumObserver

# Observer fields whose first axis is the seat.
SEAT_FIELDS = (
    "setup_picks",
    "money",
    "joiners",
    "seat_food",
    "loans",
    "foreman",
    "slot",
    "turn_order",
    "to_move",
    "hired",
    "fodder",
    "flags",
    "equip",
    "held_craft",
    "held_tasks",
    "held_buildings",
    "woodpile",
    "river",
    "sawing",
    "sale",
    "sale_logs",
    "store",
    "drying",
    "joinery_wood",
    "small_storage",
    "worker_use",
    "winter_order",
    "ot_queue",
    "fs_pending",
    "choosers",
    "huts",
    "plan_card",
    "plan_target",
    "private_picks",
)
N_SEAT_FEATS = 17
N_TASKS = 19


class Encoder:
    """Reusable encoder for one game (one observer buffer, not thread safe)."""

    def __init__(self, game: pyspiel.Game) -> None:
        assert isinstance(game, LignumGame)
        self.n = game.players
        self.obs = LignumObserver(
            game,
            pyspiel.IIGObservationType(
                perfect_recall=False,
                public_info=True,
                private_info=pyspiel.PrivateInfoType.SINGLE_PLAYER,
            ),
            None,
        )
        self.obs_size = len(self.obs.tensor)
        self.size = self.obs_size + self.n * N_SEAT_FEATS + N_TASKS + 1

    def encode(self, state: LignumState, seat: int) -> np.ndarray:
        out = np.zeros(self.size, np.float32)
        self.encode_into(state, seat, out)
        return out

    def encode_into(self, state: LignumState, seat: int, out: np.ndarray) -> None:
        obs = self.obs
        obs.set_from(state, seat)
        n = self.n
        order = [(seat + k) % n for k in range(n)]
        if seat:
            for name in SEAT_FIELDS:
                a = obs.dict[name]
                a[:] = a[order].copy()
        out[: self.obs_size] = obs.tensor
        i = self.obs_size
        for k, s in enumerate(order):
            out[i : i + N_SEAT_FEATS] = seat_feats(state, s)
            i += N_SEAT_FEATS
            if k == 0:
                tv = task_feats(state, s)
                out[i : i + N_TASKS] = tv
                i += N_TASKS
        out[i] = state.round / 8.0


def seat_feats(state: LignumState, seat: int) -> np.ndarray:
    v = np.zeros(N_SEAT_FEATS, np.float32)
    if not state.picks or state.is_terminal():
        return v
    try:
        c = Ctx(state, seat, DEFAULT_WEIGHTS)
        plan = c.slot_plan()
        slots = c.open_slots()
        live = [s for s in slots if s.task not in plan.dead]
        v[:] = (
            c.food_short(),
            c.heat_short(),
            c.heat_short(next_only=True),
            hw_supply(c),
            hw_committed(c),
            hw_certain(c),
            sw_supply_logs(c),
            plan.need_logs(FW, -1),
            plan.need_logs(SW, -1),
            plan.need_logs(HW, -1),
            len(live),
            sum({s.task: s.reward for s in live}.values()) / 10.0,
            len(plan.dead),
            r8_kit(c),
            c.cur_opp(),
            c.seasonal_left(),
            sum(plan.reserved.values()),
        )
    except Exception:  # noqa: BLE001 - features are advisory; never break a search
        pass
    return v


def task_feats(state: LignumState, seat: int) -> np.ndarray:
    v = np.zeros(N_TASKS, np.float32)
    if not state.picks or state.is_terminal():
        return v
    try:
        c = Ctx(state, seat, DEFAULT_WEIGHTS)
        for t in state.task_row:
            v[t] = max(-10.0, task_value(c, t)) / 10.0
    except Exception:  # noqa: BLE001
        pass
    return v


__all__ = ["Encoder", "FW", "SW", "HW"]
