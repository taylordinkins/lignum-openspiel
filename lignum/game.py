"""OpenSpiel adapter: LignumGame / LignumState (Phase 2, units 2-13: setup through final scoring).

Implements R-001 (parameters), R-003 (player counts), R-012..R-020 and R-026/R-027/R-031 (setup:
chance run SC, public picks SP, round 1 at TR), R-032 (terminology, seats from 0). The setup
rules live in ``lignum.rules``; later units add the rounds after TR.

Unit 4 (R-033..R-037, R-062, R-063, R-078..R-080) adds the round-start chance run (RS), the
hidden picks (PK, minimal: R-038/R-039 land fully in unit 5) and the Joiner location.

Unit 6 (R-021..R-025, R-040..R-044, R-076) adds the supply-path travel phase. Unit 7 adds the
wood-work phases W1 woodcutting, W2 log driving and W3 transportation (R-045..R-053). Unit 8 adds
W4 sawing, W5 tasks and joinery wood, W6 selling and W7 drying (R-054..R-059, R-063, R-082).
Unit 9 adds the order and cleanup (R-060, R-061). Unit 10 adds winter rounds 4 and 8 (R-064..
R-074: bonus, N1..N4 turns, automatic feeding and heating, the SF shortfall) and loans in them
(R-075..R-077). The end of round 8 runs the final sale, scoring and returns (R-081..R-086).
"""

from __future__ import annotations

from functools import cache
from typing import Any, cast

import pyspiel

from lignum import actions as A
from lignum.components import Components, load_components
from lignum.constants import (
    CLEARING_LOC,
    MAX_CHANCE_OUTCOMES,
    MAX_PLAYERS,
    MIN_PLAYERS,
    NUM_AREAS,
    NUM_DISTINCT_ACTIONS,
)
from lignum.huts import (
    HB_PW,
    HUT_DRYING,
    HUT_FOOD,
    HUT_NAMES,
    HUT_WORKER,
    build_actions,
    build_size,
    window_actions,
)
from lignum.rules import (
    CRAFT_ORDER,
    EQUIP_SLOTS,
    FIRST_CRAFT_SPOT,
    MULTI_UNIT_KINDS,
    SPOT_NAMES,
    RoundDraws,
    SetupDraws,
    SetupTables,
    apply_placement,
    build_tables,
    building_param,
    craft_price,
    distribute_food,
    fodder_cost,
    has_building,
    legal_destinations,
    plan_active,
    plan_cost,
    plan_param,
    start_round_draws,
    visit_options,
)
from lignum.woodwork import (
    HARDWOOD,
    IDX_RAFT,
    IDX_SAW,
    IDX_SLEDGE,
    IDX_WAGON,
    NO_SLOT,
    SRC_HUT,
    SRC_MILL,
    SRC_PAIR,
    STORAGE_SPENT,
    TRIP_NONE,
    TRIP_PW,
    TRIP_RAFT,
    TRIP_SLEDGE,
    TRIP_WAGON,
    ZERO6,
    n1_actions,
    n2_actions,
    n4_actions,
    nb_actions,
    overtime_actions,
    piece_idx,
    saw_yield,
    sf_actions,
    w1_actions,
    w2_actions,
    w3_actions,
    w4_actions,
    w5_actions,
    w6_actions,
    w7_actions,
    zone_count,
)

SHORT_NAME = "python_lignum"
DEFAULT_PARAMS: dict[str, Any] = {
    "players": 2,
    "joinery": True,
    "returns": "win_loss",
    "easy_winter": False,
}
RETURNS_MODES = ("win_loss", "margin")

# State phase codes (ACTIONS 4). Later units add the rest after PHASE_TR.
PHASE_SC = 0  # setup chance run (R-012, R-026)
PHASE_SP = 1  # public cutting-area token placement in seat order (R-015)
PHASE_TR = 2  # supply-path travel; round 1 starts here (R-020)
PHASE_END = 3  # terminal: after the final sale and scoring (R-081..R-083)
PHASE_RS = 4  # round-start chance run, rounds 2.. (R-034, R-035, R-062)
PHASE_PK = 5  # hidden cutting-area picks, rounds 2.. (R-038)
PHASE_W1 = 6  # woodcutting (R-047, R-048)
PHASE_W2 = 7  # log driving, wood arrival (R-049)
PHASE_W3 = 8  # transportation (R-050..R-053)
PHASE_W4 = 9  # sawing (R-054)
PHASE_W5 = 10  # tasks and joinery wood (R-055..R-057)
PHASE_W6 = 11  # selling (R-058)
PHASE_W7 = 12  # drying (R-059)
PHASE_WS = 13  # winter start: PW Overtime option (Phase 4; never entered in Phase 2)
PHASE_NB = 14  # winter bonus (R-065)
PHASE_N1 = 15  # winter woodcutting (R-066)
PHASE_N2 = 16  # transportation by sledge (R-067)
PHASE_N3 = 17  # sawing (R-068)
PHASE_N4 = 18  # tasks (R-069)
PHASE_N5 = 19  # feeding, automatic (R-071)
PHASE_N6 = 20  # heating, automatic (R-072)
PHASE_SF = 21  # shortfall payment (R-073)
PHASE_FS = 22  # final sale river choice (unit 11)
PHASE_NAMES = (
    "SC", "SP", "TR", "END", "RS", "PK", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
    "WS", "NB", "N1", "N2", "N3", "N4", "N5", "N6", "SF", "FS",
)  # fmt: skip
HUT_WINDOW_PHASES = (  # ACTIONS 4 matrix: turns with a hut window (TR is handled separately)
    PHASE_W1, PHASE_W2, PHASE_W3, PHASE_W4, PHASE_W5, PHASE_W6, PHASE_W7,
    PHASE_N1, PHASE_N2, PHASE_N3, PHASE_N4,
)  # fmt: skip
W_PHASES = (PHASE_W1, PHASE_W2, PHASE_W3, PHASE_W4, PHASE_W5, PHASE_W6, PHASE_W7)
N_PHASES = (PHASE_NB, PHASE_N1, PHASE_N2, PHASE_N3, PHASE_N4)  # winter turn phases
WINTER_TURNS = (*N_PHASES, PHASE_SF)  # phases in which a winter seat acts, in ``wint`` order
FEED, HEAT = 0, 1
ZERO3 = (0, 0, 0)

# Loose upper bounds (ACTIONS 2: setup chance <= 37, whole game <= 152 chance nodes).
MAX_CHANCE_NODES = 152
MAX_DECISIONS = 3000

_GAME_TYPE_BASE = {
    "short_name": SHORT_NAME,
    "long_name": "Lignum",
    "dynamics": pyspiel.GameType.Dynamics.SEQUENTIAL,
    "chance_mode": pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    "information": pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    "reward_model": pyspiel.GameType.RewardModel.TERMINAL,
    "min_num_players": MIN_PLAYERS,
    "max_num_players": MAX_PLAYERS,
    "provides_information_state_string": True,
    "provides_information_state_tensor": True,
    "provides_observation_string": True,
    "provides_observation_tensor": True,
    "parameter_specification": dict(DEFAULT_PARAMS),
}


def _game_type(returns: str) -> pyspiel.GameType:
    utility = (
        pyspiel.GameType.Utility.ZERO_SUM
        if returns == "win_loss"
        else pyspiel.GameType.Utility.GENERAL_SUM
    )
    return pyspiel.GameType(utility=utility, **_GAME_TYPE_BASE)  # type: ignore[arg-type]


@cache
def _components() -> Components:
    return load_components()


def _parse_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "false"):
        return str(value).lower() == "true"
    raise ValueError(f"{name} must be true or false, got {value!r}")


def _bump(values: tuple[int, ...], index: int, delta: int) -> tuple[int, ...]:
    return values[:index] + (values[index] + delta,) + values[index + 1 :]


def _put(values: tuple[int, ...], index: int, value: int) -> tuple[int, ...]:
    return values[:index] + (value,) + values[index + 1 :]


def _bump2(
    rows: tuple[tuple[int, ...], ...], seat: int, col: int, delta: int
) -> tuple[tuple[int, ...], ...]:
    return rows[:seat] + (_bump(rows[seat], col, delta),) + rows[seat + 1 :]


def _add3(c: tuple[int, int, int], kind: int, delta: int) -> tuple[int, int, int]:
    """Wood counts (firewood, softwood, hardwood) with ``kind`` changed by ``delta``."""
    return (c[0] + (kind == 0) * delta, c[1] + (kind == 1) * delta, c[2] + (kind == 2) * delta)


