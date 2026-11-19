import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { GameView } from "../../shell/useGame";
import SeatPanels from "./SeatPanels";

const game = (over: Record<string, unknown> = {}) =>
  ({
    game: "lignum",
    seat: 0,
    seats: ["human", "random"],
    current_player: 1,
    legal_actions: [{ id: 1, label: "x" }],
    history: [],
    view: {
      turn_order: [1, 0],
      seats: [
        { label: "P0", money: -3, loans: 2, food: 4, joiners: 1, hired: { b: 1, w: 0, s: 2 }, held_tasks: [1], building_names: ["a", "b"] },
        { label: "P1", money: 12 },
      ],
    },
    ...over,
  }) as unknown as GameView;

describe("SeatPanels", () => {
  it("shows a panel per seat with money, tags and public counters", () => {
    render(<SeatPanels game={game()} />);
    const p0 = screen.getByRole("article", { name: "Seat P0" });
    expect(p0).toHaveTextContent("-$3");
    expect(p0).toHaveTextContent("You");
    expect(within(p0).getByText("Loans").nextSibling).toHaveTextContent("2");
    expect(within(p0).getByText("1/0/2")).toBeInTheDocument();
    const p1 = screen.getByRole("article", { name: "Seat P1" });
    expect(p1).toHaveTextContent("Random bot");
    expect(p1).toHaveTextContent("TO ACT");
    expect(p1).toHaveTextContent("FIRST");
    expect(p0).not.toHaveTextContent("TO ACT");
  });

  it("keeps the per-seat Money group", () => {
    render(<SeatPanels game={game()} />);
    const money = screen.getByRole("group", { name: "Money" });
    expect(within(money).getByLabelText("P1 money $12")).toBeInTheDocument();
  });
});
