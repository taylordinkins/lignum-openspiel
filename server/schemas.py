"""Request/response envelopes for the HTTP API (OpenAPI source for generated web types)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from server.bots import SEAT_TYPE_PATTERN

SeatType = Annotated[
    str,
    Field(
        pattern=SEAT_TYPE_PATTERN,
        description=(
            "human or a bot seat type "
            "(random, heuristic, heuristic-v1, heuristic-v2, heuristic-v3, heuristic-v4, "
            "heuristic-v5, heuristic-v6, heuristic-v7, strategist, az, mcts, mcts-fast)."
        ),
    ),
]


class GameParams(BaseModel):
    """Creation parameters for a game; adapters read the fields they know (extras are kept)."""

    model_config = ConfigDict(extra="allow")

    num_players: int | None = Field(
        default=None, ge=2, le=4, description="Number of players (2..4)."
    )
    joinery: bool = Field(
        default=True, description="Play with the Joinery and Buildings expansion."
    )
    returns: Literal["win_loss", "margin"] = Field(
        default="win_loss", description="Terminal returns mode."
    )


class CreateGameRequest(BaseModel):
    game: str = "lignum"
    params: GameParams = Field(default_factory=GameParams)
    seats: list[SeatType]
    seed: int | None = None
    scenario: dict[str, Any] | None = Field(
        default=None,
        description="Optional scenario JSON (docs/SCENARIOS.md); the game starts from it.",
    )


class LegalAction(BaseModel):
    """One action the seat to move may take, as described by the adapter."""

    id: int
    label: str
    kind: str | None = None
    region: int | None = None
    faction: int | None = None
    card: int | None = None
    params: list[int] | None = None


class HistoryEntry(BaseModel):
    """One past action; `actor` is null for chance outcomes. Hidden picks have a null id."""

    index: int
    actor: int | None
    id: int | None = Field(description="Action id; null when hidden from the rendered seat.")
    label: str


class GameView(BaseModel):
    """A game as seen by one seat."""

    id: str
    game: str
    seats: list[SeatType]
    seat_types: list[SeatType]
    bot_thinking: bool = Field(
        description="A bot seat is to move and has not failed (false in the error state)."
    )
    bot_error: str | None = Field(
        default=None, description="Set when the bot worker failed; POST bots/retry to retry."
    )
    seat: int
    history_length: int
    history: list[HistoryEntry] = Field(description="Labelled action history, oldest first.")
    dev_mode: bool = Field(description="Server allows dev-only operations (rewind).")
    current_player: int | None = Field(description="Seat to move; null at chance or terminal.")
    is_terminal: bool
    legal_actions: list[LegalAction] = Field(description="Actions for current_player.")
    returns: list[float] | None = Field(default=None, description="Final returns when terminal.")
    winners: list[int] | None = Field(default=None, description="Winning seats when terminal.")
    view: dict[str, Any] = Field(description="Adapter-defined view payload.")


class ActionRequest(BaseModel):
    action: int


class BatchActionRequest(BaseModel):
    action_ids: list[int] = Field(
        min_length=1, max_length=32, description="Actions applied in order, all or nothing."
    )


class RewindRequest(BaseModel):
    player_actions: int


class GameExport(BaseModel):
    """Replay file: everything needed to rebuild a game by replaying `history`."""

    game: str
    params: GameParams
    seats: list[SeatType]
    history: list[int]
    scenario: dict[str, Any] | None = Field(
        default=None, description="Scenario the game started from, if any."
    )


class ReportRequest(BaseModel):
    note: str = Field(min_length=1, description="What went wrong (required).")
    category: str | None = Field(default=None, description='e.g. "engine", "ui", "other".')

    @field_validator("note")
    @classmethod
    def _note_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("note must not be blank")
        return v


class ReportResponse(BaseModel):
    report_id: str
    path: str


class ErrorResponse(BaseModel):
    detail: str
