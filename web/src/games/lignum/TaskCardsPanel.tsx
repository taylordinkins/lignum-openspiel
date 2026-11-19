import type { GameView } from "../../shell/useGame";
import { taskCards } from "./CardsPanel";
import type { CardProps } from "./cards/Card";
import CardStrip from "./cards/CardStrip";
import SeatTile from "./SeatTile";
import "./details.css";
import type { LignumSeatView, LignumView } from "./types";

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const str = (x: unknown): string => (typeof x === "string" ? x : "");

/** Task cards held by every seat. Held tasks and the wood on them are public (R-028), so all seats are shown in full. */
export default function TaskCardsPanel({ game }: { game: GameView }) {
  const v = (game.view ?? {}) as LignumView;
  const seats = arr(v.seats) as (LignumSeatView | null)[];
  const row: CardProps[] = taskCards(v, arr(v.tasks?.row), []);
  return (
    <section aria-label="Task cards" className="lgc-panel">
      <section aria-label="Task row" className="card lgc-sec">
        <header>
          <div className="lgc-sec-text">
            <span className="eyebrow">Shared</span>
            <h3>Task row</h3>
          </div>
        </header>
        <div className="lgc-sec-body">
          <CardStrip title="Task row (available)" cards={row} />
          {row.length === 0 && <p className="lgc-empty">No tasks in the row.</p>}
        </div>
      </section>
      {seats.map((s, i) => {
        if (!s) return null;
        const label = str(s.label) || `P${i}`;
        const cards = taskCards(v, arr(s.held_tasks), arr(s.held_task_ids));
        return (
          <section key={i} aria-label={`${label} task cards`} className="card lgc-sec">
            <header>
              <SeatTile seat={i} label={label} />
              <div className="lgc-sec-text">
                <span className="eyebrow">{i === v.seat ? "You" : "Held tasks"}</span>
                <h4>
                  {label}
                  {i === v.seat ? " (you)" : ""}
                </h4>
              </div>
            </header>
            <div className="lgc-sec-body">
              <CardStrip title={`${label} held tasks`} cards={cards} showEmpty />
            </div>
          </section>
        );
      })}
    </section>
  );
}
