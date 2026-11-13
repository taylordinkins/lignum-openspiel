import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import GameScreen from "./GameScreen";
import Lobby from "./Lobby";
import type { GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) } }));

const POLL = { fast: 20, slow: 20 };

function view(over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "lignum",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    bot_thinking: false,
    seat: 0,
    history_length: 0,
    history: [],
    dev_mode: false,
    current_player: 0,
    is_terminal: false,
    legal_actions: [
      { id: 3, label: "Play A" },
      { id: 4, label: "Pass" },
    ],
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

describe("Lobby", () => {
  it("creates a game with chosen seats and seed", async () => {
    POST.mockResolvedValue({ data: view({ id: "abc" }) });
    const onCreated = vi.fn();
    render(<Lobby onCreated={onCreated} />);
    fireEvent.change(screen.getByLabelText("Seat P1"), { target: { value: "human" } });
    fireEvent.change(screen.getByLabelText(/Seed/), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "Create game" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("abc"));
    expect(POST).toHaveBeenCalledWith("/api/games", {
      body: {
        game: "lignum",
        params: { num_players: 2, joinery: true, returns: "win_loss" },
        seats: ["human", "human"],
        seed: 42,
      },
    });
  });

  it.each([3, 4])("creates a %i-seat game with options", async (n) => {
    POST.mockResolvedValue({ data: view({ id: "abc" }) });
    render(<Lobby onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Players"), { target: { value: String(n) } });
    expect(screen.getByLabelText("Seat P0")).toBeInTheDocument();
    expect(screen.getByLabelText(`Seat P${n - 1}`)).toBeInTheDocument();
    expect(screen.queryByLabelText(`Seat P${n}`)).toBeNull();
    expect(screen.queryByLabelText("Seat 1")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Joinery/));
    fireEvent.change(screen.getByLabelText("Returns"), { target: { value: "margin" } });
    fireEvent.click(screen.getByRole("button", { name: "Create game" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST).toHaveBeenCalledWith("/api/games", {
      body: {
        game: "lignum",
        params: { num_players: n, joinery: false, returns: "margin" },
        seats: ["human", "random", "random", "random"].slice(0, n),
      },
    });
  });

  it("shows an error when creation fails", async () => {
    POST.mockResolvedValue({ error: { detail: "bad seats" } });
    render(<Lobby onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create game" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("bad seats");
  });
});

describe("GameScreen", () => {
  it("renders legal actions and posts the clicked one", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ data: view({ current_player: 0, legal_actions: [{ id: 9, label: "Next" }] }) });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/actions", {
      params: { path: { game_id: "g1" }, query: { seat: 0 } },
      body: { action: 3 },
    });
    expect(await screen.findByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("disables buttons while a request is in flight", async () => {
    GET.mockResolvedValue({ data: view() });
    let resolve: (v: unknown) => void = () => {};
    POST.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Pass" })).toBeDisabled());
    await act(async () => resolve({ data: view() }));
    expect(screen.getByRole("button", { name: "Pass" })).toBeEnabled();
  });

  it("shows an error for a rejected action", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ error: { detail: "action 3 is not legal" } });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("action 3 is not legal");
    expect(screen.getByRole("button", { name: "Play A" })).toBeInTheDocument();
  });

  it("polls through bot thinking and stops at game over", async () => {
    GET.mockResolvedValueOnce({ data: view({ bot_thinking: true, current_player: 1 }) })
      .mockResolvedValueOnce({
        data: view({ current_player: null, is_terminal: true, legal_actions: [], returns: [1, -1], winners: [0] }),
      });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    expect(await screen.findByRole("status")).toHaveTextContent(/thinking/i);
    expect(screen.queryByRole("button", { name: "Play A" })).toBeNull();
    expect(await screen.findByText("Game over")).toBeInTheDocument();
    expect(screen.getByText("P0 wins")).toBeInTheDocument();
    expect(screen.getByText(/Returns: P0 1, P1 -1/)).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
    const calls = GET.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(GET.mock.calls.length).toBe(calls);
  });

  it("lists every winner on a tie and shows final dollars", async () => {
    GET.mockResolvedValue({
      data: view({
        seats: ["human", "random", "random"],
        current_player: null,
        is_terminal: true,
        legal_actions: [],
        returns: [0, 0, -1],
        winners: [0, 1],
        view: { final: [12, 12, -3] },
      }),
    });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    expect(await screen.findByText("Tie: P0, P1 win")).toBeInTheDocument();
    expect(screen.getByText(/Final dollars: P0 \$12, P1 \$12, P2 -\$3/)).toBeInTheDocument();
  });

  it("labels seats P0-based and groups actions by kind", async () => {
    GET.mockResolvedValue({
      data: view({
        legal_actions: [
          { id: 3, label: "Play A", kind: "hire" },
          { id: 4, label: "Pass", kind: "pass" },
        ],
      }),
    });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    await screen.findByRole("button", { name: "Play A" });
    expect(screen.getByText(/Current player: P0 \(human\)/)).toBeInTheDocument();
    expect(screen.getByText(/P0 human, P1 random/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Player 1|Seat 1\b/);
    expect(screen.getByRole("list", { name: "Legal actions: hire" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Legal actions: pass" })).toBeInTheDocument();
  });

  it("requests the view of the human seat to move (hotseat)", async () => {
    GET.mockImplementation((_p: string, o: { params: { query?: { seat: number } } }) =>
      Promise.resolve({
        data: view({ seats: ["human", "human"], current_player: 1, seat: o.params.query?.seat ?? 0 }),
      }),
    );
    const onSeatChange = vi.fn();
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} onSeatChange={onSeatChange} />);
    await screen.findByRole("button", { name: "Play A" });
    await waitFor(() => expect(onSeatChange).toHaveBeenLastCalledWith(1));
    await waitFor(() =>
      expect(GET).toHaveBeenLastCalledWith("/api/games/{game_id}", {
        params: { path: { game_id: "g1" }, query: { seat: 1 } },
      }),
    );
  });

  it("hides the board and actions while not revealed", async () => {
    GET.mockResolvedValue({ data: view() });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} revealed={false} />);
    await screen.findByText("Board hidden.");
    expect(screen.queryByRole("button", { name: "Play A" })).toBeNull();
  });

  it("stops polling on unmount", async () => {
    GET.mockResolvedValue({ data: view() });
    const { unmount } = render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByRole("button", { name: "Pass" });
    unmount();
    const calls = GET.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(GET.mock.calls.length).toBe(calls);
  });

  it("shows a load error without crashing", async () => {
    GET.mockResolvedValue({ error: { detail: "unknown game 'zz'" } });
    render(<GameScreen gameId="zz" pollMs={POLL} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("unknown game");
  });
});

