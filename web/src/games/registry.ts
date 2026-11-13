import { createElement, type ReactNode } from "react";
import type { GameView, LegalAction } from "../shell/useGame";
import { lignumPlugin } from "./lignum/plugin";

/** Transient UI state shared between the action list and the board. */
export interface BoardUi {
  /** Id of the legal action currently hovered/focused in the action list. */
  hoverAction: number | null;
  /** True only on a human seat's turn when no request is in flight and no bot is thinking. */
  canAct?: boolean;
  /** Submit a legal action by id (same path as the action list). */
  onAct?: (actionId: number) => void | Promise<unknown>;
  /** Submit several legal actions in order as one all-or-nothing request. */
  onActBatch?: (actionIds: number[]) => void | Promise<unknown>;
  /** Seat whose private information may be shown (hotseat view seat). */
  viewSeat?: number | null;
}

export interface GamePlugin {
  id: string;
  title: string;
  renderBoard(game: GameView, ui?: BoardUi): ReactNode;
  /** Whether the sole legal action on a human turn should be submitted automatically. */
  autoAdvance?(action: LegalAction, legalActions: LegalAction[]): boolean;
  phaseLabel?(game: GameView): string | undefined;
  seatStyle?(seat: number): { fill: string; ink: string };
  actionLabel?(game: GameView, action: LegalAction): string;
  actionHelp?(game: GameView, action: LegalAction): string | undefined;
}

export const fallbackPlugin: GamePlugin = {
  id: "generic",
  title: "Game",
  renderBoard: (g) =>
    createElement("pre", { "aria-label": "Game state" }, JSON.stringify(g.view, null, 2)),
};

const plugins: Record<string, GamePlugin> = {
  [lignumPlugin.id]: lignumPlugin,
};

/** Game name (GameView.game) -> plugin; unknown games get the generic fallback. */
export function getPlugin(id: string): GamePlugin {
  return (Object.prototype.hasOwnProperty.call(plugins, id) ? plugins[id] : undefined) ?? fallbackPlugin;
}
