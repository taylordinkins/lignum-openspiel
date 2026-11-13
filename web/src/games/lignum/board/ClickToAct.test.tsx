import { fireEvent, render, screen } from "@testing-library/react";
import type { GameView, LegalAction } from "../../../shell/useGame";
import type { BoardUi } from "../../registry";
import { ThemeProvider } from "../theme/ThemeProvider";
import Board from "./Board";

const la = (id: number, kind: string, params: number[], label: string): LegalAction => ({ id, kind, params, label });

function game(legal: LegalAction[]): GameView {
  return { game: "lignum", legal_actions: legal, view: { seat: 0, game: { players: 2, joinery: false }, foreman: [0, 0], clearing: [1] } } as unknown as GameView;
}
const mount = (legal: LegalAction[], ui?: BoardUi) =>
  render(
    <ThemeProvider manifests={{}}>
      <Board game={game(legal)} ui={ui} />
    </ThemeProvider>,
  );

const pick = la(4, "PICK_AREA", [2], "Pick cutting area 3");
const move = la(10, "MOVE_TO", [3], "Move to Bearers (location 3)");
const clear = la(30, "MOVE_TO", [23], "Move to the forest clearing");
const wood = [la(180, "TAKE_WOOD", [1, 0], "Take firewood from cutting area 2"), la(181, "TAKE_WOOD", [1, 1], "Take softwood from cutting area 2")];

describe("click to act", () => {
  it("clicking a single-action hotspot submits that action", () => {
    const onAct = vi.fn();
    mount([pick, move, clear], { hoverAction: null, canAct: true, onAct });
    fireEvent.click(screen.getByRole("button", { name: "Board: Pick cutting area 3" }));
    fireEvent.click(screen.getByRole("button", { name: "Board: Move to Bearers (location 3)" }));
    fireEvent.click(screen.getByRole("button", { name: "Board: Move to the forest clearing" }));
    expect(onAct.mock.calls.map((c) => c[0])).toEqual([4, 10, 30]);
  });

  it("renders no hotspots unless canAct", () => {
    const onAct = vi.fn();
    mount([pick, move], { hoverAction: null, canAct: false, onAct });
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    mount([pick]);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("several actions in one region open a menu", () => {
    const onAct = vi.fn();
    mount(wood, { hoverAction: null, canAct: true, onAct });
    expect(screen.queryByRole("group", { name: "Board: Cutting area 2 actions" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Board: Cutting area 2: 2 actions" }));
    expect(onAct).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Board: Take softwood from cutting area 2" }));
    expect(onAct).toHaveBeenCalledWith(181);
    expect(screen.queryByRole("group", { name: "Board: Cutting area 2 actions" })).toBeNull();
  });

  it("highlights the hotspot whose action is hovered in the list", () => {
    mount([pick, move], { hoverAction: 10, canAct: true, onAct: vi.fn() });
    expect(screen.getByTestId("hot-location-3")).toHaveClass("lgb-hot-lit");
    expect(screen.getByTestId("hot-area-3")).not.toHaveClass("lgb-hot-lit");
  });

  it("highlights the hovered action inside an open menu", () => {
    mount(wood, { hoverAction: 181, canAct: true, onAct: vi.fn() });
    fireEvent.click(screen.getByRole("button", { name: "Board: Cutting area 2: 2 actions" }));
    expect(screen.getByTestId("hot-area-2")).toHaveClass("lgb-hot-lit");
    expect(screen.getByRole("button", { name: "Board: Take softwood from cutting area 2" })).toHaveClass("lgb-hot-lit");
  });
});
