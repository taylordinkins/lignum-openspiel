import { createContext, useContext } from "react";
import type { GameView } from "./useGame";

/**
 * Hotseat seat-view logic, kept in one place (unit 8's curtain hooks here).
 * The viewed seat is the current player when that seat is human; otherwise the previously viewed
 * seat is kept (so a bot's turn never exposes its own private state), falling back to the first
 * human seat; only an all-bot game uses the seat the server rendered.
 */
export function deriveViewSeat(game: GameView, previous: number | null): number {
  const cp = game.current_player;
  if (cp !== null && game.seats[cp] === "human") return cp;
  if (previous !== null) return previous;
  const firstHuman = game.seats.indexOf("human");
  return firstHuman >= 0 ? firstHuman : game.seat;
}

export interface SeatView {
  /** Seat whose private information the UI may show. */
  viewSeat: number | null;
  /** False while a hotseat hand-off curtain is up: board and actions are hidden. */
  revealed: boolean;
}

export const SeatViewContext = createContext<SeatView>({ viewSeat: null, revealed: true });

export const useSeatView = (): SeatView => useContext(SeatViewContext);
