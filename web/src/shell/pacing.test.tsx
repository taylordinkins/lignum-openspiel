import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import GameScreen from "./GameScreen";
import { updateSettings } from "./settings";
import type { GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) } }));

const POLL = { fast: 20, slow: 20 };

/** P0 human, P1 random; `n` history entries alternating P0, P1. */
function view(n: number, over: Partial<GameView> = {}): GameView {
  const cp = n % 2;
  return {
    id: "g1",
    game: "generic-test",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    bot_thinking: cp === 1,
    seat: 0,
    history_length: n,
    history: Array.from({ length: n }, (_, i) => ({ index: i, actor: i % 2, id: 10 + i, label: `m${i}`, events: [] })),
    dev_mode: false,
    current_player: cp,
    is_terminal: false,
    legal_actions: cp === 0 ? [{ id: 3, label: "Play A" }] : [],
    returns: null,
    winners: null,
    view: { n },
    ...over,
  };
}

/** GET answers: the live game is `live()`; `?at=k` frames are view(k). */
function serve(live: () => GameView) {
  GET.mockImplementation(async (_path: string, opts: { params?: { query?: { at?: number } } }) => {
    const at = opts?.params?.query?.at;
    return { data: at === undefined ? live() : view(at) };
  });
}

const stateText = () => screen.getByLabelText("Game state").textContent ?? "";

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
});

describe("unit6b bot pacing through the shell (UI_DESIGN 7)", () => {
  it("bot moves are held at the pace; input is off meanwhile; Skip to my turn fast-forwards", async () => {
    updateSettings({ botPace: 2 });
    let live = view(1); // P1 (bot) to move
    serve(() => live);
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await waitFor(() => expect(stateText()).toContain('"n": 1'));
    live = view(4); // the bot played twice around a P0 move; P0 to move
    await waitFor(() => expect(screen.getByRole("button", { name: /skip to my turn/i })).toBeInTheDocument());
    expect(stateText()).toContain('"n": 1');
    expect(screen.queryByRole("button", { name: "Play A" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /skip to my turn/i }));
    await waitFor(() => expect(stateText()).toContain('"n": 4'));
    expect(screen.queryByRole("button", { name: /skip to my turn/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Play A" })).toBeEnabled();
  });

  it("pace 0: the latest state shows at once and no frames are fetched", async () => {
    updateSettings({ botPace: 0 });
    let live = view(1);
    serve(() => live);
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await waitFor(() => expect(stateText()).toContain('"n": 1'));
    live = view(4);
    await waitFor(() => expect(stateText()).toContain('"n": 4'));
    const frames = GET.mock.calls.filter((c) => (c[1] as { params?: { query?: { at?: number } } })?.params?.query?.at !== undefined);
    expect(frames).toHaveLength(0);
  });

  it("paced bot moves arrive one frame at a time", async () => {
    updateSettings({ botPace: 0.1 });
    let live = view(0);
    serve(() => live);
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await waitFor(() => expect(stateText()).toContain('"n": 0'));
    live = view(4);
    await waitFor(() => expect(stateText()).toContain('"n": 2'));
    await waitFor(() => expect(stateText()).toContain('"n": 4'));
    const ats = GET.mock.calls
      .map((c) => (c[1] as { params?: { query?: { at?: number } } })?.params?.query?.at)
      .filter((a) => a !== undefined);
    // steps end after entries 1 (P0), 2 (P1 bot), 3 (P0), 4 (P1 bot = the live view itself)
    expect(ats).toEqual([1, 2, 3]);
  });
});
