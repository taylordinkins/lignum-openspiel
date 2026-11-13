import type { LegalAction } from "../../../shell/useGame";

/** Board region a legal action is anchored to. */
export type TargetRegion =
  | { type: "area"; n: number } // cutting area, 1-based
  | { type: "location"; n: number } // supply-path location (1..22)
  | { type: "clearing" }; // forest clearing (location 23)

export interface TargetAction {
  id: number;
  label: string;
}

export interface ClickTarget {
  /** Stable key for the region (also used as the React key). */
  key: string;
  region: TargetRegion;
  /** Region label, e.g. "Cutting area 3". */
  label: string;
  /** Legal actions anchored here, in input order. */
  actions: TargetAction[];
}

/** Action families (LegalAction.kind) that get a board hotspot, with their region from params. */
const REGION_OF: Record<string, (p: number[]) => TargetRegion | undefined> = {
  PICK_AREA: (p) => area(p[0]),
  MOVE_CUT_TOKEN: (p) => area(p[0]),
  TAKE_WOOD: (p) => area(p[0]),
  HUT_FOOD: (p) => area(p[0]),
  MOVE_TO: (p) => (p[0] === 23 ? { type: "clearing" } : p[0] !== undefined && p[0] >= 1 ? { type: "location", n: p[0] } : undefined),
};
const area = (a: number | undefined): TargetRegion | undefined => (a !== undefined && a >= 0 && a <= 5 ? { type: "area", n: a + 1 } : undefined);

export const ON_BOARD_KINDS: ReadonlySet<string> = new Set(Object.keys(REGION_OF));

/**
 * Action families with no board location. They stay reachable only through the action list
 * (always available) or the panels of later units. Every kind in server/adapters/lignum.py's
 * _ACTION_FMT must be in exactly one of ON_BOARD_KINDS and LIST_ONLY (a test enforces this).
 */
export const LIST_ONLY: ReadonlySet<string> = new Set([
  "DONE", "TAKE_LOAN", "HIRE_BEARER", "HIRE_WOODCUTTER", "HIRE_SAWYER", "BUY_FODDER", "BUY_SAW",
  "BUY_FOOD", "SELL_FOOD", "TAKE_TASK", "CHOOSE_BUILDING", "PLAN_WORK", "SELL_SET", "SELL_SET_JOKERS",
  "SELL_EQUIP", "TAKE_OVERTIME", "BUILD_HUT", "HUT_TOKEN", "HUT_AREA", "HUT_DRY", "ASSIGN_WORKER",
  "MOVE_WOOD", "RIVER_MOVE", "WC_MOVE", "USE_WAGON", "USE_SLEDGE", "USE_PW_LOGDRIVING", "END_TRIP",
  "SAW", "WINTER_CUT", "TAKE_BONUS", "PLACE_TASK", "PLACE_JOINERY", "STORE_PIECE", "SELL", "DRY_ENTER",
  "RIVER_SALE",
]);

const regionKey = (r: TargetRegion): string => (r.type === "clearing" ? "clearing" : `${r.type}-${r.n}`);
const regionLabel = (r: TargetRegion): string =>
  r.type === "area" ? `Cutting area ${r.n}` : r.type === "location" ? `Location ${r.n}` : "Forest clearing";

/** Group the legal actions that have a board location by region. Order follows first appearance. */
export function targetsFor(legalActions: readonly LegalAction[]): ClickTarget[] {
  const out = new Map<string, ClickTarget>();
  for (const a of legalActions) {
    if (!a.kind || !a.params) continue;
    const region = REGION_OF[a.kind]?.(a.params);
    if (!region) continue;
    const key = regionKey(region);
    const t = out.get(key) ?? { key, region, label: regionLabel(region), actions: [] };
    t.actions.push({ id: a.id, label: a.label });
    out.set(key, t);
  }
  return [...out.values()];
}

/** Legal actions that no hotspot covers (they remain in the action list). */
export function unmapped(legalActions: readonly LegalAction[]): LegalAction[] {
  const mapped = new Set(targetsFor(legalActions).flatMap((t) => t.actions.map((x) => x.id)));
  return legalActions.filter((a) => !mapped.has(a.id));
}
