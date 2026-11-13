import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import type { GameView } from "../../shell/useGame";
import CutAllPanel, { batchIds, cutPlan } from "./CutAllPanel";

function game(opts: {
  wood: number[];
  hired?: number;
  used?: number;
  area?: number;
  assign?: boolean;
  cp?: number;
}): GameView {
  const area = opts.area ?? 1;
  const areaWood = [0, 1, 2, 3, 4, 5].map((a) => (a === area ? opts.wood : [0, 0, 0]));
  const legal = opts.assign === false ? [] : [{ id: 174, label: "Assign" }];
  return {
    game: "lignum",
    seat: 0,
    current_player: opts.cp ?? 0,
    history_length: 10,
    legal_actions: legal,
    view: {
      phase: "W1",
      seat: 0,
      kind_names: ["firewood", "softwood", "hardwood"],
      picks: [area, 3],
      area_wood: areaWood,
      seats: [{ hired: { b: 0, w: opts.hired ?? 2, s: 0 }, cut_used: opts.used ?? 0 }],
    },
  } as unknown as GameView;
}

const ui = (onActBatch = vi.fn()) => ({ hoverAction: null, canAct: true, viewSeat: 0, onActBatch });

describe("CutAllPanel", () => {
  it("builds the id list: 2 woodcutters, area wood [3,0,0]", () => {
    const onActBatch = vi.fn();
    render(<CutAllPanel game={game({ wood: [3, 0, 0] })} ui={ui(onActBatch)} />);
    expect(screen.getByRole("status").textContent).toContain("2 firewood");
    fireEvent.click(screen.getByRole("button", { name: "Take 2 pieces" }));
    // area 1, kind 0: 177 + 3 = 180
    expect(onActBatch).toHaveBeenCalledTimes(1);
    expect(onActBatch).toHaveBeenCalledWith([174, 180, 174, 180]);
  });

  it("clamps to the wood available and leaves extra woodcutters unused", () => {
    const onActBatch = vi.fn();
    render(<CutAllPanel game={game({ wood: [1, 1, 0], hired: 5 })} ui={ui(onActBatch)} />);
    expect(screen.getByRole("status").textContent).toContain("3 woodcutters unused");
    fireEvent.click(screen.getByRole("button", { name: "Take 2 pieces" }));
    expect(onActBatch).toHaveBeenCalledWith([174, 180, 174, 181]);
  });

  it("stepper adjusts kinds within the woodcutter cap", () => {
    const onActBatch = vi.fn();
    render(<CutAllPanel game={game({ wood: [2, 2, 0], hired: 2 })} ui={ui(onActBatch)} />);
    fireEvent.click(screen.getByRole("button", { name: "Fewer firewood" }));
    fireEvent.click(screen.getByRole("button", { name: "More softwood" }));
    expect(screen.getByRole("button", { name: "More firewood" })).toBeDisabled(); // at cap
    fireEvent.click(screen.getByRole("button", { name: "Take 2 pieces" }));
    expect(onActBatch).toHaveBeenCalledWith([174, 180, 174, 181]);
  });

  it("is hidden when assigning is not legal, no woodcutters remain, or not our turn", () => {
    expect(cutPlan(game({ wood: [3, 0, 0], assign: false }))).toBeNull();
    expect(cutPlan(game({ wood: [3, 0, 0], hired: 2, used: 2 }))).toBeNull();
    expect(cutPlan(game({ wood: [3, 0, 0], cp: 1 }))).toBeNull();
    expect(cutPlan(game({ wood: [0, 0, 0] }))).toBeNull();
    const { container } = render(
      <CutAllPanel game={game({ wood: [3, 0, 0], assign: false })} ui={ui()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is disabled when the viewer cannot act", () => {
    render(
      <CutAllPanel
        game={game({ wood: [3, 0, 0] })}
        ui={{ hoverAction: null, canAct: false, viewSeat: 0, onActBatch: vi.fn() }}
      />,
    );
    expect(screen.getByRole("button", { name: "Take 2 pieces" })).toBeDisabled();
  });

  it("batchIds orders by kind", () => {
    expect(batchIds(0, [1, 0, 2])).toEqual([174, 177, 174, 179, 174, 179]);
  });
});
