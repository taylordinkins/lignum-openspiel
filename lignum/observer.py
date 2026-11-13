"""Observer with public and private parts (R-028..R-030).

The tensor never encodes the observing seat's id, so a public-only view is identical for every
seat and private-only fields stay all-zero until a pick exists (R-029). Strings of the
single-player view name the seat ("P<seat>", seats from 0); the public and full views do not.
Setup (draws and SP picks) is public; hidden round picks (R-038) fill ``private_picks``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pyspiel

from lignum.constants import CLEARING_LOC, NUM_AREAS
from lignum.rules import CRAFT_ORDER, SPOT_NAMES

if TYPE_CHECKING:
    from lignum.game import LignumGame, LignumState


class LignumObserver:
    """Implements R-028, R-029, R-030."""

    def __init__(
        self,
        game: LignumGame,
        iig_obs_type: pyspiel.IIGObservationType,
        params: dict[str, Any] | None,
    ) -> None:
        if params:
            raise ValueError(f"observation parameters not supported: {params}")
        from lignum.game import PHASE_NAMES

        self.private = iig_obs_type.private_info
        self.public = iig_obs_type.public_info
        self.recall = iig_obs_type.perfect_recall
        n = game.players
        d_tasks, d_pw, d_bld = game.tables.deck_sizes
        pieces: list[tuple[str, tuple[int, ...]]] = []
        if self.public:
            pieces += [
                ("joinery", (1,)),
                ("phase", (len(PHASE_NAMES),)),
                ("areas3", (NUM_AREAS,)),
                ("winter", (2, 8)),
                ("tasks_laid_out", (d_tasks,)),
                ("pw_laid_out", (d_pw,)),
                ("buildings", (d_bld,)),
                ("craft_drawn", (len(CRAFT_ORDER),)),
                ("path_tokens", (len(game.tables.token_spots), len(SPOT_NAMES))),
                ("setup_picks", (n, NUM_AREAS)),
                ("round", (8,)),
                ("area_wood", (NUM_AREAS, 3)),
                ("area_food", (NUM_AREAS,)),
                ("placement_discarded", (game.tables.placement_cards,)),
                ("craft_removed", (len(CRAFT_ORDER),)),
                ("money", (n,)),
                ("joiners", (n,)),
                ("seat_food", (n,)),
                ("path_joiner", (1,)),
                ("loans", (n,)),
                ("foreman", (n, CLEARING_LOC + 1)),
                ("slot", (n, n)),
                ("turn_order", (n, n)),
                ("to_move", (n,)),
                ("visit", (CLEARING_LOC + 1, 3)),
                ("hired", (n, 3)),
                ("path_workers", (5,)),
                ("fodder", (n, 2)),
                ("flags", (n, 2)),
                ("equip", (n, 4)),
                ("held_craft", (n, len(CRAFT_ORDER))),
                ("held_tasks", (n, d_tasks)),
                ("held_buildings", (n, d_bld)),
                ("woodpile", (n, 3)),
                ("river", (n, 3)),
                ("sawing", (n, 3)),
                ("sale", (n, 3)),
                ("sale_logs", (n, 3)),
                ("store", (n, 3)),
                ("drying", (n, 3, 6)),
                ("task_filled", (d_tasks,)),
                ("joinery_wood", (n, 3, 4)),
                ("small_storage", (n, 5)),
                ("worker_use", (n, 4)),
                ("wturn", (8,)),
                ("winter_order", (n, n)),
                ("pay", (3,)),
                ("pw_turn", (5,)),
                ("ot_queue", (n,)),
                ("cut_lost", (NUM_AREAS,)),
                ("fs_pending", (n,)),
                ("choosers", (n,)),
                ("huts", (n, 3)),
                ("hut_build", (5 + 3 + 4,)),
                ("plan_card", (n, game.tables.pw_pairs)),
                ("plan_target", (n, game.tables.pw_pairs)),
            ]
        if self.recall and self.public:  # D27: earlier rounds' revealed picks, one-hot per seat
            pieces.append(("pick_log", (8, n, NUM_AREAS)))
        if self.private != pyspiel.PrivateInfoType.NONE:
            pieces.append(("private_picks", (n, NUM_AREAS)))
        size = sum(int(np.prod(shape)) for _, shape in pieces)
        self.tensor = np.zeros(size, np.float32)
        self.dict: dict[str, np.ndarray] = {}
        index = 0
        for name, shape in pieces:
            length = int(np.prod(shape))
            self.dict[name] = self.tensor[index : index + length].reshape(shape)
            index += length

    def set_from(self, state: LignumState, player: int) -> None:
        self.tensor.fill(0)
        d = self.dict
        if self.public:
            d["joinery"][0] = float(state.joinery)
            d["phase"][state.phase] = 1
            for area in state.high_areas():
                d["areas3"][area] = 1
            dr = state.draws
            for year, w in enumerate(dr.winter):
                d["winter"][year][w] = 1
            for key, picks in (("tasks_laid_out", state.task_row), ("pw_laid_out", dr.pw)):
                for i in picks:
                    d[key][i] = 1
            for i in state.bld_supply:
                d["buildings"][i] = 1
            for x in dr.craft:
                d["craft_drawn"][x] += 1
            for spot, y in enumerate(state.path_tokens):
                if y >= 0:  # -1 = taken (R-042)
                    d["path_tokens"][spot][y] = 1
            for seat, area in enumerate(state.picks):
                d["setup_picks"][seat][area] = 1
            d["round"][state.round - 1] = 1
            for a, w in enumerate(state.wood):
                d["area_wood"][a][:] = w
            d["area_food"][:] = state.area_food
            for q in state.placement_discarded:
                d["placement_discarded"][q] = 1
            d["craft_removed"][:] = state.craft_removed
            d["money"][:] = state.money
            d["joiners"][:] = state.joiners
            d["seat_food"][:] = state.food
            d["path_joiner"][0] = state.path_joiner
            d["loans"][:] = state.loans
            for seat in range(state.n):
                d["foreman"][seat][state.foreman[seat]] = 1
                d["turn_order"][seat][state.turn_order.index(seat)] = 1
                if seat in state.clearing:
                    d["slot"][seat][state.clearing.index(seat)] = 1
                d["hired"][seat][:] = (
                    state.hired_w[seat],
                    state.hired_b[seat],
                    state.hired_s[seat],
                )
                d["fodder"][seat][:] = (state.fodder3[seat], state.fodder2[seat])
                d["flags"][seat][:] = (state.task_taken[seat], state.fodder_bought[seat])
                d["equip"][seat][:] = state.equip[seat]
                d["held_craft"][seat][:] = state.held_craft[seat]
                for c in state.held_tasks[seat]:
                    d["held_tasks"][seat][c] = 1
                for c in state.held_buildings[seat]:
                    d["held_buildings"][seat][c] = 1
                d["woodpile"][seat][:] = state.woodpile[seat]
                d["river"][seat][:] = state.river[seat]
                d["sawing"][seat][:] = state.sawing[seat]
                d["sale"][seat][:] = state.sale[seat]
                d["sale_logs"][seat][:] = state.sale_logs[seat]
                d["store"][seat][:] = state.store[seat]
                d["drying"][seat][:] = state.dry[seat]
                for slot, kind in enumerate(state.joinery_wood[seat]):
                    d["joinery_wood"][seat][slot][kind + 1] = 1  # index 0 = empty slot
                d["small_storage"][seat][state.small_storage[seat] + 1] = 1  # R-114; 0 = none
                d["worker_use"][seat][:] = (
                    state.mill_used[seat],
                    state.cut_used[seat],
                    state.bear_used[seat],
                    state.saw_used[seat],
                )
            d["task_filled"][:] = [f.bit_count() for f in state.filled]
            for pos, seat in enumerate(state.wint):
                d["winter_order"][seat][pos] = 1
            for seat in state.fs_pending:
                d["fs_pending"][seat] = 1
            for seat in state.choosers:
                d["choosers"][seat] = 1
            for seat, card, pair, target in state.plans:  # R-087: plans are public
                d["plan_card"][seat][pair - 1] = card + 1
                d["plan_target"][seat][pair - 1] = target
            for seat in range(state.n):
                d["huts"][seat][:] = state.huts[seat]
            for x in state.hb_tok:
                d["hut_build"][x] += 1
            for h in state.hb_area:
                d["hut_build"][5 + h] += 1
            d["hut_build"][8:] = (state.hb_open, state.win_closed, state.hut_built, state.hut_spent)
            d["pay"][:] = (state.pay, state.sf_due, state.round)
            d["wturn"][:] = (
                state.w_worker + 2,  # SRC_PAIR (-2) gets its own slot 0
                state.w_dirty,
                state.w_took,
                state.w_moved,
                state.trip_kind,
                state.trip_n,
                state.trip_cap,
                state.w_turn,
            )
            d["pw_turn"][:] = (state.w_ld, state.w_out, state.w_outa + 1, state.w_wc, 0)
            for pos, seat in enumerate(state.ot_q):
                d["ot_queue"][seat] = pos + 1
            for a in range(NUM_AREAS):
                d["cut_lost"][a] = state.cut_lost >> a & 1
            if not state.is_terminal() and not state.is_chance_node():
                d["to_move"][state.current_player()] = 1
            d["visit"][state.visit_loc][0] = 1
            d["visit"][state.visit_loc][1] = state.visit_n
            d["visit"][state.visit_loc][2] = state.visit_food
            d["path_workers"][:] = (
                state.path_b,
                state.path_w,
                state.path_sf,
                state.path_sp,
                state.path_fodder,
            )
        if self.recall and self.public:
            for r, row in enumerate(state.pick_log):
                for seat, area in enumerate(row):
                    d["pick_log"][r][seat][area] = 1
        if self.private != pyspiel.PrivateInfoType.NONE:
            for seat, area in self._visible_picks(state, player):
                d["private_picks"][seat][area] = 1

    def _visible_picks(self, state: LignumState, player: int) -> list[tuple[int, int]]:
        """Implements R-029: hidden round picks (R-038) visible to their owner or to all."""
        if self.private == pyspiel.PrivateInfoType.ALL_PLAYERS:
            return list(enumerate(state.pk))
        return [(seat, area) for seat, area in enumerate(state.pk) if seat == player]

    def string_from(self, state: LignumState, player: int) -> str:
        from lignum.game import PHASE_NAMES

        parts: list[str] = []
        join = ",".join
        # The seat is named only once it has private content (hidden picks, unit 5); setup is
        # entirely public, so every seat sees the same string (R-028).
        if self.public:
            parts.append(f"board {'joinery' if state.joinery else 'base'}")
            parts.append(f"phase {PHASE_NAMES[state.phase]}")
            dr = state.draws
            parts.append("areas3 " + join(map(str, state.high_areas())))
            parts.append("winter " + join(f"c{w // 2}h{w % 2}" for w in dr.winter))
            parts.append(f"round {state.round}")
            parts.append("tasks " + join(map(str, state.task_row)))
            parts.append("pw " + join(map(str, dr.pw)))
            parts.append("buildings " + join(map(str, state.bld_supply)))
            parts.append("craft " + join(CRAFT_ORDER[x] for x in dr.craft))
            parts.append(
                "tokens " + join(SPOT_NAMES[y] if y >= 0 else "-" for y in state.path_tokens)
            )
            parts.append("picks " + join(f"P{s}:{a}" for s, a in enumerate(state.picks)))
            parts.append("wood " + join("/".join(map(str, w)) for w in state.wood))
            parts.append("areafood " + join(map(str, state.area_food)))
            parts.append("placed " + join(map(str, state.placement_discarded)))
            parts.append("removed " + join(map(str, state.craft_removed)))
            parts.append("money " + join(map(str, state.money)))
            parts.append("joiners " + join(map(str, state.joiners)))
            parts.append("food " + join(map(str, state.food)))
            parts.append(f"pathjoiner {state.path_joiner}")
            parts.append("loans " + join(map(str, state.loans)))
            parts.append("order " + join(map(str, state.turn_order)))
            parts.append("foremen " + join(map(str, state.foreman)))
            parts.append("clearing " + join(map(str, state.clearing)))
            if not state.is_terminal() and not state.is_chance_node():
                parts.append(f"to_move {state.current_player()}")
            parts.append(f"visit {state.visit_loc}/{state.visit_n}/{state.visit_food}")
            parts.append(
                "path "
                + join(map(str, (state.path_b, state.path_w, state.path_sf, state.path_sp)))
                + f" fodder {state.path_fodder}"
            )
            for seat in range(state.n):
                parts.append(
                    f"P{seat} hired"
                    f" {state.hired_b[seat]}/{state.hired_w[seat]}/{state.hired_s[seat]}"
                    f" fodder {state.fodder3[seat]}{state.fodder2[seat]}"
                    f" flags {state.task_taken[seat]}{state.fodder_bought[seat]}"
                    f" equip {join(map(str, state.equip[seat]))}"
                    f" craft {join(map(str, state.held_craft[seat]))}"
                    f" tasks {join(map(str, state.held_tasks[seat]))}"
                    + (
                        f" bld {join(map(str, state.held_buildings[seat]))}"
                        if state.held_buildings[seat]
                        else ""
                    )
                )
            for seat in range(state.n):
                parts.append(
                    f"P{seat} wood pile {join(map(str, state.woodpile[seat]))}"
                    f" river {join(map(str, state.river[seat]))}"
                    f" saw {join(map(str, state.sawing[seat]))}"
                    f" sale {join(map(str, state.sale[seat]))}"
                    f" salelogs {join(map(str, state.sale_logs[seat]))}"
                    f" store {join(map(str, state.store[seat]))}"
                    f" dry {'/'.join(join(map(str, a)) for a in state.dry[seat])}"
                    f" joinery {join(map(str, state.joinery_wood[seat]))}"
                    f" used {state.mill_used[seat]}{state.cut_used[seat]}{state.bear_used[seat]}"
                    f"{state.saw_used[seat]}"
                    + (
                        f" storage {state.small_storage[seat]}"
                        if state.small_storage[seat] >= 0
                        else ""
                    )
                    + (f" wcut {state.wcut[seat]}" if state.wcut[seat] else "")
                    + (f" huts {join(map(str, state.huts[seat]))}" if any(state.huts[seat]) else "")
                )
            if state.hb_open or state.hut_built or state.win_closed:  # omitted until needed
                parts.append(
                    f"hutbuild {state.hb_open} {join(map(str, state.hb_tok))}"
                    f"/{join(map(str, state.hb_area))} closed {state.win_closed}"
                    f" built {state.hut_built} spent {state.hut_spent}"
                )
            parts.append("filled " + join(map(str, state.filled)))
            parts.append(
                f"wturn {state.w_turn} worker {state.w_worker} dirty {state.w_dirty}"
                f" took {state.w_took} moved {state.w_moved}"
                f" trip {state.trip_kind}/{state.trip_n}/{state.trip_cap}"
            )
            if (
                state.w_ld or state.w_out or state.w_wc or state.cut_lost or state.ot_q
            ):  # omitted until used
                parts.append(
                    f"pwturn ld {state.w_ld} out {state.w_out}@{state.w_outa} wc {state.w_wc}"
                    f" lost {state.cut_lost} ot {join(map(str, state.ot_q))}"
                )
            parts.append(f"pk {len(state.pk)}")
            parts.append(
                f"fs {join(map(str, state.fs_pending))} choosers {join(map(str, state.choosers))}"
            )
            parts.append(
                f"winter order {join(map(str, state.wint))} pay {state.pay} due {state.sf_due}"
            )
            parts.append("plans " + join(f"P{s}:{c}/{p}/{t}" for s, c, p, t in state.plans))
            rd = state.rd
            if rd is not None:
                parts.append(
                    f"rs {rd.pos} t{join(map(str, rd.new_tasks))} c{join(map(str, rd.craft))}"
                    f" s{join(map(str, rd.spots))} p{join(map(str, rd.cards))}"
                )
        if self.recall and self.public and state.pick_log:
            parts.append("log " + ";".join(join(map(str, row)) for row in state.pick_log))
        if self.private != pyspiel.PrivateInfoType.NONE:
            hidden = self._visible_picks(state, player)
            if hidden:
                parts.append("hidden " + join(f"P{s}:{a}" for s, a in hidden))
        return " | ".join(parts)
