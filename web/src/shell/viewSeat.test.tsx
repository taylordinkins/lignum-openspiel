import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import GameScreen from "./GameScreen";
import { deriveViewSeat } from "./viewSeat";
import type { GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const POLL = { fast: 20, slow: 20 };

function view(over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "lignum",
    seats: ["human", "human"],
    seat_types: ["human", "human"],
    bot_thinking: false,
    seat: 0,
    history_length: 0,
    history: [{ index: 0, actor: 0, id: 1, label: "SECRET-LOG" }],
    dev_mode: false,
    current_player: 0,
    is_terminal: false,
    legal_actions: [{ id: 3, label: "Play A" }],
    returns: null,
    winners: null,
    view: {},
    ...over,
  };
}

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
});

describe("deriveViewSeat", () => {
  it("falls back to the first human seat, never a bot seat", () => {
    const g = view({ seats: ["random", "human"], current_player: 0, seat: 0 });
    expect(deriveViewSeat(g, null)).toBe(1);
  });
  it("keeps game.seat in an all-bot game", () => {
    const g = view({ seats: ["random", "random"], current_player: 0, seat: 1 });
    expect(deriveViewSeat(g, null)).toBe(1);
  });
});

describe("view seat mismatch", () => {
  it("shows no board or log and keeps the curtain closed while data is for another seat", async () => {
    let phase = 0;
    let served = 0;
    GET.mockImplementation(async () => {
      if (phase === 0) return { data: view({ history: [] }) };
      served += 1;
      // Server keeps rendering seat 0 although seat 1 was requested.
      return { data: view({ seat: 0, current_player: 1 }) };
    });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByText("Play A");
    phase = 1;
    await screen.findByText(/Pass to P1/);
    await waitFor(() => expect(served).toBeGreaterThan(1));
    expect(screen.getByRole("button", { name: /click when ready/i })).toBeDisabled();
    expect(document.body.textContent).not.toContain("SECRET-LOG");
    expect(document.body.textContent).not.toContain("Action log");
    expect(screen.queryByText("Play A")).toBeNull();
  });

  it("sends the view seat with actions", async () => {
    GET.mockResolvedValue({ data: view({ seat: 0, current_player: 0 }) });
    POST.mockResolvedValue({ data: view({ seat: 0, current_player: 1 }) });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/actions", {
      params: { path: { game_id: "g1" }, query: { seat: 0 } },
      body: { action: 3 },
    });
  });
});
