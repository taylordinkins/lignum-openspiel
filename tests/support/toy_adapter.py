"""Server adapter for the toy chance game, so the game-agnostic server shell can be tested
without the real Lignum adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyspiel
from fastapi import FastAPI

import tests.support.toy_chance_game as toy
from server.adapters.base import JSON, GameAdapter
from server.app import create_app

NAME = "toy"


class ToyAdapter(GameAdapter):
    name = NAME

    def load(self, params: dict[str, Any]) -> pyspiel.Game:
        n = params.get("num_players")
        return pyspiel.load_game(
            toy.GAME_TYPE.short_name, {"players": toy.DEFAULT_PLAYERS if n is None else n}
        )

    def action_meta(self, state: pyspiel.State, action_id: int) -> JSON:
        return {"label": state.action_to_string(state.current_player(), action_id)}

    def chance_label(self, state: pyspiel.State, action_id: int) -> str:
        return state.action_to_string(pyspiel.PlayerId.CHANCE, action_id)

    def view(self, state: pyspiel.State, seat: int) -> JSON:
        terminal = state.is_terminal()
        chance = state.is_chance_node()
        current = None if terminal or chance else state.current_player()
        legal = (
            [{"id": a, **self.action_meta(state, a)} for a in state.legal_actions()]
            if current is not None
            else []
        )
        returns = list(state.returns()) if terminal else None
        winners = (
            [p for p, r in enumerate(returns) if r == max(returns)] if returns is not None else None
        )
        return {
            "seat": seat,
            "state": str(state),
            "current_player": current,
            "is_terminal": terminal,
            "legal_actions": legal,
            "returns": returns,
            "winners": winners,
        }


def toy_app(
    dev_mode: bool = False,
    reports_dir: Path | str | None = None,
    inline_bots: bool | None = None,
) -> FastAPI:
    return create_app(
        dev_mode=dev_mode,
        reports_dir=reports_dir,
        inline_bots=inline_bots if inline_bots is not None else True,
        adapters={NAME: ToyAdapter()},
    )
