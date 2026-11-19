import type { GameView } from "../../shell/useGame";
import type { CardProps } from "./cards/Card";
import CardStrip from "./cards/CardStrip";
import SeatTile from "./SeatTile";
import "./details.css";
import type { LignumSeatView, LignumTaskCard, LignumView } from "./types";

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const num = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) ? x : 0);
const str = (x: unknown): string => (typeof x === "string" ? x : "");

function taskDetail(c: LignumTaskCard | null | undefined): string | undefined {
  if (!c) return undefined;
  const reqs = arr(c.requirements)
    .map((r) => str((r as { text?: unknown } | null)?.text))
    .filter(Boolean)
    .join(", ");
  return `$${num(c.reward)}${reqs ? ` for ${reqs}` : ""}`;
}

export function taskCards(v: LignumView, indices: unknown[], names: unknown[]): CardProps[] {
  const cards = arr(v.tasks?.cards) as (LignumTaskCard | null)[];
  return indices.map((k, i) => {
    const c = cards.find((x) => x?.index === k);
    const reqs = arr(c?.requirements);
    const done = reqs.length > 0 && reqs.every((r) => (r as { filled?: boolean } | null)?.filled);
    return { kind: "task", id: str(c?.id) || str(names[i]) || `task ${String(k)}`, detail: taskDetail(c), done };
  });
}

function SeatCards({ s, v, label, seat }: { s: LignumSeatView; v: LignumView; label: string; seat: number }) {
  const craftNames = arr(v.craft_order).map(str);
  const craft: CardProps[] = arr(s.held_craft).flatMap((n, i) =>
    Array.from({ length: Math.min(num(n), 12) }, () => ({ kind: "craftwork" as const, id: craftNames[i] ?? `craft ${i}` })),
  );
  const loans = num(s.loans);
  const repay = (k: number): string => {
    const r = arr(v.loan_repayment)[k];
    return typeof r === "number" ? `, $${r} repayment` : "";
  };
  const loanCards: CardProps[] = [
    ...Array.from({ length: Math.floor(loans / 2) }, () => ({ kind: "loan" as const, id: "loan (flipped)", spriteId: "loan-back", detail: `2 loans${repay(2)}` })),
    ...(loans % 2 === 1 ? [{ kind: "loan" as const, id: "loan", spriteId: "loan", detail: `1 loan${repay(1)}` }] : []),
  ];
  const plans: CardProps[] = arr(s.plans).map((p) => ({
    kind: "pw" as const,
    id: str((p as { name?: unknown } | null)?.name),
    detail: `target round ${num((p as { target?: unknown } | null)?.target)}`,
  }));
  const held = taskCards(v, arr(s.held_tasks), arr(s.held_task_ids));
  const buildings: CardProps[] = arr(s.building_names).map((n) => ({ kind: "building" as const, id: str(n) }));
  return (
    <section aria-label={`${label} cards`} className="card lgc-sec">
      <header>
        <SeatTile seat={seat} label={label} />
        <div className="lgc-sec-text">
          <span className="eyebrow">Seat cards</span>
          <h4>{label}</h4>
        </div>
      </header>
      <div className="lgc-sec-body">
        {[held, plans, buildings, craft, loanCards].every((c) => c.length === 0) && <p className="lgc-empty">No cards held yet.</p>}
        <CardStrip title={`${label} held tasks`} cards={held} />
        <CardStrip title={`${label} planned work`} cards={plans} />
        <CardStrip title={`${label} buildings`} cards={buildings} />
        <CardStrip title={`${label} craftwork`} cards={craft} />
        <CardStrip title={`${label} loans`} cards={loanCards} />
      </div>
    </section>
  );
}

/** Card lists from the public view: board rows, this year's winter cards and each seat's cards. */
export default function CardsPanel({ game }: { game: GameView }) {
  const v = (game.view ?? {}) as LignumView;
  const seats = arr(v.seats) as (LignumSeatView | null)[];
  const year = num(v.round) > 4 ? 2 : 1;
  const winter: CardProps[] = arr(v.winter?.cards)
    .map((w, i) => ({ c: w as { year?: number; food?: number; heating?: number }, i }))
    .filter(({ c }) => c.year === year)
    .map(({ c, i }) => {
      return { kind: "winter" as const, id: str(arr(v.winter?.card_ids)[i]) || `winter ${year}`, detail: `food ${num(c.food)}, heating ${num(c.heating)}` };
    });
  const pw: CardProps[] = arr(v.pw?.cards).map((c) => ({ kind: "pw" as const, id: str((c as { name?: unknown } | null)?.name) }));
  const discarded: CardProps[] = arr(v.placement?.discarded_ids).map((n) => ({ kind: "placement" as const, id: str(n) }));
  return (
    <section aria-label="Cards" className="lgc-panel">
      <section aria-label="Board cards" className="card lgc-sec">
        <header>
          <div className="lgc-sec-text">
            <span className="eyebrow">Shared</span>
            <h3>Board cards</h3>
          </div>
        </header>
        <div className="lgc-sec-body">
          <CardStrip title="Task row" cards={taskCards(v, arr(v.tasks?.row), [])} />
          <CardStrip title="Tasks with pieces placed" cards={arr(v.tasks?.filled_ids).map((n) => ({ kind: "task" as const, id: str(n) }))} />
          <CardStrip title={`Winter cards, year ${year}`} cards={winter} />
          <CardStrip title="Planned-work row" cards={pw} />
          <CardStrip title="Building supply" cards={arr(v.buildings?.names).map((n) => ({ kind: "building" as const, id: str(n) }))} />
          <CardStrip title="Placement cards discarded" cards={discarded} />
        </div>
      </section>
      {seats.map((s, i) => (s ? <SeatCards key={i} s={s} v={v} seat={i} label={str(s.label) || `P${i}`} /> : null))}
    </section>
  );
}
