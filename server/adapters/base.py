"""Game-agnostic adapter interface. The server shell only talks to this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pyspiel

JSON = dict[str, Any]


class GameAdapter(ABC):
    """Maps one OpenSpiel game to JSON for clients."""

    name: str

    @abstractmethod
    def load(self, params: dict[str, Any]) -> pyspiel.Game:
        """Build the pyspiel game from creation params.

        `params` holds the set fields of the API's GameParams (`num_players`, `joinery`,
        `returns`, ...); the adapter maps them to the game's own parameter names.
        """

    @abstractmethod
    def view(self, state: pyspiel.State, seat: int) -> JSON:
        """JSON-serialisable view of `state` for `seat` (hidden info is filtered per seat)."""

    @abstractmethod
    def action_meta(self, state: pyspiel.State, action_id: int) -> JSON:
        """Metadata for an action: at least a `label`; optional game-specific keys."""

    def chance_label(self, state: pyspiel.State, action_id: int) -> str:
        """Label for a chance outcome, given the state at the chance node (override per game)."""
        return f"Chance outcome {action_id}"

    def history_mask(
        self,
        state_before: pyspiel.State,
        actor: int,
        action_id: int,
        state_now: pyspiel.State,
        viewer: int,
    ) -> str | None:
        """Hidden-information hook for history rendering.

        Called for each player action in the history: `state_before` is the state it was played
        in, `state_now` the current state, `viewer` the rendered seat. Return a replacement label
        if `viewer` must not see which action it was (the entry is then sent with `id` null), or
        None (default) to show it. Must not call `action_meta` for hidden actions.
        """
        return None

    def pick_revealed(
        self, state_before: pyspiel.State, actor: int, action_id: int, state_now: pyspiel.State
    ) -> bool:
        """True if this player action was hidden when played and has since been revealed.

        Back may not undo such an action (R-038). Default: games have no hidden actions.
        """
        return False

    def chance_blocks_back(self, state_before: pyspiel.State, action_id: int) -> bool:
        """True if Back may not remove this chance outcome (replay would re-deal it identically
        and leak it). Called with the state the chance outcome was drawn in. Default: no."""
        return False

    def export_block(self, state: pyspiel.State) -> str | None:
        """Reason the history cannot be exported now (it would leak hidden info), else None."""
        return None

    def scenario_players(self, scenario: JSON) -> int:
        """Player count of a scenario JSON; raise ValueError if invalid or unsupported."""
        raise ValueError(f"{self.name} does not support scenarios")

    def initial_state(self, game: pyspiel.Game, scenario: JSON | None) -> pyspiel.State:
        """Start state: the game's own, or the one a scenario JSON describes (D18)."""
        if scenario is not None:
            raise ValueError(f"{self.name} does not support scenarios")
        return game.new_initial_state()
