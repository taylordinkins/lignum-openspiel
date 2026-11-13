import { useTheme } from "./theme/ThemeProvider";
import { seatColor } from "./board/seatColors";
import type { LignumSeatView, LignumView } from "./types";

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const num = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) ? x : 0);
const plural = (n: number, w: string): string => `${n} ${w}${n === 1 ? "" : "s"}`;

export interface RosterRow {
  /** Stable key, also the sprite lookup. */
  key: string;
  sprite: string;
  type: string;
  colour: string;
  count: number;
  where: string;
}

/**
 * Every worker a seat owns, by type and colour, with where it stands. Only public view fields are
 * used (R-028): hired counts, joiners, mill_used, cut_used and hut worker tokens. The view does not
 * say which section a hired worker is assigned to (workers are only placed while a phase resolves),
 * so between phases they all stand in the Worker Area.
 */
export function rosterRows(s: LignumSeatView, seat: number): RosterRow[] {
  const hired = s.hired ?? {};
  const b = num(hired.b);
  const w = num(hired.w);
  const sw = num(hired.s);
  const used = Math.min(num(s.cut_used), w);
  const joiners = num(s.joiners);
  const rows: RosterRow[] = [
    {
      key: "mill",
      sprite: `mill-worker-${seat}`,
      type: "Mill worker",
      colour: `seat colour (P${seat})`,
      count: 1,
      where: s.mill_used ? "away from the Worker Area (used this round)" : "Worker Area",
    },
  ];
  if (b > 0) rows.push({ key: "b", sprite: "worker-bearer", type: "Hired bearer", colour: "green", count: b, where: "Worker Area (hired)" });
  if (w > 0)
    rows.push({
      key: "w",
      sprite: "worker-woodcutter",
      type: "Hired woodcutter",
      colour: "brown",
      count: w,
      where: used > 0 ? `Worker Area (hired); ${used} used this round` : "Worker Area (hired)",
    });
  if (sw > 0) rows.push({ key: "s", sprite: "worker-sawyer", type: "Hired sawyer", colour: "white", count: sw, where: "Worker Area (hired)" });
  if (joiners > 0) rows.push({ key: "j", sprite: "worker-joiner", type: "Joiner", colour: "yellow", count: joiners, where: "Joinery board" });
  const hut = num(s.huts?.worker);
  if (hut > 0) rows.push({ key: "hut", sprite: "icon-hut", type: "Hut worker token", colour: "hut", count: hut, where: "Worker hut (spent on use)" });
  return rows;
}

/** Per-seat roster table: shared by both themes; sprites when the theme has them, else colour chips. */
export default function WorkerRoster({ v }: { v: LignumView }) {
  const { sprite } = useTheme();
  const seats = arr(v.seats) as (LignumSeatView | null)[];
  return (
    <section aria-label="Worker roster" className="lgw">
      <h3>Worker roster</h3>
      {seats.map((s, i) =>
        s ? (
          <div key={i} role="group" aria-label={`${s.label || `P${i}`} workers`} className="lgw-seat">
            <h4>
              <span className="lgw-dot" style={{ background: seatColor(i) }} aria-hidden="true" /> {s.label || `P${i}`}
              {i === v.seat ? " (you)" : ""}
            </h4>
            <table>
              <thead>
                <tr><th>Worker</th><th>Colour</th><th>Count</th><th>Location</th></tr>
              </thead>
              <tbody>
                {rosterRows(s, i).map((r) => {
                  const sp = sprite(r.sprite);
                  return (
                    <tr key={r.key} data-testid="roster-row" aria-label={`${s.label || `P${i}`} ${plural(r.count, r.type.toLowerCase())}, ${r.colour}: ${r.where}`}>
                      <td>{sp && <img src={sp.src} alt="" className="lgw-img" />} {r.type}</td>
                      <td>{r.colour}</td>
                      <td>{r.count}</td>
                      <td>{r.where}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null,
      )}
    </section>
  );
}
