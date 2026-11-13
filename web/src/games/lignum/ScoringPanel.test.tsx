import { render, screen, within } from "@testing-library/react";
import type { GameView } from "../../shell/useGame";
import ScoringPanel from "./ScoringPanel";
import CardsPanel from "./CardsPanel";
import { ThemeProvider } from "./theme/ThemeProvider";
import { indexManifest } from "./theme/resolve";

const seats = (n: number) => Array.from({ length: n }, (_, i) => ({ label: `P${i}` }));
const sc = (o: Record<string, number>) => ({ money: 0, wood_sale: 0, river_sale: 0, joinery_sale: 0, office: 0, tasks: 0, loan_repay: 0, final: 0, ...o });
const game = (view: Record<string, unknown>) => ({ view: { is_terminal: true, ...view } }) as unknown as GameView;

describe("ScoringPanel", () => {
  it("renders nothing before the game ends", () => {
    const { container } = render(<ScoringPanel game={game({ is_terminal: false })} />);
    expect(container.textContent).toBe("");
  });

  it("shows the breakdown and a sole winner with seat 0 labelled P0", () => {
    render(
      <ScoringPanel
        game={game({
          seats: seats(2),
          final: [45, 10],
          winners: [0],
          returns: [1, -1],
          score: [sc({ money: 20, wood_sale: 15, tasks: 17, loan_repay: -7, final: 45 }), sc({ money: 10, final: 10 })],
        })}
      />,
    );
    expect(screen.getByLabelText("Winners").textContent).toBe("Winner: P0");
    expect(screen.queryByText(/Player 1/)).toBeNull();
    const row = within(screen.getByRole("table", { name: "Final scores" })).getByRole("row", { name: /^P0/ });
    const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toEqual(["$20", "$15", "$0", "$0", "$0", "$17", "-$7", "$45", "1.000"]);
  });

  it("shows a tie as shared", () => {
    render(<ScoringPanel game={game({ seats: seats(3), final: [60, 60, 20], winners: [0, 1], returns: [0.25, 0.25, -0.5], score: [sc({ final: 60 }), sc({ final: 60 }), sc({ final: 20 })] })} />);
    expect(screen.getByLabelText("Winners").textContent).toBe("Tie: P0, P1 share the win");
    expect(screen.getByText("-0.500")).toBeTruthy();
  });

  it("handles margin returns and missing keys without crashing", () => {
    render(<ScoringPanel game={game({ final: [59, 41], winners: [0], returns: [0.36, -0.36] })} />);
    expect(screen.getByText("0.360")).toBeTruthy();
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
    render(<ScoringPanel game={game({})} />);
  });
});

describe("CardsPanel", () => {
  it("renders card lists from a sparse view and text fallbacks", () => {
    const manifests = { generic: indexManifest("generic", { assets: [] }, {}) };
    render(
      <ThemeProvider manifests={manifests}>
        <CardsPanel
          game={game({
            is_terminal: false,
            round: 2,
            seats: [{ label: "P0", loans: 3, held_tasks: [1], held_task_ids: ["task 02"], building_names: ["Inn"] }],
            tasks: { row: [1], cards: [{ index: 1, id: "task 02", reward: 16, requirements: [{ text: "hardwood", filled: false }] }] },
            winter: { card_ids: ["winter-1-2", "winter-2-1"], cards: [{ year: 1, food: 6, heating: 3 }, { year: 2, food: 1, heating: 1 }] },
          })}
        />
      </ThemeProvider>,
    );
    expect(screen.getByRole("group", { name: "Task row" }).textContent).toContain("$16 for hardwood");
    expect(screen.getByRole("group", { name: "Winter cards, year 1" }).textContent).toContain("food 6, heating 3");
    expect(screen.queryByRole("group", { name: "Winter cards, year 2" })).toBeNull();
    expect(screen.getByRole("group", { name: "P0 buildings" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "P0 loans" }).querySelectorAll("[data-testid=lgc-card]")).toHaveLength(2);
  });
});
