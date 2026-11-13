import { fireEvent, render, screen } from "@testing-library/react";
import { ThemeProvider } from "../theme/ThemeProvider";
import { indexManifest } from "../theme/resolve";
import type { LoadedManifests } from "../theme/types";
import { cardInfo } from "./cardInfo";
import CardStrip from "./CardStrip";
import { CardViewerProvider } from "./CardViewer";
import type { CardProps } from "./Card";

const m = { assets: [] };
const manifests: LoadedManifests = { official: indexManifest("official", m, {}), generic: indexManifest("generic", m, {}) };
const cards: CardProps[] = [
  { kind: "task", id: "task-01" },
  { kind: "task", id: "task-02" },
  { kind: "task", id: "task-03" },
];
const ui = (onAct = () => {}) => (
  <ThemeProvider manifests={manifests}>
    <CardViewerProvider>
      <button type="button" onClick={onAct}>act</button>
      <CardStrip title="Task row" cards={cards} />
    </CardViewerProvider>
  </ThemeProvider>
);

describe("card data", () => {
  it("reads task values from the exported component data", () => {
    const t = cardInfo("task", "task 01")!;
    expect(t.title).toBe("Task 01");
    expect(t.lines[0]).toBe("Reward: $12");
    expect(t.lines).toHaveLength(3);
    expect(cardInfo("pw", "Trade")?.lines.join("|")).toMatch(/Seasons: Spring, Summer, Fall/);
    expect(cardInfo("building", "small workshop")?.title).toBe("Building: Small Workshop");
    expect(cardInfo("winter", "winter-1-1")?.lines[0]).toBe("Top half: food 7, heating 6");
  });
});

describe("card viewer", () => {
  it("opens from the magnifier, steps with arrow keys, wraps and closes with Esc", () => {
    render(ui());
    fireEvent.click(screen.getByRole("button", { name: "Enlarge task task-02" }));
    const dlg = screen.getByRole("dialog");
    expect(dlg).toHaveAccessibleName("Card viewer: Task 02");
    expect(dlg).toHaveTextContent("Task row: 2 of 3");
    expect(dlg).toHaveTextContent(/Reward: \$16/);
    fireEvent.keyDown(dlg, { key: "ArrowRight" });
    expect(dlg).toHaveTextContent("3 of 3");
    fireEvent.keyDown(dlg, { key: "ArrowRight" });
    expect(dlg).toHaveTextContent("1 of 3");
    fireEvent.keyDown(dlg, { key: "ArrowLeft" });
    expect(dlg).toHaveTextContent("3 of 3");
    fireEvent.keyDown(dlg, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens with Shift-click and Browse, and a plain click on a card does nothing", () => {
    render(ui());
    const first = screen.getAllByTestId("lgc-card")[0]!;
    fireEvent.click(first);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(first, { shiftKey: true });
    expect(screen.getByRole("dialog")).toHaveTextContent("1 of 3");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Browse Task row" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("1 of 3");
  });
});
