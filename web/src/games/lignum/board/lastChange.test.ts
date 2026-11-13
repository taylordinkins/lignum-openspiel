import { diffBoard } from "./lastChange";
import { roundSummary } from "./Trackers";

describe("last-action diff", () => {
  const base = { area_wood: [[1, 0, 0], [0, 0, 0]], area_food: [0, 0], path: { locations: [{ number: 3, kind: "x", name: "", capacity: 1, foremen: [] as number[] }], clearing_slots: [null, null] } };
  it("reports only the spots that changed (areas 1-based)", () => {
    const next = { ...base, area_wood: [[1, 0, 0], [0, 2, 0]], path: { locations: [{ ...base.path.locations[0]!, foremen: [0] }], clearing_slots: [1, null] } };
    expect(diffBoard(base, next)).toEqual({ areas: [2], locs: [3], clearing: [0] });
  });
  it("reports nothing for an identical view", () => {
    expect(diffBoard(base, structuredClone(base))).toEqual({ areas: [], locs: [], clearing: [] });
  });
});

describe("round summary", () => {
  it("names year, season, round and the planned work resolving now", () => {
    const v = { round: 6, seats: [{ plans: [{ card: 1, name: "Trade", pair: 1, target: 6 }, { card: 2, name: "Sawing", pair: 2, target: 7 }] }] };
    expect(roundSummary(v)).toBe("Year 2, Summer (round 6); planned work now: Trade");
  });
});
