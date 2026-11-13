import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { GameView } from "../../../shell/useGame";
import { ThemeProvider } from "../theme/ThemeProvider";
import { indexManifest } from "../theme/resolve";
import type { LoadedManifests, ThemeManifest } from "../theme/types";
import Board from "./Board";
import { LAYOUTS, type BoardSide } from "./layout";

const root = resolve(__dirname, "../../../../..");
/** Path locations per side, read from data/components/path.yaml (flow-style rows, no YAML dependency). */
function readPath(): Record<string, { number: number; kind: string }[]> {
  const out: Record<string, { number: number; kind: string }[]> = {};
  let side = "";
  for (const line of readFileSync(resolve(root, "data/components/path.yaml"), "utf8").split("\n")) {
    const hdr = /^  (base|joinery):/.exec(line);
    if (hdr) side = hdr[1]!;
    const m = /number: (\d+), kind: (\w+)/.exec(line);
    if (m && side) (out[side] ??= []).push({ number: Number(m[1]), kind: m[2]! });
    if (/^forest_clearing/.test(line)) side = "";
  }
  return out;
}
const pathYaml = { sides: Object.fromEntries(Object.entries(readPath()).map(([k, v]) => [k, { locations: v }])) } as {
  sides: Record<string, { locations: { number: number; kind: string }[] }>;
};

const ids = ["board", "board-joinery", "pawn-0", "pawn-1", "icon-raft", "icon-food", "piece-softwood-disk", "piece-firewood-disk", "piece-hardwood-disk"];
const manifest = (): ThemeManifest => ({
  assets: ids.map((id) => ({ id, category: "x", alt: id, file: `${id}.svg` })),
});
const urls = (m: ThemeManifest, tag: string) => Object.fromEntries(m.assets.map((a) => [a.file, `/${tag}/${a.file}`]));
const manifests: LoadedManifests = {
  official: indexManifest("official", manifest(), urls(manifest(), "o")),
  generic: indexManifest("generic", manifest(), urls(manifest(), "g")),
};

function game(joinery: boolean, extra: Record<string, unknown> = {}): GameView {
  return {
    game: "lignum",
    view: {
      seat: 0,
      game: { players: 2, joinery },
      high_areas: [2],
      area_wood: [[0, 2, 1], [0, 0, 0], [3, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
      area_food: [1, 0, 0, 0, 0, 0],
      picks: [[0, 1], [2]],
      foreman: [0, 4],
      clearing: [1],
      turn_order: [1, 0],
      path: { tokens: [{ spot: 1, location: 1, kind: "raft", taken: false }, { spot: 2, location: 2, kind: null, taken: true }] },
      ...extra,
    },
  } as unknown as GameView;
}

const wrap = (g: GameView, initial?: "generic") => (
  <ThemeProvider manifests={initial ? { generic: manifests.generic } : manifests} initialTheme="official">
    <Board game={g} />
  </ThemeProvider>
);

describe("layout", () => {
  for (const side of ["base", "joinery"] as BoardSide[]) {
    it(`${side}: 6 areas, every path location, coordinates in 0..1`, () => {
      const L = LAYOUTS[side];
      expect(L.areas.map((a) => a.n)).toEqual([1, 2, 3, 4, 5, 6]);
      const want = pathYaml.sides[side]!.locations.map((l) => l.number);
      expect(Object.keys(L.locations).map(Number).sort((a, b) => a - b)).toEqual(want);
      for (const l of pathYaml.sides[side]!.locations) {
        if (l.kind === "token_spot") expect(L.locations[l.number]?.spot, `${l.number}`).toBeDefined();
        else expect(L.locations[l.number]?.w, `${l.number}`).toBeDefined();
      }
      expect(L.turn).toHaveLength(4);
      expect(L.clearing).toHaveLength(4);
      const pts = [
        ...L.areas.flatMap((a) => [a, a.token]),
        ...Object.values(L.locations).flatMap((l) => (l.spot ? [l, l.spot] : [l])),
        L.start,
        ...L.turn,
        ...L.clearing,
      ];
      for (const p of pts) {
        expect(p.x).toBeGreaterThan(0);
        expect(p.x).toBeLessThan(1);
        expect(p.y).toBeGreaterThan(0);
        expect(p.y).toBeLessThan(1);
      }
    });
  }
});

describe("Board", () => {
  it.each([[false], [true]])("renders joinery=%s with labels", (joinery) => {
    const { container } = render(wrap(game(joinery)));
    expect(container.querySelector(".lgb")?.getAttribute("data-side")).toBe(joinery ? "joinery" : "base");
    expect(container.querySelector("img.lgb-img")?.getAttribute("src")).toBe(joinery ? "/o/board-joinery.svg" : "/o/board.svg");
    expect(screen.getByLabelText("Cutting area 1: 2 softwood, 1 hardwood, 1 food; picked by P0")).toBeInTheDocument();
    expect(screen.getByLabelText("Cutting area 3 (high wood): 3 firewood; picked by P1")).toBeInTheDocument();
    expect(screen.getByLabelText("Cutting area 2: empty; picked by P0")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 4; foremen: P1")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 1, token spot: raft")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 2, token spot: taken")).toBeInTheDocument();
    expect(screen.getByLabelText("Location 0 (start): P0")).toBeInTheDocument();
    expect(screen.getByLabelText("Clearing slot A: P1")).toBeInTheDocument();
    expect(screen.getByLabelText("Clearing slot B: empty")).toBeInTheDocument();
    expect(screen.getByLabelText("Starting player position 1: P1")).toBeInTheDocument();
    expect(screen.getAllByTestId("path-token")).toHaveLength(1);
  });

  it("generic-only theme (official absent) still renders", () => {
    const { container } = render(wrap(game(true), "generic"));
    expect(container.querySelector("img.lgb-img")?.getAttribute("src")).toBe("/g/board-joinery.svg");
  });

  it("survives a nearly empty view and unknown sprites", () => {
    const { container } = render(
      <ThemeProvider manifests={{}}>
        <Board game={{ game: "lignum", view: {} } as unknown as GameView} />
      </ThemeProvider>,
    );
    expect(container.querySelector("img.lgb-img")).toBeNull();
    expect(screen.getByLabelText("Cutting area 6: empty")).toBeInTheDocument();
    const bad = game(false, { area_wood: "x", foreman: null, picks: [null, "a"], path: { tokens: [{ location: 1, kind: "mystery", taken: false }] }, clearing: 5 });
    render(wrap(bad));
    expect(screen.getAllByLabelText("Cutting area 1: empty").length).toBeGreaterThan(0);
  });
});
