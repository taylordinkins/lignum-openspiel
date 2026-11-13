import { render, screen, within } from "@testing-library/react";
import { ThemeProvider } from "./theme/ThemeProvider";
import { indexManifest } from "./theme/resolve";
import type { LoadedManifests } from "./theme/types";
import WorkerRoster, { rosterRows } from "./WorkerRoster";
import type { LignumView } from "./types";

const m = { assets: [] };
const manifests: LoadedManifests = { official: indexManifest("official", m, {}), generic: indexManifest("generic", m, {}) };
const view: LignumView = {
  seat: 1,
  seats: [
    { label: "P0", joiners: 0, hired: { b: 0, w: 0, s: 0 } },
    { label: "P1", joiners: 2, hired: { b: 1, w: 2, s: 1 }, cut_used: 1, mill_used: true, huts: { worker: 1 } },
  ],
};

describe("worker roster", () => {
  it("lists every worker type with colour, count and location", () => {
    const rows = rosterRows(view.seats![1]!, 1);
    expect(rows.map((r) => [r.type, r.colour, r.count])).toEqual([
      ["Mill worker", "seat colour (P1)", 1],
      ["Hired bearer", "green", 1],
      ["Hired woodcutter", "brown", 2],
      ["Hired sawyer", "white", 1],
      ["Joiner", "yellow", 2],
      ["Hut worker token", "hut", 1],
    ]);
    expect(rows[0]!.where).toBe("away from the Worker Area (used this round)");
    expect(rows[2]!.where).toBe("Worker Area (hired); 1 used this round");
    expect(rows[4]!.where).toBe("Joinery board");
  });

  it("keeps the mill worker apart from hired workers and labels seats from P0", () => {
    render(
      <ThemeProvider manifests={manifests}>
        <WorkerRoster v={view} />
      </ThemeProvider>,
    );
    const p0 = screen.getByRole("group", { name: "P0 workers" });
    expect(within(p0).getAllByTestId("roster-row")).toHaveLength(1);
    expect(within(p0).getByText("Mill worker")).toBeInTheDocument();
    expect(within(p0).getByText("Worker Area")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "P1 workers" })).toHaveTextContent("P1 (you)");
    expect(document.body.textContent).not.toMatch(/Player 1/);
  });
});
