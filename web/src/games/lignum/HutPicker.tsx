import { useState } from "react";
import type { GameView } from "../../shell/useGame";
import type { BoardUi } from "../registry";
import { areaSequence } from "./board/sectionTargets";
import type { LignumView } from "./types";
import "./details.css";

const AREAS = ["Drying", "Food", "Mill worker"];

/**
 * Hut token areas (R-100): click any area in any order; once every token is placed the choice is
 * sent as the sorted HUT_AREA sequence in one batch. Shown only while HUT_AREA is legal.
 */
export default function HutPicker({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const areas = (game.legal_actions ?? []).filter((a) => a.kind === "HUT_AREA" && a.params);
  const open = (game.view as LignumView | undefined)?.huts?.open;
  if (!ui?.canAct || !ui.onActBatch || areas.length === 0 || !open) return null;
  return <Picker key={game.history_length} ids={areas.map((a) => [a.params![0]!, a.id])} remaining={open.tokens.length - open.areas.length} ui={ui} />;
}

function Picker({ ids, remaining, ui }: { ids: number[][]; remaining: number; ui: BoardUi }) {
  const [counts, setCounts] = useState([0, 0, 0]);
  const placed = counts.reduce((a, b) => a + b, 0);
  const idOf = (h: number) => ids.find(([x]) => x === h)?.[1];
  const click = (h: number) => {
    const next = counts.map((c, i) => (i === h ? c + 1 : c));
    if (placed + 1 < remaining) return setCounts(next);
    setCounts(next);
    const base = ids[0]![1]! - ids[0]![0]!; // HUT_AREA(h) = base + h
    void ui.onActBatch?.(areaSequence(next).map((x) => base + x));
  };
  return (
    <div className="lgp-hut" role="group" aria-label="Board: hut token areas">
      <span className="lgp-hut-title">
        <strong>Place hut tokens</strong>
        <span>Hut tokens left to place: {remaining - placed}</span>
      </span>
      {AREAS.map((n, h) => (
        <button
          key={n}
          type="button"
          disabled={idOf(h) === undefined}
          className={ui.hoverAction !== null && ui.hoverAction === idOf(h) ? "lgb-hot-lit" : undefined}
          aria-label={`Board: hut area ${n.toLowerCase()}, ${counts[h]} tokens`}
          onClick={() => click(h)}
        >
          {n}: {counts[h]}
        </button>
      ))}
      <button type="button" disabled={placed === 0} onClick={() => setCounts([0, 0, 0])}>
        Reset
      </button>
    </div>
  );
}
