import type { GameView } from "../../shell/useGame";
import { taskCards } from "./CardsPanel";
import type { CardProps } from "./cards/Card";
import CardStrip from "./cards/CardStrip";
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
      <CardStrip title="Task row (available)" cards={row} />
      {seats.map((s, i) => {
        if (!s) return null;
        const label = str(s.label) || `P${i}`;
        const cards = taskCards(v, arr(s.held_tasks), arr(s.held_task_ids));
        return (
          <section key={i} aria-label={`${label} task cards`}>
            <h4>
              {label}
              {i === v.seat ? " (you)" : ""}
            </h4>
            <CardStrip title={`${label} held tasks`} cards={cards} showEmpty />
          </section>
        );
      })}
    </section>
  );
}
