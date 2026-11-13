import { fireEvent, render, screen } from "@testing-library/react";
import type { GameView, LegalAction } from "../../shell/useGame";
import { areaSequence, boardTargets, sawmillSections } from "./board/sectionTargets";
import Sawmill from "./board/Sawmill";
import HutPicker from "./HutPicker";
import { ThemeProvider } from "./theme/ThemeProvider";

const la = (id: number, kind: string, params: number[], label: string): LegalAction => ({ id, kind, params, label });
const areas = [0, 1, 2].map((h) => la(141 + h, "HUT_AREA", [h], `Hut: assign token to area ${h}`));
const game = (legal: LegalAction[], open: unknown = { tokens: ["board", "stake", "shingle"], areas: [] }): GameView =>
  ({ game: "lignum", seat: 0, history_length: 5, legal_actions: legal, view: { seat: 0, huts: { open }, seats: [{ label: "P0", money: 1 }], foreman: [4] } }) as unknown as GameView;

describe("hut area picker", () => {
  const labels = ["drying", "food", "mill worker"];
  const click = (h: number) => fireEvent.click(screen.getByRole("button", { name: new RegExp(`hut area ${labels[h]},`) }));
  // every multiset of three areas, clicked in every order, yields the sorted non-decreasing sequence
  const splits: number[][] = [];
  for (let a = 0; a < 3; a++) for (let b = a; b < 3; b++) for (let c = b; c < 3; c++) splits.push([a, b, c]);
  for (const s of splits) {
    for (const order of [s, [...s].reverse()]) {
      it(`areas ${s.join("")} clicked as ${order.join("")} submits ${s.join("")}`, () => {
        const onActBatch = vi.fn();
        render(<HutPicker game={game(areas)} ui={{ hoverAction: null, canAct: true, onActBatch }} />);
        order.forEach(click);
        expect(onActBatch).toHaveBeenCalledTimes(1);
        expect(onActBatch).toHaveBeenCalledWith(s.map((h) => 141 + h));
      });
    }
  }

  it("counts per area and waits until all tokens are placed; reset clears", () => {
    const onActBatch = vi.fn();
    render(<HutPicker game={game(areas)} ui={{ hoverAction: null, canAct: true, onActBatch }} />);
    click(2);
    click(2);
    expect(screen.getByRole("button", { name: "Board: hut area mill worker, 2 tokens" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByRole("button", { name: "Board: hut area mill worker, 0 tokens" })).toBeVisible();
    expect(onActBatch).not.toHaveBeenCalled();
  });

  it("respects tokens already assigned and areas no longer legal", () => {
    const onActBatch = vi.fn();
    render(<HutPicker game={game(areas.slice(1), { tokens: ["a", "b", "c"], areas: ["food"] })} ui={{ hoverAction: null, canAct: true, onActBatch }} />);
    expect(screen.getByRole("button", { name: /hut area drying/ })).toBeDisabled();
    click(1);
    click(2);
    expect(onActBatch).toHaveBeenCalledWith([142, 143]);
  });

  it("areaSequence is sorted", () => {
    expect(areaSequence([1, 0, 2])).toEqual([0, 2, 2]);
  });
});

describe("section hotspots", () => {
  it("hires at the foreman's location open a popover with the choices", () => {
    const legal = [la(31, "HIRE_BEARER", [], "Hire a bearer"), la(32, "HIRE_SAWYER", [], "Hire a sawyer")];
    const t = boardTargets(legal, 4);
    expect(t).toHaveLength(1);
    expect(t[0]!.key).toBe("location-4");
    expect(t[0]!.actions.map((a) => a.id)).toEqual([31, 32]);
    expect(boardTargets(legal, undefined)).toEqual([]);
  });

  it("selling is anchored to the sawmill section of its zone", () => {
    const s = sawmillSections([la(400, "SELL", [0, 2], "Sell softwood disk from sale area"), la(401, "SELL", [2, 3], "x"), la(9, "TAKE_LOAN", [], "Take a loan")]);
    expect(Object.keys(s)).toEqual(["sale", "dry2"]);
  });

  it("clicking a sell hotspot on the own pad submits the action; other seats' pads have none", () => {
    const onAct = vi.fn();
    const g = game([la(400, "SELL", [0, 2], "Sell softwood disk from sale area")]);
    render(
      <ThemeProvider manifests={{}}>
        <Sawmill game={g} ui={{ hoverAction: null, canAct: true, onAct }} />
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Board: Sell softwood disk from sale area" }));
    expect(onAct).toHaveBeenCalledWith(400);
  });
});
