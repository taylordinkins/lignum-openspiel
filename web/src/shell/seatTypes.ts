import type { SeatType } from "./useGame";

/** Seat-type choices offered in the lobby (values are validated server-side by pattern). */
export const SEAT_PRESETS: { value: SeatType; label: string }[] = [
  { value: "human", label: "Human" },
  { value: "random", label: "Random bot" },
  { value: "heuristic", label: "Heuristic bot" },
  { value: "strategist", label: "Strategist bot" },
  { value: "az", label: "AZ bot" },
  { value: "azpp", label: "AZPP bot" },
  { value: "mcts-fast", label: "MCTS (fast)" },
  { value: "mcts", label: "MCTS" },
];

/** Display name for a seat type, e.g. "Heuristic", "MCTS Medium", "MCTS (50 sims)". */
export function seatTypeName(t: string): string {
  const preset = SEAT_PRESETS.find((p) => p.value === t);
  if (preset) return preset.label.replace(/ bot$/, "").replace(/ \(\d+ sims\)$/, "");
  if (t === "mcts-fast") return "MCTS (fast)";
  const m = /^mcts(?::(\d+))?$/.exec(t);
  if (m) return m[1] ? `MCTS (${m[1]} sims)` : "MCTS";
  if (t.startsWith("trained:")) return `Trained (${t.slice(8)})`;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function thinkingText(seatType: string, seat: number): string {
  return `${seatTypeName(seatType)} (P${seat}) is thinking…`;
}

/** Seat kind as shown on panels and prompts: "Human", "Random bot", "MCTS (50 sims) bot". */
export function seatKindName(t: string): string {
  const preset = SEAT_PRESETS.find((p) => p.value === t);
  if (preset) return preset.label;
  return t === "human" ? "Human" : `${seatTypeName(t)} bot`;
}
