import { render } from "@testing-library/react";
import type { GameView } from "../../shell/useGame";
import TextBoard from "./TextBoard";

function seat(money: number) {
  return {
    money,
    loans: 1,
    joiners: 2,
    food: 3,
    hired: { b: 1, w: 0, s: 2 },
    woodpile: [1, 2],
    river: [],
    sawing: [],
    sale: [],
    sale_logs: [],
    store: [],
    dry: [],
    joinery_wood: [],
    equip: ["raft"],
    held_craft: [],
    held_tasks: [],
  };
}

function game(n: number, view: Record<string, unknown>): GameView {
  const base = {
    seat: 0,
    private: { pick: null },
    round: 2,
    phase: "W1",
    is_terminal: false,
    current_player: 0,
    picks: Array.from({ length: n }, () => []),
    picked: [],
    high_areas: [2],
    area_wood: [0, 1, 2, 3, 4, 5].map((i) => [i, 1, 0]),
    area_food: [0, 1, 0, 0, 0, 1],
    turn_order: [1, 0],
    clearing: [0, 1],
    foreman: Array.from({ length: n }, () => "none"),
    seats: Array.from({ length: n }, (_, i) => seat(10 + i)),
    path: {
      boys: 1,
      women: 2,
      sf: 3,
      sp: 4,
      fodder: 5,
      joiner: 6,
      tokens: TOKENS,
    },
    tasks: { row: [7, 8], filled: [] },
    winter: { order: [1, 0], pay: 3, sf_due: 1 },
    ...view,
  };
  return { game: "lignum", view: base } as unknown as GameView;
}

const TOKENS = [
  { spot: 1, location: 1, kind: "raft", taken: false },
  { spot: 2, location: 2, kind: null, taken: true },
];

const text = (c: HTMLElement) => c.textContent ?? "";

