import { useEffect, useRef, useState } from "react";
import type { LignumView } from "../types";

export interface Changed {
  areas: number[];
  locs: number[];
  clearing: number[];
}
const NONE: Changed = { areas: [], locs: [], clearing: [] };
const j = (x: unknown): string => JSON.stringify(x ?? null);

/** Board spots whose public contents differ between two views: cutting areas (1-based), path locations, clearing slots. */
export function diffBoard(a: LignumView, b: LignumView): Changed {
  const n = Math.max(arr(a.area_wood).length, arr(b.area_wood).length);
  const areas = Array.from({ length: n }, (_, i) => i).filter(
    (i) => j(arr(a.area_wood)[i]) !== j(arr(b.area_wood)[i]) || j(arr(a.area_food)[i]) !== j(arr(b.area_food)[i]) || j(arr(a.picks).map((p) => arr(p).includes(i))) !== j(arr(b.picks).map((p) => arr(p).includes(i))),
  );
  const la = a.path?.locations ?? [];
  const lb = b.path?.locations ?? [];
  const locs = lb.flatMap((l) => {
    const o = la.find((x) => x.number === l.number);
    return !o || j([o.foremen, o.pool, o.token]) !== j([l.foremen, l.pool, l.token]) ? [l.number] : [];
  });
  const sa = a.path?.clearing_slots ?? [];
  const sb = b.path?.clearing_slots ?? [];
  const clearing = sb.flatMap((s, i) => (j(s) !== j(sa[i]) ? [i] : []));
  return { areas: areas.map((i) => i + 1), locs, clearing };
}
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);

/** Spots changed by the latest state change, for `ms` after it happens (empty on first render and on identical polls). */
export function useLastChange(v: LignumView, ms = 3500): Changed {
  const prev = useRef<LignumView | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [hl, setHl] = useState<Changed>(NONE);
  useEffect(() => {
    const p = prev.current;
    prev.current = v;
    if (!p) return;
    const d = diffBoard(p, v);
    if (!d.areas.length && !d.locs.length && !d.clearing.length) return;
    setHl(d);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setHl(NONE), ms);
  }, [v, ms]);
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);
  return hl;
}
