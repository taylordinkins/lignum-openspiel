import { fireEvent, render, screen } from "@testing-library/react";
import type { GameView } from "../../../shell/useGame";
import { ThemeProvider } from "../theme/ThemeProvider";
import { indexManifest } from "../theme/resolve";
import type { LoadedManifests, ThemeManifest } from "../theme/types";
import Board from "./Board";
import Sawmill from "./Sawmill";
import { GENERIC_PADS, PADS } from "./sawmillLayout";

const ids = ["sawmill", "player-extension", "board", "pawn-0", "pawn-1", "piece-softwood-disk", "piece-softwood-log", "piece-firewood-disk", "loan", "loan-back", "icon-food"];
const manifest = (): ThemeManifest => ({ assets: ids.map((id) => ({ id, category: "x", alt: id, file: `${id}.svg` })) });
const urls = (m: ThemeManifest, tag: string) => Object.fromEntries(m.assets.map((a) => [a.file, `/${tag}/${a.file}`]));
const manifests: LoadedManifests = {
  official: indexManifest("official", manifest(), urls(manifest(), "o")),
  generic: indexManifest("generic", manifest(), urls(manifest(), "g")),
};

const seat = (label: string, extra: Record<string, unknown> = {}) => ({
  label,
  money: 7,
  loans: 3,
  joiners: 1,
  food: 2,
  hired: { b: 1, w: 0, s: 2 },
  woodpile: [1, 0, 0],
  river: [0, 2, 0],
  sawing: [0, 1, 0],
  sale: [0, 1, 0],
  sale_logs: [0, 2, 0],
  store: [0, 0, 0],
  dry: [[0, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 0]],
  joinery_wood: [1, -1, -1],
  equip: [1, 0, 0, 1],
  held_craft: [1, 0, 0, 0, 0],
  held_tasks: [5],
  held_task_ids: ["T5"],
  fodder: [1, 0],
  buildings: [2],
  building_names: ["Inn"],
  small_storage: { kind: "softwood", spent: false },
  huts: { drying: 1, food: 0, worker: 0 },
  plans: [{ card: 1, name: "Pier", pair: 2, target: 4 }],
  ...extra,
});

function game(joinery: boolean, extra: Record<string, unknown> = {}): GameView {
  return {
    game: "lignum",
    view: {
      seat: 0,
      game: { players: 2, joinery },
      kind_names: ["firewood", "softwood", "hardwood"],
      equip_slots: ["saw", "wagon", "raft", "sledge"],
      craft_order: ["board", "shingle", "stake", "reed", "joker"],
      seats: [seat("P0"), seat("P1", { money: 2, sale_logs: [0, 0, 0], sale: [0, 0, 0], held_tasks: [], held_task_ids: [] })],
      tasks: { cards: [{ index: 5, id: "T5", reward: 6, requirements: [{ text: "2 softwood", filled: true }, { text: "firewood", filled: false }] }] },
      ...extra,
    },
  } as unknown as GameView;
}

const wrap = (g: GameView, m: LoadedManifests = manifests) => (
  <ThemeProvider manifests={m} initialTheme="official">
    <Sawmill game={g} />
  </ThemeProvider>
);

describe("sawmill layout", () => {
  it("the generic grid has the same regions as the official layout, inside its image", () => {
    for (const k of ["sawmill", "extension"] as const) {
      expect(Object.keys(GENERIC_PADS[k].regions).sort()).toEqual(Object.keys(PADS[k].regions).sort());
      for (const b of Object.values(GENERIC_PADS[k].regions)) {
        expect(b.x - b.w / 2).toBeGreaterThanOrEqual(0);
        expect(b.x + b.w / 2).toBeLessThanOrEqual(1);
        expect(b.y - b.h / 2).toBeGreaterThanOrEqual(0);
        expect(b.y + b.h / 2).toBeLessThanOrEqual(1);
      }
    }
  });
  it("every box lies inside its image", () => {
    for (const pad of Object.values(PADS))
      for (const b of Object.values(pad.regions)) {
        expect(b.x - b.w / 2).toBeGreaterThanOrEqual(0);
        expect(b.x + b.w / 2).toBeLessThanOrEqual(1);
        expect(b.y - b.h / 2).toBeGreaterThanOrEqual(0);
        expect(b.y + b.h / 2).toBeLessThanOrEqual(1);
      }
  });
});