describe("TextBoard", () => {
  it("renders every section for a 2-player game", () => {
    const { container, getByLabelText, getByText } = render(
      <TextBoard game={game(2, {})} />,
    );
    for (const l of [
      "Overview",
      "Cutting areas",
      "Seats",
      "Path",
      "Task cards",
      "Winter",
    ])
      getByLabelText(l);
    getByText("Round 2");
    expect(
      container.querySelectorAll("table tbody tr").length,
    ).toBeGreaterThanOrEqual(6 + 10);
    expect(text(container)).toContain("P1");
    expect(text(container)).toContain("$11");
    expect(text(container)).toContain("To moveP0");
    expect(text(container)).toContain("High-wood areas3");
  });

  it("labels the path and supply rows with rulebook terms and the view's values", () => {
    const { container } = render(<TextBoard game={game(2, {})} />);
    const t = text(
      container.querySelector("section[aria-label='Path']") as HTMLElement,
    );
    expect(t).toContain("Bearers1");
    expect(t).toContain("Woodcutters2");
    expect(t).toContain("Sawyers ($0)3");
    expect(t).toContain("Sawyers ($1)4");
    expect(t).toContain("Fodder5");
    expect(t).toContain("Joiner6");
    expect(t).not.toMatch(/Boys|Women|Sawmill (food|pay)\b(?! due)/);
  });

  it("labels equipment and wood kinds by name, not as bare arrays", () => {
    const seats = [
      {
        ...seat(10),
        equip: [1, 0, 2, 1],
        woodpile: [0, 3, 1],
        held_craft: [0, 2, 0, 0, 1],
      },
    ];
    const { container } = render(
      <TextBoard
        game={game(1, {
          seats,
          equip_slots: ["saw", "wagon", "raft", "sledge"],
          kind_names: ["firewood", "softwood", "hardwood"],
          craft_order: ["board", "shingle", "stake", "reed", "joker"],
        })}
      />,
    );
    const t = text(
      container.querySelector("section[aria-label='Seats']") as HTMLElement,
    );
    expect(t).toContain("saws 1, wagons 0, rafts 2, sledges 1");
    expect(t).toContain("softwood 3, hardwood 1");
    expect(t).toContain("shingle 2, joker 1");
    expect(t).not.toContain("1, 0, 2, 1");
  });

  it("renders a 4-player seat table", () => {
    const { container } = render(<TextBoard game={game(4, {})} />);
    const heads = [...container.querySelectorAll("th[scope=col]")].map(
      (e) => e.textContent,
    );
    expect(heads).toEqual(["P0", "P1", "P2", "P3"]);
  });

  it("shows own hidden pick and only who else has picked, never what", () => {
    const { container } = render(
      <TextBoard
        game={game(4, {
          phase: "PK",
          seat: 0,
          private: { pick: 2 },
          picked: [0, 1],
        })}
      />,
    );
    const t = text(container);
    expect(t).toContain("Your hidden pick: area 3");
    expect(t).toContain("P1 has picked");
    expect(t).not.toContain("P0 has picked");
    expect(t).not.toContain("P2 has picked");
  });

  it("does not print another seat's pick before reveal", () => {
    const { container } = render(
      <TextBoard
        game={game(2, {
          phase: "PK",
          seat: 0,
          private: { pick: null },
          picked: [1],
        })}
      />,
    );
    const t = text(container);
    expect(t).toContain("P1 has picked");
    expect(t).not.toContain("Your hidden pick");
    const rows = [
      ...container.querySelectorAll(
        "section[aria-label='Cutting areas'] tbody td:last-child",
      ),
    ];
    expect(rows.every((r) => r.textContent === "-")).toBe(true);
  });

  it("shows revealed picks per area after the reveal", () => {
    const { container } = render(
      <TextBoard game={game(2, { phase: "W1", picks: [[0], [3]] })} />,
    );
    const rows = [
      ...container.querySelectorAll(
        "section[aria-label='Cutting areas'] tbody tr",
      ),
    ];
    expect(rows[0]?.textContent).toContain("P0");
    expect(rows[3]?.textContent).toContain("P1");
  });

  it("shows final dollars and winners at game over", () => {
    const { container } = render(
      <TextBoard
        game={game(2, {
          is_terminal: true,
          current_player: null,
          final: [5, -2],
          winners: [0],
        })}
      />,
    );
    const t = text(container);
    expect(t).toContain("Final dollarsP0 $5, P1 -$2");
    expect(t).toContain("WinnersP0");
    expect(t).toContain("game over");
  });

  it("never prints Player N or a JSON dump, and tolerates an empty view", () => {
    const { container } = render(<TextBoard game={game(3, {})} />);
    const t = text(container);
    expect(t).not.toMatch(/Player \d/);
    expect(t).not.toMatch(/[{}"]/);
    expect(() =>
      render(
        <TextBoard
          game={{ game: "lignum", view: {} } as unknown as GameView}
        />,
      ),
    ).not.toThrow();
  });

  it("shows the public winter food and heating requirements per year", () => {
    const { container } = render(
      <TextBoard
        game={game(2, {
          winter: {
            order: [],
            pay: 0,
            sf_due: 0,
            cards: [
              { year: 1, food: 7, heating: 6 },
              { year: 2, food: 9, heating: 8 },
            ],
          },
        })}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toMatch(/Winter 1[^]*food 7[^]*heating 6/);
    expect(text).toMatch(/Winter 2[^]*food 9[^]*heating 8/);
  });
});

describe("TextBoard token spots", () => {
  it("names each token by spot and location, and shows taken spots", () => {
    const { getByLabelText, container } = render(
      <TextBoard game={game(2, {})} />,
    );
    const items = Array.from(
      getByLabelText("Token spots").querySelectorAll("li"),
    ).map((li) => li.textContent);
    expect(items).toEqual([
      "Spot 1 (Location 1): raft",
      "Spot 2 (Location 2): taken",
    ]);
    expect(container.textContent).not.toContain("-1");
  });
});

describe("TextBoard task cards", () => {
  it("shows card ids for the row, filled and held tasks, never raw indices", () => {
    const base = game(2, {}).view as { seats: Record<string, unknown>[] };
    const seats = base.seats.map((s, i) => ({
      ...s,
      held_tasks: i === 0 ? [6] : [],
      held_task_ids: i === 0 ? ["task 07"] : [],
    }));
    const { container } = render(
      <TextBoard
        game={game(2, {
          seats,
          tasks: {
            row: [0, 6, 7, 17],
            row_ids: ["task 01", "task 07", "task 08", "task 18"],
            filled: [0, 1],
            filled_ids: ["task 02"],
          },
        })}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("task 01, task 07, task 08, task 18");
    expect(text).not.toContain("0, 6, 7, 17");
    expect(text).toContain("task 02");
  });
});

describe("TextBoard phase label", () => {
  it("shows the phase label, not a bare code", () => {
    const { container } = render(
      <TextBoard
        game={game(2, { phase: "W3", phase_label: "W3 · Transportation" })}
      />,
    );
    expect(text(container)).toContain("W3 · Transportation");
    expect(text(container)).not.toMatch(/Phase\s*W3(?!\s·)/);
  });
});
