import { useState } from "react";
import type { GameView } from "../../shell/useGame";
import type { BoardUi } from "../registry";
import type { LignumView } from "./types";
import "./details.css";

/** Action ids (docs/ACTIONS.md section 5): ASSIGN_WORKER(0) and TAKE_WOOD(a, k). */
const ASSIGN_HIRED = 174;
export const takeWoodId = (area: number, kind: number): number => 177 + 3 * area + kind;

const nums = (x: unknown): number[] =>
  Array.isArray(x) ? x.map((n) => (typeof n === "number" ? n : 0)) : [];

export interface CutPlan {
  area: number;
  /** Wood per kind in the seat's area. */
  wood: number[];
  /** Hired woodcutters not yet used this round. */
  cutters: number;
  kindNames: string[];
}

/** Plan for the panel, or null when it should not be offered. */
export function cutPlan(game: GameView): CutPlan | null {
  const v = game.view as LignumView;
  const seat = game.seat;
  if (v.phase !== "W1" || game.current_player !== seat) return null;
  if (!(game.legal_actions ?? []).some((a) => a.id === ASSIGN_HIRED)) return null;
  const pick = (v.picks as unknown[] | undefined)?.[seat];
  if (typeof pick !== "number" || pick < 0) return null;
  const sv = v.seats?.[seat];
  const cutters = (sv?.hired?.w ?? 0) - (sv?.cut_used ?? 0);
  const wood = nums((v.area_wood as unknown[] | undefined)?.[pick]);
  if (cutters < 1 || wood.reduce((a, b) => a + b, 0) < 1) return null;
  return { area: pick, wood, cutters, kindNames: v.kind_names ?? wood.map((_, k) => `kind ${k}`) };
}

/** Default counts: fill in kind order up to min(cutters, wood). */
export function defaultCounts(plan: CutPlan): number[] {
  let left = plan.cutters;
  return plan.wood.map((w) => {
    const n = Math.min(w, left);
    left -= n;
    return n;
  });
}

/** [ASSIGN_WORKER(0), TAKE_WOOD(area, k)] once per piece, in kind order. */
export function batchIds(area: number, counts: number[]): number[] {
  return counts.flatMap((n, k) =>
    Array.from({ length: n }, () => [ASSIGN_HIRED, takeWoodId(area, k)]).flat(),
  );
}

function Stepper({ plan, enabled, onAct }: { plan: CutPlan; enabled: boolean; onAct: (ids: number[]) => void }) {
  const [counts, setCounts] = useState(() => defaultCounts(plan));
  const total = counts.reduce((a, b) => a + b, 0);
  const cap = Math.min(plan.cutters, plan.wood.reduce((a, b) => a + b, 0));
  const unused = plan.cutters - total;
  const summary =
    counts
      .map((n, k) => (n ? `${n} ${plan.kindNames[k] ?? k}` : ""))
      .filter(Boolean)
      .join(", ") || "nothing";
  const set = (k: number, d: number) =>
    setCounts((c) => c.map((n, i) => (i === k ? n + d : n)));
  return (
    <section aria-label="Cut with all hired woodcutters" className="panel-framed lgd-card lgd-cut">
      <header>
        <span className="eyebrow">Your move</span>
        <h3>Cut with all hired woodcutters</h3>
      </header>
      <p className="lgd-cut-hint">
        {plan.cutters} hired woodcutter{plan.cutters === 1 ? "" : "s"} left, area {plan.area + 1}
      </p>
      <ul>
        {plan.wood.map((w, k) =>
          w > 0 ? (
            <li key={k}>
              <span className="lgd-kind">
                {plan.kindNames[k] ?? k} (of {w})
              </span>{" "}
              <button
                type="button"
                aria-label={`Fewer ${plan.kindNames[k] ?? k}`}
                disabled={!enabled || counts[k]! <= 0}
                onClick={() => set(k, -1)}
              >
                -
              </button>{" "}
              <span aria-label={`${plan.kindNames[k] ?? k} to take`}>{counts[k]}</span>{" "}
              <button
                type="button"
                aria-label={`More ${plan.kindNames[k] ?? k}`}
                disabled={!enabled || counts[k]! >= w || total >= cap}
                onClick={() => set(k, 1)}
              >
                +
              </button>
            </li>
          ) : null,
        )}
      </ul>
      <p role="status">
        Take {summary}
        {unused > 0 ? `; ${unused} woodcutter${unused === 1 ? "" : "s"} unused this season` : ""}
      </p>
      <button
        type="button"
        className="btn-primary"
        disabled={!enabled || total < 1}
        onClick={() => onAct(batchIds(plan.area, counts))}
      >
        Take {total} piece{total === 1 ? "" : "s"}
      </button>
    </section>
  );
}

export default function CutAllPanel({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const plan = cutPlan(game);
  if (!plan || !ui?.onActBatch) return null;
  const key = `${game.history_length}:${plan.area}:${plan.cutters}:${plan.wood.join(",")}`;
  return (
    <Stepper
      key={key}
      plan={plan}
      enabled={!!ui.canAct && (ui.viewSeat ?? game.seat) === game.seat}
      onAct={(ids) => void ui.onActBatch?.(ids)}
    />
  );
}
