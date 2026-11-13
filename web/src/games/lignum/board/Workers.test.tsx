import { render, screen } from "@testing-library/react";
import type { GameView } from "../../../shell/useGame";
import { ThemeProvider } from "../theme/ThemeProvider";
import { indexManifest } from "../theme/resolve";
import type { LoadedManifests, ThemeManifest } from "../theme/types";
import Sawmill, { WORKER_SPRITES, workerItems } from "./Sawmill";
import { PADS } from "./sawmillLayout";

const ids = ["sawmill", "player-extension", "worker-bearer", "worker-woodcutter", "worker-sawyer", "worker-joiner", "mill-worker-0", "building-inn", "building-office"];
const m: ThemeManifest = { assets: ids.map((id) => ({ id, category: "x", alt: id, file: `${id}.svg` })) };
const manifests: LoadedManifests = { official: indexManifest("official", m, Object.fromEntries(m.assets.map((a) => [a.file, `/o/${a.file}`]))), generic: indexManifest("generic", m, {}) };

const game = (seat: Record<string, unknown>): GameView =>
  ({
    game: "lignum",
    view: { seat: 0, game: { players: 2, joinery: true }, seats: [{ label: "P0", joiners: 2, hired: { b: 2, w: 1, s: 1 }, building_names: ["inn", "office"], ...seat }] },
  }) as unknown as GameView;
const wrap = (g: GameView) => (
  <ThemeProvider manifests={manifests} initialTheme="official">
    <Sawmill game={g} />
  </ThemeProvider>
);

describe("worker colours", () => {
  it("maps each hired kind to its own sprite with a count", () => {
    expect(WORKER_SPRITES).toEqual({ b: "worker-bearer", w: "worker-woodcutter", s: "worker-sawyer" });
    expect(workerItems({ b: 2, w: 0, s: 1 }).map((i) => [i.sprite, i.n, i.text])).toEqual([
      ["worker-bearer", 2, "2 bearers"],
      ["worker-sawyer", 1, "1 sawyer"],
    ]);
  });

  it("draws hired workers, the mill worker and the joiner", () => {
    const { container } = render(wrap(game({})));
    const src = (sel: string) => Array.from(container.querySelectorAll(`${sel} img`)).map((i) => i.getAttribute("src"));
    expect(src(".lgs-hired")).toEqual(["/o/worker-bearer.svg", "/o/worker-woodcutter.svg", "/o/worker-sawyer.svg"]);
    expect(src(".lgs-mill")).toEqual(["/o/mill-worker-0.svg"]);
    expect(screen.getByLabelText("P0 mill worker: in the worker area")).toBeInTheDocument();
    expect(container.querySelector('[aria-label^="P0 joinery"] img')?.getAttribute("src")).toBe("/o/worker-joiner.svg");
  });

  it("shows the mill worker as away once used", () => {
    const { container } = render(wrap(game({ mill_used: true })));
    expect(screen.getByLabelText("P0 mill worker: used, away from the worker area")).toBeInTheDocument();
    expect(container.querySelector(".lgs-mill .lgs-off")).not.toBeNull();
  });
});

describe("building overlay", () => {
  it("places each taken building over its slot", () => {
    const { container } = render(wrap(game({})));
    expect(screen.getByLabelText("P0 building space 1: inn")).toBeInTheDocument();
    expect(screen.getByLabelText("P0 building space 2: office")).toBeInTheDocument();
    expect(container.querySelector('[aria-label="P0 building space 1: inn"] img')?.getAttribute("src")).toBe("/o/building-inn.svg");
    expect(container.querySelector('[aria-label="P0 building space 2: office"] [title="office"]')).not.toBeNull();
  });

  it("leaves a free slot empty and has slot boxes in the layout", () => {
    render(wrap(game({ building_names: ["inn"] })));
    expect(screen.getByLabelText("P0 building space 2: empty")).toBeInTheDocument();
    expect(Object.keys(PADS.extension.regions)).toEqual(expect.arrayContaining(["building_slot_1", "building_slot_2"]));
  });
});