describe("Sawmill", () => {
  it("labels each region for the viewed seat", () => {
    const { container } = render(wrap(game(false)));
    const has = (l: string) => expect(screen.getByLabelText(l), l).toBeInTheDocument();
    has("P0 sawmill");
    has("P0 river: 2 softwood logs");
    has("P0 sawing: 1 softwood log");
    has("P0 sale area: 1 softwood log, 2 softwood milled");
    has("P0 drying area 1: 1 softwood log");
    has("P0 drying area 2: 1 firewood milled");
    has("P0 drying area 3: empty");
    has("P0 storage: empty");
    has("P0 equipment: 1 saw, 1 sledge");
    has("P0 held craftwork: 1 board");
    has("P0 food storage: 2 food");
    has("P0 hired workers: 1 bearer, 2 sawyers");
    has("P0 huts: 1 drying hut");
    has("P0 fodder slots: value 3 filled, value 2 empty");
    has("P0 money: $7");
    has("P0 loans: 3");
    has("P0 woodpile: 1 firewood log");
    has("P0 held tasks: T5 (2 softwood filled; firewood open)");
    has("P0 planned work: Pier (pair 2, round 4)");
    expect(container.querySelectorAll('img[src="/o/loan-back.svg"]')).toHaveLength(1);
    expect(container.querySelectorAll('img[src="/o/loan.svg"]')).toHaveLength(1);
    expect(container.querySelector("img.lgs-img")?.getAttribute("src")).toBe("/o/sawmill.svg");
  });

  it("shows the woodpile in a strip above the boards, not in the ledger", () => {
    const { container } = render(wrap(game(false)));
    const wp = screen.getByLabelText("P0 woodpile: 1 firewood log");
    expect(wp).toHaveTextContent("Woodpile");
    expect(wp.className).toBe("lgs-woodpile");
    expect(wp.compareDocumentPosition(container.querySelector(".lgs-pads")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelector(".lgs-ledger")!.contains(wp)).toBe(false);
  });

  it("switches seats via the tab strip", () => {
    render(wrap(game(false)));
    expect(screen.getByRole("button", { name: "Show P0 sawmill" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Show P1 sawmill" }));
    expect(screen.getByLabelText("P1 sawmill")).toBeInTheDocument();
    expect(screen.getByLabelText("P1 sale area: empty")).toBeInTheDocument();
    expect(screen.getByLabelText("P1 money: $2")).toBeInTheDocument();
    expect(screen.getByLabelText("P1 held tasks: none")).toBeInTheDocument();
    expect(screen.queryByLabelText("P0 river: 2 softwood logs")).toBeNull();
  });

  it("joinery slots and extension only with the joinery side", () => {
    const base = render(wrap(game(false)));
    expect(screen.queryByLabelText(/joinery:/)).toBeNull();
    expect(base.container.querySelector(".lgs-ext")).toBeNull();
    base.unmount();
    const { container } = render(wrap(game(true)));
    expect(container.querySelector(".lgs-ext img")?.getAttribute("src")).toBe("/o/player-extension.svg");
    expect(screen.getByLabelText("P0 joinery: 1 joiner; joinery wood slot 1 softwood, slot 2 empty, slot 3 empty")).toBeInTheDocument();
    expect(screen.getByLabelText("P0 buildings: Inn")).toBeInTheDocument();
    expect(screen.getByLabelText("P0 small storage: softwood")).toBeInTheDocument();
  });

  it("uses the generic theme and survives missing sprites", () => {
    const { container } = render(wrap(game(true), { generic: manifests.generic }));
    expect(container.querySelector("img.lgs-img")?.getAttribute("src")).toBe("/g/sawmill.svg");
    expect(screen.getByLabelText("P0 river: 2 softwood logs")).toBeInTheDocument();
    render(wrap(game(false), {}));
    expect(screen.getAllByLabelText("P0 river: 2 softwood logs").length).toBeGreaterThan(0);
  });

  it("tolerates malformed input", () => {
    const { container, unmount } = render(wrap({ game: "lignum", view: {} } as unknown as GameView));
    expect(container.innerHTML).toBe("");
    unmount();
    const bad = game(true, {
      seats: [null, { label: 3, money: "x", dry: "no", equip: null, joinery_wood: "z", small_storage: null, plans: [null], held_tasks: ["a"], building_names: [1], hired: null }],
    });
    render(wrap(bad));
    expect(screen.getByLabelText("P0 sawmill")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show P1 sawmill" }));
    expect(screen.getByLabelText("P1 drying area 1: empty")).toBeInTheDocument();
    expect(screen.getByLabelText("P1 money: $0")).toBeInTheDocument();
  });
});

describe("Board path occupancy", () => {
  const view = (extra: Record<string, unknown>) =>
    ({
      game: "lignum",
      view: { seat: 0, game: { players: 2, joinery: false }, path: { locations: [], ...extra } },
    }) as unknown as GameView;
  const board = (g: GameView) => (
    <ThemeProvider manifests={manifests} initialTheme="official">
      <Board game={g} />
    </ThemeProvider>
  );

  it("draws foremen, pools, clearing slots and tokens from path.locations", () => {
    const g = view({
      locations: [
        { number: 4, kind: "bearers", name: "b", capacity: 2, foremen: [1], pool: 3, token: null },
        { number: 5, kind: "sawyers", name: "s", capacity: 1, foremen: [], pool: { free: 2, paid: 1 }, token: null },
        { number: 1, kind: "token_spot", name: "t", capacity: 1, foremen: [0], pool: null, token: { spot: 1, kind: "raft", taken: false } },
      ],
      clearing_slots: [null, 1, null, 0],
    });
    render(board(g));
    expect(screen.getByLabelText("Location 4; foremen: P1")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 4 pool: 3 bearers")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 5 pool: 2 free sawyers, 1 paid sawyers")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 1, token spot: raft; foremen: P0")).toBeInTheDocument();
    expect(screen.getAllByTestId("path-token")).toHaveLength(1);
    expect(screen.getByLabelText("Clearing slot A: empty")).toBeInTheDocument();
    expect(screen.getByLabelText("Clearing slot B: P1")).toBeInTheDocument();
    expect(screen.getByLabelText("Clearing slot D: P0")).toBeInTheDocument();
  });

  it("ignores malformed pools", () => {
    render(board(view({ locations: [{ number: 4, kind: "bearers", pool: "x", foremen: "no" }, null], clearing_slots: "no" })));
    expect(screen.getByLabelText("Location 4")).toBeInTheDocument();
    expect(screen.queryByTestId("pool-4")).toBeNull();
  });
});
