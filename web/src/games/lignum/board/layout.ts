import raw from "./layout.json";

/** Board layout in fractional (0..1) coordinates of the board image, so any theme size works. */
export interface Pt {
  x: number;
  y: number;
}
export interface Rect extends Pt {
  /** Centre x/y; w/h are the box size as fractions of the image. */
  w: number;
  h: number;
}
export interface AreaLayout extends Rect {
  /** 1-based cutting area number. */
  n: number;
  /** Where the area's cutting token / seat pawns sit. */
  token: Pt;
}
export interface LocationLayout extends Pt {
  /** Capacity boxes (bearers, tasks, ...) have a size. */
  w?: number;
  h?: number;
  /** Token spots have a separate circle for the token itself. */
  spot?: Pt;
}
export interface SideLayout {
  /** Pixel size of the official image (the aspect ratio of the board box). */
  width: number;
  height: number;
  areas: AreaLayout[];
  /** By printed location number. */
  locations: Record<number, LocationLayout>;
  /** Location 0 (foremen start). */
  start: Rect;
  /** Starting-player positions 1..4. */
  turn: Pt[];
  /** Forest clearing slots A..D. */
  clearing: Pt[];
  trackers: Trackers;
}
/** Printed phase track (top), season legend and round rows (right), and the card areas. */
export interface Trackers {
  /** Keys W1..W7, N1..N6 and "winter" (the winter label). */
  phase: Record<string, Rect>;
  legend: Record<"spring" | "summer" | "fall", Rect>;
  /** Round "1".."8". */
  season: Record<string, Rect>;
  cards: { tasks: Rect; pw: Rect; buildings: Rect; winter: Rect[] };
}
export type BoardSide = "base" | "joinery";

interface RawPt {
  x: number;
  y: number;
}
interface RawSide {
  width: number;
  height: number;
  areas: { n: number; x: number; y: number; w: number; h: number; token: RawPt }[];
  locations: Record<string, { x: number; y: number; w?: number; h?: number; spot?: RawPt }>;
  start: { x: number; y: number; w: number; h: number };
  turn: RawPt[];
  clearing: RawPt[];
  trackers: {
    phase: Record<string, RawRect>;
    legend: Record<string, RawRect>;
    season: Record<string, RawRect>;
    cards: { tasks: RawRect; pw: RawRect; buildings: RawRect; winter: RawRect[] };
  };
}
type RawRect = { x: number; y: number; w: number; h: number };

function normalise(r: RawSide): SideLayout {
  const px = (p: RawPt): Pt => ({ x: p.x / r.width, y: p.y / r.height });
  const rect = (p: { x: number; y: number; w: number; h: number }): Rect => ({ ...px(p), w: p.w / r.width, h: p.h / r.height });
  const locations: Record<number, LocationLayout> = {};
  for (const [k, l] of Object.entries(r.locations)) {
    locations[Number(k)] = {
      ...px(l),
      ...(l.w !== undefined && l.h !== undefined ? { w: l.w / r.width, h: l.h / r.height } : {}),
      ...(l.spot ? { spot: px(l.spot) } : {}),
    };
  }
  const rects = <K extends string>(m: Record<string, RawRect>) => Object.fromEntries(Object.entries(m).map(([k, v]) => [k, rect(v)])) as Record<K, Rect>;
  const t = r.trackers;
  return {
    width: r.width,
    height: r.height,
    areas: r.areas.map((a) => ({ n: a.n, ...rect(a), token: px(a.token) })),
    locations,
    start: rect(r.start),
    turn: r.turn.map(px),
    clearing: r.clearing.map(px),
    trackers: {
      phase: rects(t.phase),
      legend: rects(t.legend),
      season: rects(t.season),
      cards: { tasks: rect(t.cards.tasks), pw: rect(t.cards.pw), buildings: rect(t.cards.buildings), winter: t.cards.winter.map(rect) },
    },
  };
}

export const LAYOUTS: Record<BoardSide, SideLayout> = {
  base: normalise(raw.base as RawSide),
  joinery: normalise(raw.joinery as RawSide),
};

/** Location number the engine uses for the forest clearing (server/adapters/lignum.py). */
export const CLEARING_LOCATION = 23;

/** Anchor for an area's wood pieces: along the bottom edge of its box; kind 0..2 left to right. */
export function woodAnchor(a: AreaLayout, kind: number): Pt {
  return { x: a.x - a.w * 0.3 + kind * a.w * 0.3, y: a.y + a.h * 0.32 };
}
/** Anchor for an area's food count: top-right corner of its box. */
export function foodAnchor(a: AreaLayout): Pt {
  return { x: a.x + a.w * 0.32, y: a.y - a.h * 0.3 };
}
