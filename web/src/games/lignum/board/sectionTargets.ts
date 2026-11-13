import type { LegalAction } from "../../../shell/useGame";
import { targetsFor, type ClickTarget, type TargetAction } from "./clickTargets";

/** Sawmill-pad region keys by zone index (adapter _ZONES) and by MOVE_WOOD destination (_DESTS). */
const ZONE = ["sale", "dry1", "dry2", "dry3", "sawing", "store"];
const DEST = ["sawing", "sale"];
const at = (list: string[], i: number | undefined): string | undefined => (i === undefined ? undefined : list[i]);

/** Action families anchored to a sawmill-pad section (region key of sawmillLayout.json). */
const SAWMILL_SECTION: Record<string, (p: number[]) => string | undefined> = {
  SELL: (p) => at(ZONE, p[0]),
  HUT_DRY: (p) => at(ZONE, p[0]),
  DRY_ENTER: () => "dry1",
  MOVE_WOOD: (p) => at(DEST, p[1]),
  WC_MOVE: (p) => at(DEST, p[1]),
  SAW: () => "sawing",
  RIVER_MOVE: () => "river",
  RIVER_SALE: () => "river",
  STORE_PIECE: () => "store",
  SELL_EQUIP: () => "equip",
  BUY_SAW: () => "equip",
  SELL_SET: () => "craft",
  SELL_SET_JOKERS: () => "craft",
  SELL_FOOD: () => "food",
  BUY_FOOD: () => "food",
  BUY_FODDER: () => "fodder",
  HIRE_BEARER: () => "hired",
  HIRE_WOODCUTTER: () => "hired",
  HIRE_SAWYER: () => "hired",
  PLACE_JOINERY: () => "joinery",
  BUILD_HUT: () => "huts",
  HUT_TOKEN: () => "huts",
  ASSIGN_WORKER: (p) => (["hired", "mill", "huts"] as const)[p[0] ?? -1],
};

/** Legal actions grouped by the sawmill section they belong to (own pad only). */
export function sawmillSections(legal: readonly LegalAction[]): Record<string, TargetAction[]> {
  const out: Record<string, TargetAction[]> = {};
  for (const a of legal) {
    const key = a.kind && a.params ? SAWMILL_SECTION[a.kind]?.(a.params) : undefined;
    if (key) (out[key] ??= []).push({ id: a.id, label: a.label });
  }
  return out;
}

/** Buying and hiring happen at the location where the foreman stands. */
const HERE_KINDS: ReadonlySet<string> = new Set(["HIRE_BEARER", "HIRE_WOODCUTTER", "HIRE_SAWYER", "BUY_FODDER", "BUY_SAW", "BUY_FOOD"]);

/** Board click targets plus the hire/buy actions anchored at the acting foreman's location. */
export function boardTargets(legal: readonly LegalAction[], here: number | undefined): ClickTarget[] {
  const targets = targetsFor(legal);
  const acts = legal.filter((a) => a.kind && HERE_KINDS.has(a.kind)).map((a) => ({ id: a.id, label: a.label }));
  if (!acts.length || here === undefined || here < 1 || here > 22) return targets;
  const key = `location-${here}`;
  const t = targets.find((x) => x.key === key);
  if (t) t.actions.push(...acts);
  else targets.push({ key, region: { type: "location", n: here }, label: `Location ${here}`, actions: acts });
  return targets;
}

/** The sorted HUT_AREA sequence for per-area token counts (non-decreasing area ids, as the engine requires). */
export function areaSequence(counts: readonly number[]): number[] {
  return counts.flatMap((n, h) => Array.from({ length: n }, () => h));
}
