import type { GameView } from "../../shell/useGame";
import SeatTile from "./SeatTile";
import "./details.css";
import type { LignumSeatScore, LignumSeatView, LignumView } from "./types";

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const dollars = (n: number | undefined): string => (typeof n !== "number" || !Number.isFinite(n) ? "-" : n < 0 ? `-$${-n}` : `$${n}`);
const seatLabel = (v: LignumView, i: number): string => {
  const s = arr(v.seats)[i] as LignumSeatView | null | undefined;
  return s?.label || `P${i}`;
};

/** Columns in the order of the final dollars sum (R-081..R-083). */
const COLS: [keyof LignumSeatScore, string][] = [
  ["money", "Money held"],
  ["wood_sale", "Sale and drying areas"],
  ["river_sale", "River"],
  ["joinery_sale", "Joinery"],
  ["office", "Office"],
  ["tasks", "Completed tasks"],
  ["loan_repay", "Loan repayment"],
  ["final", "Final dollars"],
];

/** Final sale per-seat breakdown, winners (ties shown as shared) and returns; terminal only. */
export default function ScoringPanel({ game }: { game: GameView }) {
  const v = (game.view ?? {}) as LignumView;
  if (!v.is_terminal) return null;
  const final = arr(v.final) as number[];
  const score = arr(v.score) as (LignumSeatScore | null)[];
  const winners = arr(v.winners) as number[];
  const returns = v.returns ?? null;
  const rp = arr(v.loan_repayment);
  const repayText = typeof rp[1] === "number" && typeof rp[2] === "number" ? ` ($${rp[1]} for one loan, $${rp[2]} for two)` : "";
  const n = Math.max(final.length, score.length, arr(v.seats).length);
  return (
    <section aria-label="Result" className="card lgs-score">
      <header className="lgd-head">
        <span className="eyebrow">Final sale</span>
        <h3>Result</h3>
      </header>
      {winners.length > 0 && (
        <p aria-label="Winners" className="lgs-win">
          {winners.length > 1 ? "Tie: " : "Winner: "}
          {winners.map((w, k) => (
            <span key={w}>
              <SeatTile seat={w} label={seatLabel(v, w)} />
              {k < winners.length - 1 && ", "}
            </span>
          ))}
          {winners.length > 1 ? " share the win" : ""}
        </p>
      )}
      <div className="lgd-scroll">
      <table aria-label="Final scores" className="tbl">
        <thead>
          <tr>
            <th scope="col">Seat</th>
            {COLS.map(([k, name]) => (
              <th key={k} scope="col" className="num">
                {name}
              </th>
            ))}
            {returns && <th scope="col" className="num">Return</th>}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: n }, (_, i) => {
            const sc = score[i];
            const f = final[i] ?? sc?.final;
            return (
              <tr key={i} className={winners.includes(i) ? "lgs-win" : undefined}>
                <th scope="row">
                  <SeatTile seat={i} label={seatLabel(v, i)} />
                </th>
                {COLS.map(([k]) => (
                  <td key={k} className={k === "final" ? "num fin" : "num"}>{k === "final" ? dollars(f) : dollars(sc?.[k] as number | undefined)}</td>
                ))}
                {returns && <td className="num">{typeof returns[i] === "number" ? returns[i]!.toFixed(3) : "-"}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
      <p>
        <small>
          Final dollars = money after the final sale minus loan repayment{repayText}. The most final dollars wins; equal
          amounts share the win.
        </small>
      </p>
    </section>
  );
}