def _zone(
    rows: tuple[tuple[int, int, int], ...], seat: int, kind: int, delta: int
) -> tuple[tuple[int, int, int], ...]:
    return rows[:seat] + (_add3(rows[seat], kind, delta),) + rows[seat + 1 :]


# Static tables by (players, joinery, easy_winter): states look them up without get_game().
_TABLES: dict[tuple[int, bool, bool], SetupTables] = {}


_GAMES: dict[tuple[int, bool, bool, str], LignumGame] = {}


class LignumGame(pyspiel.Game):
    """Implements R-001, R-003."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = {**DEFAULT_PARAMS, **dict(params or {})}
        players = int(p["players"])
        if not MIN_PLAYERS <= players <= MAX_PLAYERS:
            raise ValueError(f"players must be {MIN_PLAYERS}..{MAX_PLAYERS}, got {players}")
        returns = p["returns"]
        if returns not in RETURNS_MODES:
            raise ValueError(f"returns must be one of {RETURNS_MODES}, got {returns!r}")
        self.players = players
        self.joinery = _parse_bool(p["joinery"], "joinery")
        self.returns_mode = returns
        self.easy_winter = _parse_bool(p["easy_winter"], "easy_winter")
        # Static tables, kept on the game (never the state).
        self.tables: SetupTables = build_tables(
            _components(), players, self.joinery, self.easy_winter
        )
        _TABLES[(players, self.joinery, self.easy_winter)] = self.tables
        _GAMES[(players, self.joinery, self.easy_winter, returns)] = self
        info = pyspiel.GameInfo(
            num_distinct_actions=NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=MAX_CHANCE_OUTCOMES,
            num_players=players,
            min_utility=-1.0 if returns == "margin" else -1.0 / (players - 1),
            max_utility=1.0,
            utility_sum=None if returns == "margin" else 0.0,  # GENERAL_SUM has no sum (R-086)
            max_game_length=MAX_DECISIONS,
        )
        super().__init__(
            _game_type(returns),
            info,
            {
                "players": players,
                "joinery": self.joinery,
                "returns": returns,
                "easy_winter": self.easy_winter,
            },
        )

    def max_chance_nodes_in_history(self) -> int:
        return MAX_CHANCE_NODES

    def new_initial_state(self) -> LignumState:
        return LignumState(self)

    def make_py_observer(
        self,
        iig_obs_type: pyspiel.IIGObservationType | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        from lignum.observer import LignumObserver

        return LignumObserver(
            self, iig_obs_type or pyspiel.IIGObservationType(perfect_recall=False), params
        )

    def full_observer(self) -> Any:
        """Cached full-information observer used by State.__str__ (R-030)."""
        cached = self.__dict__.get("_full_observer")
        if cached is None:
            cached = self.make_py_observer(
                pyspiel.IIGObservationType(
                    public_info=True,
                    perfect_recall=False,
                    private_info=pyspiel.PrivateInfoType.ALL_PLAYERS,
                )
            )
            self.__dict__["_full_observer"] = cached
        return cached


class LignumState(pyspiel.State):
    """Small state: ints, tuples and frozen dataclasses (cloned by a shallow __dict__ copy).

    Every field is an immutable value replaced (never mutated) on change, so clones share them.
    ``fast_apply`` (default False) skips the legality re-check in ``_apply_*``; for search on
    clones whose actions come from ``legal_actions()``. It is carried over by clone().
    """

    fast_apply = False

    def __init__(self, game: LignumGame) -> None:
        super().__init__(game)
        n = game.players
        self.n = n
        self.joinery = game.joinery
        self._tkey = (n, game.joinery, game.easy_winter)
        self._gkey = (*self._tkey, game.returns_mode)
        self.phase = PHASE_SC
        self.round = 1
        self.draws = SetupDraws()  # public setup chance results (R-026)
        self.picks: tuple[int, ...] = ()  # cutting area per seat: setup picks, then revealed picks
        # Revealed picks of earlier rounds, oldest first; read only by the recall observer (D27).
        self.pick_log: tuple[tuple[int, ...], ...] = ()
        self.pk: tuple[int, ...] = ()  # hidden picks of the current round so far (R-038)
        self.rd: RoundDraws | None = None  # chance run of the round start (R-062)
        # Board state (public, R-028). Synced from the setup draws during SC.
        self.task_row: tuple[int, ...] = ()  # laid-out task cards, sorted (R-036)
        self.tasks_seen: tuple[int, ...] = ()  # task cards drawn so far (laid out or held)
        self.craft_pile: tuple[int, ...] = ()  # craftwork pile counts in CRAFT_ORDER (R-035)
        self.craft_removed: tuple[int, ...] = (0,) * len(CRAFT_ORDER)
        self.path_tokens: tuple[int, ...] = ()  # SPOT_TOKEN y per token spot, in spot order
        self.placement_discarded: tuple[int, ...] = ()  # sorted (R-037)
        self.wood: tuple[tuple[int, int, int], ...] = ()  # (fw, sw, hw) per cutting area
        self.area_food: tuple[int, ...] = (0,) * NUM_AREAS
        self.path_joiner = 0  # joiners on the Joiner location (R-035, R-078)
        # Per seat.
        self.money: tuple[int, ...] = (_components().setup.starting_holdings.money,) * n
        self.joiners: tuple[int, ...] = (0,) * n
        self.held_buildings: tuple[tuple[int, ...], ...] = ((),) * n  # R-106, permanent
        self.food: tuple[int, ...] = (0,) * n
        self.loans: tuple[int, ...] = (0,) * n  # R-075
        self.fs_pending: tuple[int, ...] = ()  # seats still to choose a river kind (R-081)
        self.choosers: tuple[int, ...] = ()  # seats that had a river choice (already sold)
        self.final: tuple[int, ...] = ()  # final dollars per seat once terminal (R-083)
        self.turn_order: tuple[int, ...] = tuple(range(n))  # starting-player track (R-040, R-060)
        # Supply path (R-035, R-041), refilled each round start.
        tb = self._tables()
        self.path_b = tb.path_bearers
        self.path_w = tb.path_woodcutters
        self.path_sf = tb.path_sawyers_free
        self.path_sp = tb.path_sawyers_paid
        self.path_fodder = tb.path_fodder
        # Travel (R-040, R-044): foreman location per seat (0 start, CLEARING_LOC = clearing).
        self.foreman: tuple[int, ...] = (0,) * n
        self.clearing: tuple[int, ...] = ()  # seats in slot order A, B, C, D
        self.tr_seat = 0  # seat to act in TR
        self.visit_loc = 0  # location of the open visit, 0 at a turn boundary
        self.visit_n = 0  # acquisitions made in the open visit
        self.visit_food = 0  # Market visit: 1 food bought, 2 food sold (no mixing, 2026-11-07)
        # Planned work plans (R-087): (seat, card, pair, target round), in the order made.
        self.plans: tuple[tuple[int, int, int, int], ...] = ()
        # Per-seat holdings and round flags (R-041..R-043).
        self.hired_b: tuple[int, ...] = (0,) * n
        self.hired_w: tuple[int, ...] = (0,) * n
        self.hired_s: tuple[int, ...] = (0,) * n
        self.fodder3: tuple[int, ...] = (0,) * n  # value-3 fodder slot occupied
        self.fodder2: tuple[int, ...] = (0,) * n  # value-2 fodder slot occupied
        self.fodder_bought: tuple[int, ...] = (0,) * n
        self.task_taken: tuple[int, ...] = (0,) * n
        self.held_tasks: tuple[tuple[int, ...], ...] = ((),) * n
        self.equip: tuple[tuple[int, int, int, int], ...] = ((0, 0, 0, 0),) * n  # EQUIP_SLOTS
        self.held_craft: tuple[tuple[int, ...], ...] = ((0,) * len(CRAFT_ORDER),) * n
        # Huts (R-100): unspent tokens per seat on the drying, food and worker areas; the open
        # build's chosen token types and areas; flipped / spent totals (token conservation).
        self.huts: tuple[tuple[int, int, int], ...] = ((0, 0, 0),) * n
        self.hb_open = 0
        self.hb_tok: tuple[int, ...] = ()
        self.hb_area: tuple[int, ...] = ()
        self.hut_built = 0
        self.hut_spent = 0
        self.w_turn = 0  # index into ``clearing`` (``wint`` in winter) of the seat to act
        # Winter (R-064): fall clearing order kept as the turn order; payment progress (R-071..73).
        self.wint: tuple[int, ...] = ()
        self.pay = FEED  # which payment (feeding or heating) N5/N6/SF is working on
        self.sf_due = 0  # money due in the open shortfall (R-073)
        # Wood zones per seat as (firewood, softwood, hardwood) disk counts (R-046).
        self.woodpile: tuple[tuple[int, int, int], ...] = (ZERO3,) * n
        self.river: tuple[tuple[int, int, int], ...] = (ZERO3,) * n
        self.sawing: tuple[tuple[int, int, int], ...] = (ZERO3,) * n
        self.sale: tuple[tuple[int, int, int], ...] = (ZERO3,) * n  # unmilled disks
        self.sale_logs: tuple[tuple[int, int, int], ...] = (ZERO3,) * n  # milled logs
        self.store: tuple[tuple[int, int, int], ...] = (ZERO3,) * n  # firewood storage logs
        # Drying areas 1..3 per seat, each a 6-vector: disks (fw, sw, hw) then logs (fw, sw, hw).
        self.dry: tuple[tuple[tuple[int, ...], ...], ...] = ((ZERO6,) * 3,) * n
        self.filled: tuple[int, ...] = (0,) * len(_components().tasks)  # bitmask per task card
        self.joinery_wood: tuple[tuple[int, ...], ...] = ((NO_SLOT,) * 3,) * n
        # R-114 Small Storage Area per seat: NO_SLOT = empty and unused, 0..2 = the milled kind
        # held, STORAGE_SPENT = the piece has been moved to a task (never refilled)
        self.small_storage: tuple[int, ...] = (NO_SLOT,) * n
        # Workers used this round (R-045 mill worker; hired woodcutters and bearers).
        self.mill_used: tuple[int, ...] = (0,) * n
        self.cut_used: tuple[int, ...] = (0,) * n
        self.bear_used: tuple[int, ...] = (0,) * n
        self.saw_used: tuple[int, ...] = (0,) * n
        self.wcut: tuple[int, ...] = (0,) * n  # winter woodcutting actions taken (R-066)
        # Turn-local state of the acting seat in W1/W3 (reset when its turn ends).
        self.win_closed = 0  # the hut window is closed: a non-hut, non-loan action was played
        self.w_worker = -1  # committed worker source (ACTIONS 5.2), -1 none
        self.w_dirty = 0  # the seat has acted this turn (loans excluded): not a turn boundary
        self.w_took = 0  # took wood this turn (no more token moves, R-048)
        self.w_moved = 0  # moved its cutting token this turn
        self.trip_kind = TRIP_NONE
        self.trip_n = 0  # pieces moved in the open trip
        self.trip_cap = 0  # wagon trip capacity (R-052)
        self.w_ld = 0  # PW Log Driving trip used this turn (R-098)
        self.w_wc = 0  # Waterchannel pieces used this transport phase (R-107)
        self.w_out = 0  # workers sent into another cutting area this turn (R-099)
        self.w_outa = -1  # that other area, -1 none
        self.cut_lost = 0  # bitmask of cutting areas reduced by an outside take this round (R-099)
        # PW Overtime holders still to decide at RS / WS, in starting-player order (R-097).
        self.ot_q: tuple[int, ...] = ()

    def _tables(self) -> SetupTables:
        return _TABLES[self._tkey]

    def search_clone(self) -> LignumState:
        """Fast clone for search and rollouts: fresh C++ base, so no history (bots need none).

        Shares the immutable ``__dict__`` values and carries ``fast_apply`` over. Use ``clone()``
        when history, move_number or serialize() must match the original.
        """
        new = type(self).__new__(type(self))
        pyspiel.State.__init__(new, _GAMES[self._gkey])
        new.__dict__.update(self.__dict__)
        return new

    def clone(self) -> LignumState:
        """Exact copy (history, move_number, serialize round-trip), via the C++ clone."""
        return cast(LignumState, pyspiel.State.clone(self))

    def high_areas(self) -> tuple[int, ...]:
        """Areas that started with 3 firewood (empty before AREAS3)."""
        return self.draws.high_areas(self._tables())

    def _sync_from_setup(self) -> None:
        """Copy the setup chance results into the board state (R-014, R-020)."""
        t = self._tables()
        dr = self.draws
        self.task_row = dr.tasks
        self.tasks_seen = dr.tasks
        self.craft_pile = tuple(t.craft_totals[x] - dr.craft.count(x) for x in range(5))
        self.path_tokens = dr.spots
        fw = dr.firewood(t)
        self.wood = tuple((fw[a], 0, 0) for a in range(NUM_AREAS))
        self.path_joiner = 1 if self.joinery and dr.done(t) else 0

    @property
    def bld_supply(self) -> tuple[int, ...]:
        """Implements R-106, R-063: drawn buildings not yet taken (never refilled)."""
        taken = {b for h in self.held_buildings for b in h}
        return tuple(b for b in self.draws.buildings if b not in taken)

    def current_player(self) -> int:
        if self.phase == PHASE_SC or (self.phase == PHASE_RS and self.rd is not None):
            return pyspiel.PlayerId.CHANCE
        if self.phase in (PHASE_RS, PHASE_WS):
            return self.ot_q[0]  # R-097: the holder whose Overtime node is open
        if self.phase == PHASE_END:
            return pyspiel.PlayerId.TERMINAL
        if self.phase == PHASE_FS:
            return self.fs_pending[0]
        if self.phase == PHASE_SP:
            return len(self.picks)  # seat order 0..n-1 (R-015, R-016)
        if self.phase == PHASE_PK:
            return len(self.pk)  # seat order 0..n-1 (R-038)
        if self.phase in W_PHASES:
            return self.clearing[self.w_turn]  # clearing order (R-044)
        if self.phase in WINTER_TURNS:
            return self.wint[self.w_turn]  # fall clearing order (R-064)
        return self.tr_seat

    def is_terminal(self) -> bool:
        return self.phase == PHASE_END

    def chance_outcomes(self) -> list[tuple[int, float]]:
        """Implements R-026/R-027/R-062: ACTIONS 2 outcomes, uniform over remaining items."""
        if self.phase == PHASE_RS:
            assert self.rd is not None
            return [
                (A.encode_chance(fam, *params), p)
                for fam, params, p in self.rd.outcomes(self._tables())
            ]
        assert self.phase == PHASE_SC
        return [
            (A.encode_chance(fam, *params), p)
            for fam, params, p in self.draws.outcomes(self._tables())
        ]

    @property
    def pw_cards(self) -> tuple[int, ...]:
        return self.draws.pw

    def _loc_kind(self, loc: int) -> str:
        return next(k for number, k, _ in self._tables().locations if number == loc)

    def _tr_actions(self) -> list[int]:
        """Implements R-040..R-044, R-076: legal decisions of the acting seat in TR."""
        seat = self.tr_seat
        out: list[int] = []
        if self.loans[seat] < self._tables().max_loans:
            out.append(A.TAKE_LOAN)  # R-076: any node of the seat's own turn
        if self.hb_open:  # ACTIONS 5.7: an open build allows only its own steps and loans
            return sorted(out + self._encode_moves(build_actions(self._tables(), self, seat)))
        if self.visit_loc == 0:
            out += [A.encode("MOVE_TO", d) for d in legal_destinations(self._tables(), self, seat)]
            out += self._encode_moves(window_actions(self._tables(), self, seat, False))
        else:
            kind = self._loc_kind(self.visit_loc)
            out += [
                A.encode(name, *params)
                for name, params in visit_options(self._tables(), self, seat, kind)
            ]
            if kind in MULTI_UNIT_KINDS and self.visit_n >= 1:
                out.append(A.DONE)  # user decision 2026-11-05: multi-unit visits end on DONE
        return sorted(out)

    @staticmethod
    def _encode_moves(moves: list[tuple[str, tuple[int, ...]]]) -> list[int]:
        return [A.encode(name, *params) for name, params in moves]

    def _legal_actions(self, player: int) -> list[int]:
        if self.phase == PHASE_SC or (self.phase == PHASE_RS and self.rd is not None):
            return [a for a, _ in self.chance_outcomes()]
        if self.phase in (PHASE_RS, PHASE_WS):  # R-097 / ACTIONS 5.9
            moves = overtime_actions(self._tables(), self, player)
            return sorted(A.encode(name, *params) for name, params in moves)
        if self.phase == PHASE_SP:
            # Implements R-015: a 3-firewood area with no token yet; a forced pick is still offered.
            return [A.encode("PICK_AREA", a) for a in self.high_areas() if a not in self.picks]
        if self.phase == PHASE_PK:
            return [A.encode("PICK_AREA", a) for a in range(NUM_AREAS)]  # R-038: any area
        if self.phase == PHASE_TR:
            return self._tr_actions()
        t = self._tables()
        if self.phase == PHASE_FS:
            out = [A.encode("RIVER_SALE", k) for k in (0, 1)]
            if self.loans[player] < t.max_loans:
                out.append(A.TAKE_LOAN)  # ACTIONS 3.7: loans stay legal at the final sale
            return sorted(out)
        fn = {
            PHASE_W1: w1_actions,
            PHASE_W2: w2_actions,
            PHASE_W3: w3_actions,
            PHASE_W4: w4_actions,
            PHASE_W5: w5_actions,
            PHASE_W6: w6_actions,
            PHASE_W7: w7_actions,
            PHASE_NB: nb_actions,
            PHASE_N1: n1_actions,
            PHASE_N2: n2_actions,
            PHASE_N3: w4_actions,
            PHASE_N4: n4_actions,
            PHASE_SF: sf_actions,
        }.get(self.phase)
        if fn is None:
            return []
        if self.hb_open:  # ACTIONS 5.7
            loan = [A.TAKE_LOAN] if self.loans[player] < t.max_loans else []
            return sorted(loan + self._encode_moves(build_actions(t, self, player)))
        moves = fn(t, self, player)
        if self.phase in HUT_WINDOW_PHASES and not self.win_closed:  # R-100, C5, A1
            moves = moves + window_actions(t, self, player, self.phase in N_PHASES)
        return sorted(A.encode(name, *params) for name, params in moves)

    def _apply_action(self, action: int) -> None:
        if self.phase == PHASE_SC:
            t = self._tables()
            decoded = A.decode_chance(action)
            if not any(A.encode_chance(f, *p) == action for f, p, _ in self.draws.outcomes(t)):
                raise ValueError(f"chance outcome {A.chance_name(action)} not legal here")
            self.draws = self.draws.apply(t, decoded.name, decoded.params)
            self._sync_from_setup()
            if self.draws.done(t):
                self.phase = PHASE_SP
        elif self.phase == PHASE_RS and self.rd is not None:
            self._apply_round_start_chance(action)
        elif self.phase in (PHASE_RS, PHASE_WS):
            self._apply_overtime(action)
        elif self.phase == PHASE_SP:
            if not self.fast_apply and action not in self._legal_actions(self.current_player()):
                raise ValueError(f"SP action {A.action_name(action)} not legal here (R-015)")
            (area,) = A.decode(action).params
            self.picks = self.picks + (area,)
            if len(self.picks) == self.n:
                self._begin_travel()
        elif self.phase == PHASE_PK:
            if not self.fast_apply and action not in self._legal_actions(self.current_player()):
                raise ValueError(f"PK action {A.action_name(action)} not legal here (R-038)")
            (area,) = A.decode(action).params
            self.pk = self.pk + (area,)
            if len(self.pk) == self.n:
                self._reveal_picks()
        elif self.phase == PHASE_TR:
            self._apply_travel(action)
        elif self.phase == PHASE_FS:
            self._apply_final_sale(action)
        elif self.phase in W_PHASES or self.phase in WINTER_TURNS:
            self._apply_wood(action)
        else:
            raise ValueError(f"no action {action} applicable in phase {PHASE_NAMES[self.phase]}")

    def _begin_travel(self) -> None:
        """Implements R-040: foremen on location 0, the track's first seat moves."""
        self.phase = PHASE_TR
        self.tr_seat = self.turn_order[0]

    def _apply_travel(self, action: int) -> None:
        """Implements R-040..R-044, R-076: one TR decision of the acting seat."""
        if not self.fast_apply and action not in self._legal_actions(self.tr_seat):
            raise ValueError(f"TR action {A.action_name(action)} not legal here (R-040)")
        seat = self.tr_seat
        decoded = A.decode(action)
        name, params = decoded.name, decoded.params
        if name == "TAKE_LOAN":  # R-075, R-076
            self.money = _bump(self.money, seat, self._tables().loan_amount)
            self.loans = _bump(self.loans, seat, 1)
        elif name in HUT_NAMES:
            self._hut(seat, name, params)
        elif name == "MOVE_TO":
            self._move_to(seat, params[0])
        elif name == "DONE":
            self._end_turn()
        else:
            self._acquire(seat, name, params)

    def _move_to(self, seat: int, loc: int) -> None:
        """Implements R-040, R-042, R-044, R-078: move the foreman; token spots and the Joiner
        are taken at once and end the turn, worker/fodder/task locations open a visit."""
        self.foreman = _put(self.foreman, seat, loc)
        if loc == CLEARING_LOC:  # R-044: next free slot, no more moves this round
            self.clearing = self.clearing + (seat,)
            self._end_turn()
            return
        kind = self._loc_kind(loc)
        if kind == "token_spot":
            self._take_token(seat, self._tables().token_spots.index(loc))
            self._end_turn()
        elif kind == "joiner":
            self.joiners = _bump(self.joiners, seat, 1)  # R-078: free, permanent
            self.path_joiner = 0
            self._end_turn()
        else:
            self.visit_loc, self.visit_n, self.visit_food = loc, 0, 0

    def _take_token(self, seat: int, spot: int) -> None:
        """Implements R-042: the token goes where its type says; the spot is left empty (-1)."""
        y = self.path_tokens[spot]
        self.path_tokens = _put(self.path_tokens, spot, -1)
        name = SPOT_NAMES[y]
        if name == "dollar":
            self.money = _bump(self.money, seat, 1)
        elif name == "food":
            self.food = _bump(self.food, seat, 1)
        elif y >= FIRST_CRAFT_SPOT:
            self.held_craft = _bump2(self.held_craft, seat, y - FIRST_CRAFT_SPOT, 1)
        else:
            slot = EQUIP_SLOTS.index(name)
            s0, s1, s2, s3 = (e + (i == slot) for i, e in enumerate(self.equip[seat]))
            self.equip = self.equip[:seat] + ((s0, s1, s2, s3),) + self.equip[seat + 1 :]

    def _acquire(self, seat: int, name: str, params: tuple[int, ...]) -> None:
        """Implements R-025, R-041, R-043: one purchase inside an open visit. Single-acquisition
        locations (Fodder, Tasks) end the visit at once (ACTIONS 1.4)."""
        t = self._tables()
        price = t.price_location
        if name == "HIRE_BEARER":
            self.money = _bump(self.money, seat, -price)
            self.hired_b = _bump(self.hired_b, seat, 1)
            self.path_b -= 1
        elif name == "HIRE_WOODCUTTER":
            self.money = _bump(self.money, seat, -price)
            self.hired_w = _bump(self.hired_w, seat, 1)
            self.path_w -= 1
        elif name == "HIRE_SAWYER":
            if self.visit_n == 0:  # the free sawyer
                self.path_sf -= 1
            else:  # the $1 sawyer (R-025)
                self.money = _bump(self.money, seat, -t.price_sawyer_extra)
                self.path_sp -= 1
            self.hired_s = _bump(self.hired_s, seat, 1)
        elif name == "BUY_FODDER":
            self.money = _bump(self.money, seat, -fodder_cost(t, self, seat))
            self.fodder3 = _put(self.fodder3, seat, 1)
            self.fodder_bought = _put(self.fodder_bought, seat, 1)
            self.path_fodder -= 1
        elif name == "BUY_SAW":  # R-104: $1 to the bank, saw to the equipment area
            self.money = _bump(self.money, seat, -t.price_saw)
            self.equip = self._equip_add(seat, 0, 1)
        elif name == "PLAN_WORK":  # R-088: pay the bank, place both tokens
            card, pair = params[0], params[1] + 1
            self.money = _bump(self.money, seat, -plan_cost(t, self, card, seat))
            self.plans = self.plans + ((seat, card, pair, self.round + pair),)
        elif name == "SELL_FOOD":  # R-108: $1 per food back to the supply
            self.money = _bump(
                self.money, seat, building_param(t, "marketstand", "food_sale_price")
            )
            self.food = _bump(self.food, seat, -1)
            self.visit_food = 2
        elif name == "BUY_FOOD":  # R-104
            self.money = _bump(self.money, seat, -t.price_food)
            self.food = _bump(self.food, seat, 1)
            self.visit_food = 1
        elif name in ("SELL_SET", "SELL_SET_JOKERS"):  # R-105: tokens leave the game
            joker = len(CRAFT_ORDER) - 1
            x, size, jokers = params if name == "SELL_SET" else (joker, 2, 0)
            real = size - jokers
            self.money = _bump(self.money, seat, craft_price(t, self, seat, size))
            self.held_craft = _bump2(self.held_craft, seat, x, -real)
            removed = _bump(self.craft_removed, x, real)
            if jokers:
                self.held_craft = _bump2(self.held_craft, seat, joker, -jokers)
                removed = _bump(removed, joker, jokers)
            self.craft_removed = removed
        elif name == "SELL_EQUIP":  # R-090: $ per token, the token returns to the supply
            slot = EQUIP_SLOTS.index(("raft", "sledge", "wagon")[params[0]])
            self.money = _bump(self.money, seat, plan_param(t, "pw_trade", "price_per_equipment"))
            self.equip = self._equip_add(seat, slot, -1)
        elif name == "CHOOSE_BUILDING":  # R-106: free, permanent, leaves the supply for good
            self.held_buildings = (
                self.held_buildings[:seat]
                + (tuple(sorted(self.held_buildings[seat] + params)),)
                + self.held_buildings[seat + 1 :]
            )
        else:  # TAKE_TASK
            self.money = _bump(self.money, seat, -price)
            self.task_row = tuple(c for c in self.task_row if c != params[0])
            self.held_tasks = (
                self.held_tasks[:seat]
                + (tuple(sorted(self.held_tasks[seat] + params)),)
                + self.held_tasks[seat + 1 :]
            )
            self.task_taken = _put(self.task_taken, seat, 1)
        self.visit_n += 1
        if name in ("BUY_FODDER", "TAKE_TASK", "PLAN_WORK", "CHOOSE_BUILDING"):
            self._end_turn()

    def _end_turn(self) -> None:
        """Implements R-040, R-044: pass to the next foreman in the cycle, skipping the clearing;
        when every foreman is in the clearing, travel is over."""
        self.visit_loc = self.visit_n = self.visit_food = 0
        order = self.turn_order
        pos = order.index(self.tr_seat)
        for k in range(1, self.n + 1):
            nxt = order[(pos + k) % self.n]
            if self.foreman[nxt] != CLEARING_LOC:
                self.tr_seat = nxt
                return
        self.phase = PHASE_W1  # R-045: wood work starts with woodcutting
        self.w_turn = 0

    def _reset_turn(self) -> None:
        self.w_worker = -1
        self.win_closed = 0
        self.w_dirty = self.w_took = self.w_moved = 0
        self.w_ld = self.w_out = self.w_wc = 0
        self.w_outa = -1
        self.trip_kind, self.trip_n, self.trip_cap = TRIP_NONE, 0, 0

    def _next_turn(self) -> None:
        """Implements R-045: the next seat in clearing order, or the next phase after the last."""
        self._reset_turn()
        if self.phase in WINTER_TURNS:
            self._next_winter_turn()
            return
        self.w_turn += 1
        if self.w_turn < self.n:
            if self.phase == PHASE_W2:
                self._skip_empty_rivers()
            return
        self.w_turn = 0
        if self.phase == PHASE_W1:
            self.phase = PHASE_W2
            self._skip_empty_rivers()
        elif self.phase == PHASE_W2:
            self.phase = PHASE_W3
        elif self.phase == PHASE_W3:
            self.phase = PHASE_W4
        elif self.phase == PHASE_W4:
            self.phase = PHASE_W5
        elif self.phase == PHASE_W5:
            self.phase = PHASE_W6
        elif self.phase == PHASE_W6:
            self.phase = PHASE_W7
        else:  # W7 done: the round ends
            self._end_round()

    def _skip_empty_rivers(self) -> None:
        """W2 has a turn only for a seat with wood on its river (A2: it has no DONE to play)."""
        while self.w_turn < self.n and not sum(self.river[self.clearing[self.w_turn]]):
            self.w_turn += 1
        if self.w_turn == self.n:
            self.w_turn = 0
            self.phase = PHASE_W3

    def _apply_wood(self, action: int) -> None:
        """Implements R-045..R-059: one decision of the acting seat in W1..W7."""
        seat = self.current_player()
        if not self.fast_apply and action not in self._legal_actions(seat):
            raise ValueError(f"{A.action_name(action)} not legal in {PHASE_NAMES[self.phase]}")
        decoded = A.decode(action)
        name, params = decoded.name, decoded.params
        if name not in HUT_NAMES and name != "TAKE_LOAN":
            self.win_closed = 1  # A1: the first non-hut, non-loan action closes the window
        if name == "TAKE_LOAN":  # R-075, R-076
            self.money = _bump(self.money, seat, self._tables().loan_amount)
            self.loans = _bump(self.loans, seat, 1)
        elif name in HUT_NAMES:
            self._hut(seat, name, params)
        elif name == "DONE":
            if self.phase == PHASE_W7 and not self.w_dirty:
                self._advance_drying(seat)  # R-059: wood cannot be left behind
            self._next_turn()
        elif name == "TAKE_BONUS":  # R-065: one unmilled disk from the supply, no worker
            self.woodpile = _zone(self.woodpile, seat, params[0], 1)
            self.w_dirty = 1
        elif name == "WINTER_CUT":  # R-066: first winter cut 2 firewood, later 1
            t = self._tables()
            fw = t.winter_cut_further if self.wcut[seat] else t.winter_cut_first
            self.woodpile = _zone(self.woodpile, seat, 0, fw)
            self.wcut = _bump(self.wcut, seat, 1)
            self._use_worker(seat)
            self.w_worker = -1
            self.w_dirty = 1
        elif name == "USE_SLEDGE":  # R-067: sledge token spent, trip opens
            self._use_worker(seat)
            self.equip = self._equip_add(seat, IDX_SLEDGE, -1)
            self.trip_kind, self.trip_n, self.w_dirty = TRIP_SLEDGE, 0, 1
        elif name == "SAW":
            self._saw(seat, *params)
        elif name == "PLACE_TASK":
            self._place_task(seat, *params)
        elif name == "PLACE_JOINERY":
            self._place_joinery(seat, *params)
        elif name == "STORE_PIECE":
            self._store_piece(seat, *params)
        elif name == "SELL":
            self._sell(seat, *params)
        elif name == "DRY_ENTER":
            if not self.w_dirty:
                self._advance_drying(seat)
            self._dry_enter(seat, params[0])
        elif name == "ASSIGN_WORKER":  # ACTIONS 5.2
            self.w_worker = params[0]
            self.w_dirty = 1
        elif name == "MOVE_CUT_TOKEN":  # R-048: $1 to the bank
            self.money = _bump(self.money, seat, -self._tables().token_move_price)
            self.picks = _put(self.picks, seat, params[0])
            self.w_moved = self.w_dirty = 1
        elif name == "TAKE_WOOD":  # R-047
            area, kind = params
            self.wood = _zone(self.wood, area, kind, -1)
            self.woodpile = _zone(self.woodpile, seat, kind, 1)
            if area != self.picks[seat]:  # R-099 item 2: a worker cutting outside its own area
                self.w_out += 1
                self.w_outa = area
                self.cut_lost |= 1 << area
            self._use_worker(seat)
            self.w_worker = -1
            self.w_took = self.w_dirty = 1
        elif name == "MOVE_WOOD":
            self._move_wood(seat, *params)
        elif name == "USE_WAGON":  # R-052: wagon spent, fodder wears down at once (O-U2-9)
            self._use_worker(seat)
            self.equip = self._equip_add(seat, IDX_WAGON, -1)
            if self.fodder2[seat]:
                self.fodder2 = _put(self.fodder2, seat, 0)
                self.trip_cap = 2
            else:
                self.fodder3 = _put(self.fodder3, seat, 0)
                self.fodder2 = _put(self.fodder2, seat, 1)
                self.trip_cap = 3
            self.trip_kind, self.trip_n, self.w_dirty = TRIP_WAGON, 0, 1
        elif name == "USE_PW_LOGDRIVING":  # R-098: no worker, no raft; one trip per turn
            self.trip_kind, self.trip_n, self.w_dirty, self.w_ld = TRIP_PW, 0, 1, 1
        elif name in ("RIVER_MOVE", "WC_MOVE"):  # R-053, R-098, R-107
            pw = self.trip_kind == TRIP_PW
            if self.trip_kind == TRIP_NONE:
                self._use_worker(seat)
                self.trip_kind = TRIP_RAFT
            if not pw:
                self.equip = self._equip_add(seat, IDX_RAFT, -1)
            self.woodpile = _zone(self.woodpile, seat, params[0], -1)
            if name == "WC_MOVE":  # R-107: arrives at once; still one river placement (R-093)
                kind, dest = params
                if dest == 0:
                    self.sawing = _zone(self.sawing, seat, kind, 1)
                else:
                    self.sale = _zone(self.sale, seat, kind, 1)
                self.w_wc += 1
            else:
                self.river = _zone(self.river, seat, params[0], 1)
            self.trip_n += 1
            self.w_dirty = 1
            self._river_food(seat, 1)
            limit = plan_param(self._tables(), "pw_log_driving", "max_pieces") if pw else 0
            out_of_rafts = not pw and not self.equip[seat][IDX_RAFT]
            if out_of_rafts or (pw and self.trip_n >= limit) or not sum(self.woodpile[seat]):
                self._end_trip()
        elif name == "END_TRIP":
            self._end_trip()

    def _river_food(self, seat: int, pieces: int) -> None:
        """Implements R-093: PW Food Supply in its target round pays food per river piece."""
        t = self._tables()
        if plan_active(t, self, seat, "pw_food_supply"):
            per = plan_param(t, "pw_food_supply", "food_per_river_piece")
            self.food = _bump(self.food, seat, per * pieces)

    def _equip_add(self, seat: int, slot: int, delta: int) -> tuple[tuple[int, int, int, int], ...]:
        e = self.equip[seat]
        row = (e[0], e[1], e[2], e[3])
        row = tuple(v + delta if i == slot else v for i, v in enumerate(row))
        return self.equip[:seat] + ((row[0], row[1], row[2], row[3]),) + self.equip[seat + 1 :]

    def _use_worker(self, seat: int) -> None:
        """Implements R-045: the committed worker is used up (mill worker once per round)."""
        if self.w_worker == SRC_MILL:
            self.mill_used = _put(self.mill_used, seat, 1)
        elif self.w_worker == SRC_HUT:  # R-103: the token is spent when it is used
            self._spend_hut(seat, HUT_WORKER)
        elif self.phase in N_PHASES:  # R-064: no hired workers in winter
            raise ValueError("no hired worker in winter")
        elif self.phase == PHASE_W1:
            self.cut_used = _bump(self.cut_used, seat, 1)
        elif self.phase == PHASE_W4:
            self.saw_used = _bump(self.saw_used, seat, 1)
        else:
            self.bear_used = _bump(self.bear_used, seat, 1)

    def _spend_hut(self, seat: int, area: int) -> None:
        """Implements R-101..R-103: a spent hut token is removed from the game."""
        row = _bump(self.huts[seat], area, -1)
        self.huts = self.huts[:seat] + ((row[0], row[1], row[2]),) + self.huts[seat + 1 :]
        self.hut_spent += 1

    def _hut(self, seat: int, name: str, params: tuple[int, ...]) -> None:
        """Implements R-100..R-102: one hut action (build step, food or drying effect). Hut
        actions do not close the window and leave the turn open."""
        if name == "BUILD_HUT":
            self.hb_open, self.hb_tok, self.hb_area = (HB_PW if params[0] else 1), (), ()
        elif name == "HUT_TOKEN":
            self.hb_tok = self.hb_tok + params
        elif name == "HUT_AREA":
            self.hb_area = self.hb_area + params
            size = build_size(self._tables(), self)
            if len(self.hb_area) == size:  # the tokens flip: out of the craftwork stock
                for x in self.hb_tok:
                    self.held_craft = _bump2(self.held_craft, seat, x, -1)
                    self.craft_removed = _bump(self.craft_removed, x, 1)
                for h in self.hb_area:
                    row = _bump(self.huts[seat], h, 1)
                    new_row = (row[0], row[1], row[2])
                    self.huts = self.huts[:seat] + (new_row,) + self.huts[seat + 1 :]
                self.hut_built += size
                self.hb_open, self.hb_tok, self.hb_area = 0, (), ()
        elif name == "HUT_FOOD":  # R-102: the entire food of a free area
            self.food = _bump(self.food, seat, self.area_food[params[0]])
            self.area_food = _put(self.area_food, params[0], 0)
            self._spend_hut(seat, HUT_FOOD)
        else:  # HUT_DRY, R-101: one piece one area right, capacity ignored
            zone, p = params
            self._remove_piece(seat, zone, p)
            self._dry_add(seat, zone, piece_idx(p), 1)
            self._spend_hut(seat, HUT_DRYING)

    def _end_trip(self) -> None:
        self.trip_kind, self.trip_n, self.trip_cap, self.w_worker = TRIP_NONE, 0, 0, -1

    def _move_wood(self, seat: int, kind: int, dest: int) -> None:
        """Implements R-049, R-050..R-052: one piece to the sawing (0) or sale (1) area."""
        if self.phase == PHASE_W2:
            self.river = _zone(self.river, seat, kind, -1)
        else:
            self.woodpile = _zone(self.woodpile, seat, kind, -1)
        zone = self.sawing if dest == 0 else self.sale
        zone = _zone(zone, seat, kind, 1)
        if dest == 0:
            self.sawing = zone
        else:
            self.sale = zone
        self.w_dirty = 1
        if self.phase == PHASE_W2:
            if not sum(self.river[seat]):
                self._next_turn()
            return
        if self.trip_kind == TRIP_NONE:  # bearer trip: exactly one piece (R-051)
            self._use_worker(seat)
            self._end_trip()
            return
        if self.trip_kind == TRIP_SLEDGE:  # R-067: pieces beyond the free two cost 1 food each
            t = self._tables()
            if self.trip_n >= t.sledge_free:
                self.food = _bump(self.food, seat, -1)
            self.trip_n += 1
            full = self.trip_n >= t.sledge_free + t.sledge_food
            if (
                full
                or not sum(self.woodpile[seat])
                or (self.trip_n >= t.sledge_free and not self.food[seat])
            ):
                self._end_trip()
            return
        self.trip_n += 1
        if self.trip_n >= self.trip_cap or not sum(self.woodpile[seat]):
            self._end_trip()

    def _saw(self, seat: int, kind: int, n_store: int) -> None:
        """Implements R-054, R-092, R-094: the disk becomes logs, ``n_store`` to the firewood
        storage and the rest to the sale area. The first disk of a worker spends the saw and the
        worker; with PW Sawing the worker's second disk (``w_worker`` == SRC_PAIR) is free."""
        t = self._tables()
        total = saw_yield(t, self, seat, kind)
        self.sawing = _zone(self.sawing, seat, kind, -1)
        self.store = _zone(self.store, seat, kind, n_store)
        self.sale_logs = _zone(self.sale_logs, seat, kind, total - n_store)
        if self.w_worker == SRC_PAIR:
            self.w_worker = -1
            self.w_dirty = 0  # the closed pair leaves a clean turn start (ASSIGN_WORKER or DONE)
            return
        self.equip = self._equip_add(seat, IDX_SAW, -1)
        self._use_worker(seat)
        pair = (
            plan_active(t, self, seat, "pw_sawing")
            and plan_param(t, "pw_sawing", "disks_per_saw") > 1
        )
        self.w_worker = SRC_PAIR if pair else -1  # state holds one extra disk (data: 2 per saw)
        self.w_dirty = 1

    def _dry_add(self, seat: int, area: int, idx: int, delta: int) -> None:
        row = self.dry[seat]
        row = row[:area] + (_bump(row[area], idx, delta),) + row[area + 1 :]
        self.dry = self.dry[:seat] + (row,) + self.dry[seat + 1 :]

    def _remove_piece(self, seat: int, zone: int, p: int) -> None:
        """Take one piece of type p from the sale area (zone 0) or drying area ``zone``."""
        if zone == 4:  # winter shortfall sale only (R-073)
            self.sawing = _zone(self.sawing, seat, p // 2, -1)
        elif zone == 5:
            self.store = _zone(self.store, seat, p // 2, -1)
        elif zone == 0:
            if p % 2:
                self.sale_logs = _zone(self.sale_logs, seat, p // 2, -1)
            else:
                self.sale = _zone(self.sale, seat, p // 2, -1)
        else:
            self._dry_add(seat, zone - 1, piece_idx(p), -1)

    def _place_task(self, seat: int, slot: int, src: int) -> None:
        """Implements R-055, R-056: lock one piece on a requirement slot (source 0 = the area its
        stage names, 1 = drying 1 for a stage-0 requirement)."""
        task, req, kind, milled, stage = self._tables().task_slots[slot]
        self.filled = _put(self.filled, task, self.filled[task] | 1 << req)
        if src == 2:  # R-114: the stored piece fills it at any stage; the building is spent.
            self.small_storage = _put(self.small_storage, seat, STORAGE_SPENT)
            self.w_dirty = 1
            return
        zone = 1 if src == 1 else (0, 2, 3)[stage]
        self._remove_piece(seat, zone, 2 * kind + milled)
        self.w_dirty = 1

    def _store_piece(self, seat: int, kind: int, zone: int) -> None:
        """Implements R-114: a milled piece of ``kind`` from the sale area or a drying area is
        committed to the Small Storage Area."""
        self._remove_piece(seat, zone, 2 * kind + 1)
        self.small_storage = _put(self.small_storage, seat, kind)
        self.w_dirty = 1

    def _place_joinery(self, seat: int, kind: int, slot: int) -> None:
        """Implements R-057: a milled piece from drying 2 into joinery slot ``slot``, for good."""
        self._remove_piece(seat, 2, 2 * kind + 1)
        a, b, c = (kind if i == slot else k for i, k in enumerate(self.joinery_wood[seat]))
        jw = self.joinery_wood
        self.joinery_wood = jw[:seat] + ((a, b, c),) + jw[seat + 1 :]
        self.w_dirty = 1

    def _sell(self, seat: int, zone: int, p: int) -> None:
        """Implements R-058: base price plus the bonus of the area; the piece leaves the game."""
        t = self._tables()
        self._remove_piece(seat, zone, p)
        bonus = t.dry_bonus[zone] if zone < len(t.dry_bonus) else 0  # R-073: zones 4, 5 carry none
        self.money = _bump(self.money, seat, t.wood_price[p // 2][p % 2] + bonus)
        self.w_dirty = 1

    def _advance_drying(self, seat: int) -> None:
        """Implements R-059: drying 2 -> 3, drying 1 -> 2 (right to left, no chaining)."""
        d1, d2, d3 = self.dry[seat]
        moved = (ZERO6, d1, tuple(a + b for a, b in zip(d2, d3, strict=True)))
        self.dry = self.dry[:seat] + (moved,) + self.dry[seat + 1 :]
        self.w_dirty = 1

    def _dry_enter(self, seat: int, p: int) -> None:
        """Implements R-059: one sale-area piece into drying 1."""
        self._remove_piece(seat, 0, p)
        self._dry_add(seat, 0, piece_idx(p), 1)

    def _end_round(self) -> None:
        """Implements R-060 (player order), R-061 (cleanup) and R-033/R-064 (winter follows fall).

        The fall clearing order is kept as the winter turn order (``wint``, R-064); the starting
        order set here stays unchanged through winter (R-060).
        """
        self.turn_order = tuple(reversed(self.clearing))  # R-060
        if self.round in (self._tables().winter_rounds[0] - 1, self._tables().winter_rounds[1] - 1):
            self.wint = self.clearing
        self._cleanup()
        self.round += 1
        if self.round in self._tables().winter_rounds:
            self._open_overtime(PHASE_WS, PHASE_NB)  # R-064: no income, no path, no picks
            return
        self._begin_round()

    def _overtime_holders(self) -> tuple[int, ...]:
        """Implements R-097: seats holding Overtime for this round, in starting-player order."""
        t = self._tables()
        return tuple(s for s in self.turn_order if plan_active(t, self, s, "pw_overtime"))

    def _open_overtime(self, node: int, after: int) -> None:
        """Implements R-097 / R-034 step 3a: open the holders' Overtime nodes at ``node`` (RS or
        WS), or go straight on to ``after`` (PK or NB) when nobody holds the card."""
        self.ot_q = self._overtime_holders()
        self.phase = node if self.ot_q else after
        if after == PHASE_PK:
            self.pk = ()

    def _apply_overtime(self, action: int) -> None:
        """Implements R-097: TAKE_OVERTIME puts 1 unmilled hardwood disk (R-046) into the woodpile
        (the node then needs DONE); DONE declines or closes; TAKE_LOAN keeps it open."""
        seat = self.current_player()
        if not self.fast_apply and action not in self._legal_actions(seat):
            raise ValueError(f"{A.action_name(action)} not legal at the Overtime node (R-097)")
        name = A.decode(action).name
        if name == "TAKE_LOAN":
            self.money = _bump(self.money, seat, self._tables().loan_amount)
            self.loans = _bump(self.loans, seat, 1)
            return
        if name == "TAKE_OVERTIME":
            disks = plan_param(self._tables(), "pw_overtime", "hardwood_disks")
            self.woodpile = _zone(self.woodpile, seat, HARDWOOD, disks)
            self.w_dirty = 1  # taken: only DONE (or a loan) remains, like A2's winter nodes
            return
        self.w_dirty = 0
        self.ot_q = self.ot_q[1:]
        if not self.ot_q:
            self.phase = PHASE_PK if self.phase == PHASE_RS else PHASE_NB

    def _next_winter_turn(self) -> None:
        """Implements R-064: the next seat in fall clearing order, or the next winter phase.
        After tasks (N4) feeding and heating run automatically (R-071, R-072)."""
        if self.phase == PHASE_SF:  # R-073 step 4: pay what is held, forgive the rest (D9)
            seat = self.wint[self.w_turn]
            self.money = _bump(self.money, seat, -min(self.money[seat], self.sf_due))
            self.sf_due = 0
            self.w_turn += 1
            self._settle()
            return
        self.w_turn += 1
        if self.w_turn < self.n:
            return
        self.w_turn = 0
        if self.phase == PHASE_N4:
            self.pay = FEED
            self._settle()
        else:
            self.phase += 1

    def _winter_requirement(self) -> tuple[int, int]:
        """Implements R-070: (food, heating) of the visible half of this winter's card."""
        t = self._tables()
        year = t.winter_rounds.index(self.round)
        w = self.draws.winter[year]
        return t.winter_req[year][w // 2][w % 2]

    def _pay_feeding(self, seat: int) -> int:
        """Implements R-071, R-109: food due is the card's plus 1 per joiner (Storeroom: minus 1);
        other food returns to the supply, except the Storeroom's surplus after winter 1. Returns
        the money due for missing food."""
        t = self._tables()
        due = self._winter_requirement()[0] + self.joiners[seat] * t.joiner_food
        store = has_building(t, self.held_buildings, seat, "storeroom")
        if store:  # R-109: the requirement is reduced before the shortfall
            due = max(0, due - building_param(t, "storeroom", "winter_food_reduction"))
        missing = max(0, due - self.food[seat])
        keep = store and self.round == t.winter_rounds[0]  # R-109: surplus kept after winter 1
        self.food = _put(self.food, seat, max(0, self.food[seat] - due) if keep else 0)
        return missing * t.shortfall_unit

    def _pay_heating(self, seat: int) -> int:
        """Implements R-072: milled pieces from the firewood storage, cheapest kind first.
        Returns the money due for missing pieces."""
        need = self._winter_requirement()[1]
        for kind in range(3):
            take = min(need, self.store[seat][kind])
            self.store = _zone(self.store, seat, kind, -take)
            need -= take
        return need * self._tables().shortfall_unit

    def _settle(self) -> None:
        """Implements R-071..R-073: feeding then heating for every seat in turn; stops at the
        first seat that cannot pay from its money (SF); ends the winter when all have paid."""
        while True:
            if self.w_turn >= self.n:
                if self.pay == FEED:
                    self.pay, self.w_turn = HEAT, 0
                    continue
                self._end_winter()
                return
            seat = self.wint[self.w_turn]
            self.phase = PHASE_N5 if self.pay == FEED else PHASE_N6
            due = self._pay_feeding(seat) if self.pay == FEED else self._pay_heating(seat)
            if due > self.money[seat]:
                self.sf_due = due
                self.phase = PHASE_SF
                return
            self.money = _bump(self.money, seat, -due)
            self.w_turn += 1

    def _end_winter(self) -> None:
        """Implements R-074: mill workers return; round 4 leads to spring year 2, round 8 leads
        to the final sale (R-081)."""
        self._cleanup()
        if self.round == self._tables().winter_rounds[1]:
            self._begin_final_sale()  # ``wint`` stays: the FS choices follow it
            return
        self.wint = ()
        self.round += 1
        self._begin_round()

    def _begin_final_sale(self) -> None:
        """Implements R-081 steps 1 and 3 (R-082): sale and drying areas and covered joinery
        pieces sell now; a river with both firewood and softwood waits for the seat's choice."""
        t = self._tables()
        zeros = (ZERO3,) * self.n
        for seat in range(self.n):
            total = 0
            for p in range(6):
                price = t.wood_price[p // 2][p % 2]
                if price < 0:
                    continue
                for zone in range(4):
                    total += zone_count(self, seat, zone, p) * (price + t.dry_bonus[zone])
            bonus = t.joinery_bonus  # R-112: Small Joinery replaces the bonus
            if has_building(t, self.held_buildings, seat, "small_joinery"):
                bonus = building_param(t, "small_joinery", "joinery_bonus")
            for slot, kind in enumerate(self.joinery_wood[seat]):
                if kind != NO_SLOT and slot < self.joiners[seat]:  # R-082: covered slots only
                    total += t.wood_price[kind][1] + bonus
            self.money = _bump(self.money, seat, total)
        self.sale, self.sale_logs, self.joinery_wood = zeros, zeros, ((NO_SLOT,) * 3,) * self.n
        self.dry = ((ZERO6,) * 3,) * self.n
        self.fs_pending = tuple(  # year-2 fall clearing order (user decision 2026-11-05)
            seat for seat in self.wint if self.river[seat][0] and self.river[seat][1]
        )
        self.choosers = self.fs_pending
        self._advance_final_sale()

    def _sell_river(self, seat: int, kind: int) -> None:
        """Implements R-081 step 2: one kind of river wood at its unmilled price, no bonus."""
        self.money = _bump(
            self.money, seat, self.river[seat][kind] * self._tables().wood_price[kind][0]
        )
        self.river = _zone(self.river, seat, kind, -self.river[seat][kind])

    def _advance_final_sale(self) -> None:
        if self.fs_pending:
            self.phase = PHASE_FS
            return
        t = self._tables()
        for seat in range(self.n):
            if seat not in self.choosers:  # a single sellable kind is sold automatically
                for kind in (0, 1):
                    self._sell_river(seat, kind)
            if has_building(t, self.held_buildings, seat, "office"):  # R-116: before repayment
                self.money = _bump(
                    self.money,
                    seat,
                    len(self.held_tasks[seat]) * building_param(t, "office", "money_per_task_card"),
                )
            for held in self.held_tasks[seat]:  # R-056: completed tasks pay
                task = _components().tasks[held]
                if self.filled[held] == (1 << len(task.requirements)) - 1:
                    self.money = _bump(self.money, seat, task.reward)
        self.final = tuple(
            m - t.loan_repay[loans] for m, loans in zip(self.money, self.loans, strict=True)
        )  # R-083: repayment last
        self.phase = PHASE_END

    def _apply_final_sale(self, action: int) -> None:
        """Implements R-081 step 2: the river kind choice (or a loan, ACTIONS 3.7)."""
        seat = self.fs_pending[0]
        if not self.fast_apply and action not in self._legal_actions(seat):
            raise ValueError(f"{A.action_name(action)} not legal in FS")
        decoded = A.decode(action)
        if decoded.name == "TAKE_LOAN":
            self.money = _bump(self.money, seat, self._tables().loan_amount)
            self.loans = _bump(self.loans, seat, 1)
            return
        self._sell_river(seat, decoded.params[0])
        self.fs_pending = self.fs_pending[1:]
        self._advance_final_sale()

    def _cleanup(self) -> None:
        """Implements R-061: workers, mill workers, foremen and tokens reset; leftover equipment
        returns to the supply (not tracked on the path), leftover craftwork leaves the game."""
        t = self._tables()
        self.clearing = ()
        self.foreman = (0,) * self.n
        z = (0,) * self.n
        self.hired_b = self.hired_w = self.hired_s = z
        self.fodder_bought = self.task_taken = z
        self.mill_used = self.cut_used = self.bear_used = self.saw_used = self.wcut = z
        self.cut_lost = 0
        self._reset_turn()
        self.w_turn = 0
        removed = list(self.craft_removed)
        for y in self.path_tokens:
            if y >= FIRST_CRAFT_SPOT:
                removed[y - FIRST_CRAFT_SPOT] += 1
        self.craft_removed = tuple(removed)
        self.path_tokens = ()
        self.path_b, self.path_w = t.path_bearers, t.path_woodcutters
        self.path_sf, self.path_sp = t.path_sawyers_free, t.path_sawyers_paid

    def _begin_round(self) -> None:
        """Implements R-034 steps 1-2 and R-035..R-037: joiner income, restock the Joiner and
        Fodder locations, then the chance run (the path was cleared by ``_cleanup``)."""
        t = self._tables()
        if self.joinery:
            # R-079: $1 per joiner owned at the start of a seasonal round (hired earlier).
            self.money = tuple(
                m + j * t.joiner_income for m, j in zip(self.money, self.joiners, strict=True)
            )
        self.path_fodder = t.path_fodder
        if self.joinery:  # R-035: one joiner on the path while the supply still has one
            self.path_joiner = 1 if sum(self.joiners) < t.joiner_supply else 0
        self.rd = start_round_draws(
            t, len(self.task_row), self.tasks_seen, self.craft_pile, self.placement_discarded
        )
        self.phase = PHASE_RS

    def _apply_round_start_chance(self, action: int) -> None:
        """Implements R-035..R-037, R-062: one round-start chance outcome; the last one applies
        the whole step (path, task row, placement cards) and opens the hidden picks."""
        rd = self.rd
        assert rd is not None
        t = self._tables()
        decoded = A.decode_chance(action)
        if not any(A.encode_chance(f, *p) == action for f, p, _ in rd.outcomes(t)):
            raise ValueError(f"chance outcome {A.chance_name(action)} not legal here")
        rd = rd.apply(decoded.name, decoded.params)
        self.rd = rd
        if not rd.done():
            return
        self.task_row = tuple(sorted(self.task_row + rd.new_tasks))
        self.tasks_seen = tuple(sorted(self.tasks_seen + rd.new_tasks))
        self.craft_pile = tuple(rd.pile[x] - rd.craft.count(x) for x in range(len(CRAFT_ORDER)))
        self.path_tokens = rd.spots
        self.placement_discarded = tuple(sorted(self.placement_discarded + rd.cards))
        self.wood, self.area_food = apply_placement(t, self.wood, self.area_food, rd.cards)
        self.rd = None
        self._open_overtime(PHASE_RS, PHASE_PK)  # R-034 step 3a, before the hidden picks

    def _reveal_picks(self) -> None:
        """Implements R-038, R-039: reveal all picks together, then distribute area food."""
        self.pick_log = self.pick_log + (self.picks,)
        self.picks = self.pk
        self.pk = ()
        gain, self.area_food = distribute_food(self.picks, self.area_food)
        self.food = tuple(f + g for f, g in zip(self.food, gain, strict=True))
        self._begin_travel()

    def _action_to_string(self, player: int, action: int) -> str:
        if player == pyspiel.PlayerId.CHANCE:
            return A.chance_name(action)
        return A.action_name(action)

    def returns(self) -> list[float]:
        """Implements R-084..R-086 from the final dollars; zeros before the game ends."""
        n = self.n
        if self.phase != PHASE_END:
            return [0.0] * n
        d = self.final
        game: LignumGame = self.get_game()  # type: ignore[assignment]
        if game.returns_mode == "margin":
            return [max(-1.0, min(1.0, (x - (sum(d) - x) / (n - 1)) / 50)) for x in d]
        top = max(d)
        k = sum(1 for x in d if x == top)
        if k == n:
            return [0.0] * n
        return [(n - k) / (k * (n - 1)) if x == top else -1 / (n - 1) for x in d]

    def __str__(self) -> str:
        """Full-information view via the observer (R-030)."""
        game: LignumGame = self.get_game()  # type: ignore[assignment]
        return game.full_observer().string_from(self, 0)


pyspiel.register_game(_game_type("win_loss"), LignumGame)
