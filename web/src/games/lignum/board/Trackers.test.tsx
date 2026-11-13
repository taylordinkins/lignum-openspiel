import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LAYOUTS } from "./layout";
import { Trackers, phaseTarget, seasonOf } from "./Trackers";

describe("tracker markers", () => {
  it("maps rounds to season and year", () => {
    expect(seasonOf(3)).toEqual({ season: "fall", year: 1 });
    expect(seasonOf(5)).toEqual({ season: "spring", year: 2 });
    expect(seasonOf(8)).toEqual({ season: "winter", year: 2 });
    expect(seasonOf(9)).toBeUndefined();
  });
  it("maps phases to track positions", () => {
    expect(phaseTarget("W4", 2)).toBe("W4");
    expect(phaseTarget("N3", 4)).toBe("N3");
    expect(phaseTarget("NB", 4)).toBe("winter");
    expect(phaseTarget("PK", 2)).toBe("summer");
    expect(phaseTarget("FS", 8)).toBeUndefined();
  });
  it("labels and positions the markers", () => {
    const L = LAYOUTS.joinery;
    render(<Trackers v={{ round: 3, phase: "W4", phase_label: "W4 · Sawing" }} L={L} />);
    const p = screen.getByLabelText("Phase: Sawing");
    expect(p.style.left).toBe(`${(L.trackers.phase.W4!.x * 100).toFixed(2)}%`);
    const r = screen.getByLabelText("Round 3: Fall, year 1");
    expect(r.style.top).toBe(`${(L.trackers.season["3"]!.y * 100).toFixed(2)}%`);
  });
  it("puts a year-2 round on the lower rows", () => {
    const L = LAYOUTS.base;
    render(<Trackers v={{ round: 6, phase: "TR", phase_label: "TR · Supply-path travel" }} L={L} />);
    expect(screen.getByLabelText("Round 6: Summer, year 2").style.top).toBe(`${(L.trackers.season["6"]!.y * 100).toFixed(2)}%`);
    expect(screen.getByTestId("phase-marker").getAttribute("data-at")).toBe("summer");
  });
});
