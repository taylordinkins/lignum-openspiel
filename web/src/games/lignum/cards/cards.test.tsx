import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { ThemeProvider } from "../theme/ThemeProvider";
import { indexManifest } from "../theme/resolve";
import type { LoadedManifests, ThemeManifest } from "../theme/types";
import Card from "./Card";
import CardStrip from "./CardStrip";
import { cardSpriteId } from "./spriteIds";

const ids = ["task-05", "building-small_joinery", "pw-food-supply", "craftwork-board", "winter-1-2", "placement-03"];
const manifest = (): ThemeManifest => ({ assets: ids.map((id) => ({ id, category: "x", alt: id, file: `${id}.svg` })) });
const manifests: LoadedManifests = {
  official: indexManifest("official", manifest(), Object.fromEntries(manifest().assets.map((a) => [a.file, `/o/${a.file}`]))),
  generic: indexManifest("generic", manifest(), Object.fromEntries(manifest().assets.map((a) => [a.file, `/g/${a.file}`]))),
};
const wrap = (n: ReactNode) => render(<ThemeProvider manifests={manifests}>{n}</ThemeProvider>);

describe("cardSpriteId", () => {
  it("maps view names to sprite ids", () => {
    expect(cardSpriteId("task", "task 05")).toBe("task-05");
    expect(cardSpriteId("building", "Small Joinery")).toBe("building-small_joinery");
    expect(cardSpriteId("pw", "Food Supply")).toBe("pw-food-supply");
    expect(cardSpriteId("craftwork", "board")).toBe("craftwork-board");
    expect(cardSpriteId("placement", "placement 03")).toBe("placement-03");
  });
});

describe("Card", () => {
  it("shows the sprite when one resolves", () => {
    wrap(<Card kind="task" id="task 05" detail="$12" />);
    expect(screen.getByRole("img").getAttribute("src")).toContain("task-05.svg");
    expect(screen.queryByTestId("lgc-fallback")).toBeNull();
    expect(screen.getByLabelText(/task task 05/)).toBeTruthy();
  });
  it("falls back to text with id and details when no sprite resolves", () => {
    wrap(<Card kind="task" id="task 99" detail="$12 for hardwood" />);
    expect(screen.queryByRole("img")).toBeNull();
    const fb = screen.getByTestId("lgc-fallback");
    expect(fb.textContent).toContain("task 99");
    expect(fb.textContent).toContain("$12 for hardwood");
  });
});

describe("CardStrip", () => {
  it("lists cards under a titled group and hides when empty", () => {
    wrap(
      <CardStrip
        title="Task row"
        cards={[
          { kind: "task", id: "task 05" },
          { kind: "task", id: "task 98" },
        ]}
      />,
    );
    const g = screen.getByRole("group", { name: "Task row" });
    expect(g.querySelectorAll("[data-testid=lgc-card]")).toHaveLength(2);
  });
  it("renders nothing for an empty list unless showEmpty", () => {
    wrap(<CardStrip title="Empty" cards={[]} />);
    expect(screen.queryByRole("group")).toBeNull();
  });
});
