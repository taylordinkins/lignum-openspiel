import { describe, expect, it } from "vitest";
import { SEAT_PRESETS, seatTypeName, thinkingText } from "./seatTypes";

describe("seat presets", () => {
  it("offers human and random bot seats", () => {
    expect(SEAT_PRESETS.map((p) => p.value)).toEqual([
      "human",
      "random",
      "heuristic",
      "strategist",
      "az",
      "azpp",
      "mcts-fast",
      "mcts",
    ]);
  });
  it("names seat types", () => {
    expect(seatTypeName("random")).toBe("Random");
    expect(seatTypeName("human")).toBe("Human");
    expect(seatTypeName("mcts:50")).toBe("MCTS (50 sims)");
    expect(seatTypeName("mcts")).toBe("MCTS");
    expect(seatTypeName("strategist")).toBe("Strategist");
    expect(seatTypeName("az")).toBe("AZ");
    expect(seatTypeName("azpp")).toBe("AZPP");
  });
  it("builds the thinking text", () => {
    expect(thinkingText("random", 1)).toBe("Random (P1) is thinking…");
  });
});
