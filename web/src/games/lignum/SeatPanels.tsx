import type { GameView } from "../../shell/useGame";
import { currentPlayer, isTerminal } from "../../shell/useGame";
import { seatKindName } from "../../shell/seatTypes";
import type { BoardUi } from "../registry";
import type { LignumSeatView, LignumView } from "./types";
import { dollars } from "./money";
import "./seatpanels.css";

const num = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) ? x : 0);
const count = (x: unknown): number => (Array.isArray(x) ? x.length : 0);

function kindLabel(type: string, hotseat: boolean): string {
  return type === "human" && !hotseat ? "You" : seatKindName(type);
}

/** One card per seat: money, loans and the other public counters (R-028: only what the view exposes). */
export default function SeatPanels({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const v = (game.view ?? {}) as LignumView;
  const seats: (LignumSeatView | null | undefined)[] = v.seats ?? [];
  if (seats.length === 0) return null;
  const over = isTerminal(game);
  const cp = over ? null : currentPlayer(game);
  const hotseat = game.seats.filter((s) => s === "human").length > 1;
  const first = Array.isArray(v.turn_order) && typeof v.turn_order[0] === "number" ? v.turn_order[0] : null;
  return (
    <section className="lgs" aria-label="Seat summary">
      <span className="sr-only" role="group" aria-label="Money">
        {seats.map((s, i) => (
          <span key={i} aria-label={`${s?.label ?? `P${i}`} money ${dollars(num(s?.money))}`}>
            {s?.label ?? `P${i}`} {dollars(num(s?.money))}
          </span>
        ))}
      </span>
      {seats.map((s, i) => {
        const acting = cp === i;
        const loans = num(s?.loans);
        const hired = s?.hired ?? {};
        const tags: string[] = [];
        if (acting) tags.push("TO ACT");
        if (hotseat && ui?.viewSeat === i) tags.push("YOU");
        if (first === i) tags.push("FIRST");
        const stats: { k: string; v: string; danger?: boolean; title?: string }[] = [
          { k: "Loans", v: String(loans), danger: loans > 0 },
          { k: "Food", v: String(num(s?.food)) },
          { k: "Joiners", v: String(num(s?.joiners)) },
          { k: "Hired", title: "Hired bearers/woodcutters/sawyers", v: `${num(hired.b)}/${num(hired.w)}/${num(hired.s)}` },
          { k: "Tasks", v: String(count(s?.held_tasks)) },
          { k: "Bldgs", v: String(count(s?.building_names)) },
        ];
        return (
          <article key={i} className="card lgs-seat" data-seat={i} data-acting={acting} aria-label={`Seat P${i}`}>
            <header className="lgs-head">
              <span className="seat-tile" data-seat={i}>
                P{i}
              </span>
              <span className="lgs-kind muted">{kindLabel(game.seats[i] ?? "", hotseat)}</span>
              {tags.map((t) => (
                <span key={t} className="lgs-tag" data-tag={t}>
                  {t}
                </span>
              ))}
              <strong className="lgs-cash" aria-hidden="true">
                {dollars(num(s?.money))}
              </strong>
            </header>
            <dl className="lgs-stats">
              {stats.map((x) => (
                <div key={x.k} data-danger={x.danger ? "true" : undefined} title={x.title}>
                  <dt>{x.k}</dt>
                  <dd>{x.v}</dd>
                </div>
              ))}
            </dl>
          </article>
        );
      })}
    </section>
  );
}