describe("Hotseat curtain", () => {
  const lv = (seat: number, pick: number | null, cp: number): GameView =>
    view({
      seats: ["human", "human"],
      seat_types: ["human", "human"],
      seat,
      current_player: cp,
      view: { seat, phase: "PK", round: 2, private: { pick }, picked: [] },
    });

  it("covers the new seat's view until clicked, with none of its private data in the DOM", async () => {
    let cp = 0;
    GET.mockImplementation(async (_p: string, o: { params: { query?: { seat?: number } } }) => ({
      data: cp === 0 ? lv(0, 1, 0) : lv(1, 4, 1),
      o,
    }));
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByText(/Your hidden pick: area 2/);
    expect(screen.queryByText(/Pass to/)).toBeNull();
    cp = 1;
    await screen.findByText(/Pass to P1/);
    expect(document.body.textContent).not.toMatch(/area 5/);
    expect(document.body.textContent).not.toContain("Action log");
    expect(screen.queryByText("Play A")).toBeNull();
    await new Promise((r) => setTimeout(r, 80));
    expect(document.body.textContent).not.toMatch(/area 5/);
    fireEvent.click(screen.getByRole("button", { name: /click when ready/i }));
    await screen.findByText(/Your hidden pick: area 5/);
    expect(screen.queryByText(/Pass to/)).toBeNull();
  });

  it("never shows the curtain with a single human seat", async () => {
    GET.mockResolvedValue({ data: view({ view: { seat: 0, phase: "PK" } }) });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByText("Play A");
    expect(screen.queryByText(/Pass to/)).toBeNull();
  });
});
