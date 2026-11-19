import { useEffect, useState } from "react";
import type { GameView } from "../../shell/useGame";
import type { BoardUi } from "../registry";
import Board from "./board/Board";
import Sawmill from "./board/Sawmill";
import { CardViewerProvider } from "./cards/CardViewer";
import { roundSummary } from "./board/Trackers";
import WorkerRoster from "./WorkerRoster";
import type { LignumView } from "./types";
import CardsPanel from "./CardsPanel";
import "./details.css";
import HutPicker from "./HutPicker";
import ScoringPanel from "./ScoringPanel";
import TaskCardsPanel from "./TaskCardsPanel";
import TextBoard from "./TextBoard";
import { ThemeProvider, useTheme } from "./theme/ThemeProvider";
import type { LoadedManifests } from "./theme/types";

type View = "board" | "sawmill" | "cards" | "tasks" | "details";
const VIEWS: { id: View; label: string }[] = [
  { id: "board", label: "Board" },
  { id: "sawmill", label: "Sawmills" },
  { id: "cards", label: "Cards" },
  { id: "tasks", label: "Task Cards" },
  { id: "details", label: "Details" },
];

function Panel({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const [text, setText] = useState(false);
  const [view, setView] = useState<View>("board");
  const { themeId, setThemeId, available } = useTheme();
  const terminal = (game.view as { is_terminal?: boolean } | undefined)?.is_terminal === true;
  useEffect(() => {
    if (terminal) setView("details");
  }, [terminal]);
  const lv = (game.view ?? {}) as LignumView;
  const summary = roundSummary(lv);
  const last = [...(game.history ?? [])].reverse().find((h) => h.actor !== null);
  const on = (v: View) => ({ "data-on": text ? v === "details" : view === v });
  return (
    <div className="lgp">
      <div className="lgb-bar">
        {!text && (
          <div className="lgp-views seg" role="group" aria-label="Board views">
            {VIEWS.map((x) => (
              <button key={x.id} type="button" aria-pressed={view === x.id} onClick={() => setView(x.id)}>
                {x.label}
              </button>
            ))}
          </div>
        )}
        {summary && (
          <span className="chip lgb-round-line" data-testid="round-summary">
            {summary}
          </span>
        )}
        {last && (
          <span className="chip lgb-last-line" data-testid="last-action" aria-label="Last action">
            Last: P{last.actor}: {last.label}
          </span>
        )}
        <details className="lgb-viewopts">
          <summary className="btn btn-sm">View</summary>
          <div className="lgb-viewopts-pop card">
            <label>
              <input type="checkbox" checked={text} onChange={(e) => setText(e.target.checked)} /> Text view only
            </label>
            {available.length > 1 && (
              <label>
                Theme{" "}
                <select value={themeId} onChange={(e) => setThemeId(e.target.value as typeof themeId)}>
                  {available.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </details>
      </div>
      <HutPicker game={game} ui={ui} />
      <div className="lgp-stage">
        <div className="lgp-pane lgp-board" {...on("board")}>
          {!text && <Board game={game} ui={ui} />}
        </div>
        <div className="lgp-pane lgp-sawmill" {...on("sawmill")}>
          {!text && <Sawmill game={game} ui={ui} />}
        </div>
        <div className="lgp-pane" {...on("cards")}>
          {!text && <CardsPanel game={game} />}
        </div>
        <div className="lgp-pane" {...on("tasks")}>
          {!text && <TaskCardsPanel game={game} />}
        </div>
        <div className="lgp-pane lgp-details" {...on("details")}>
          <div className="lgd-grid">
            <ScoringPanel game={game} />
            <WorkerRoster v={lv} />
            <TextBoard game={game} ui={ui} />
          </div>
        </div>
      </div>
    </div>
  );
}

/** Sprite board (default) with a text-view fallback; the theme is mounted here, at the plugin level. */
export default function BoardPanel({ game, ui, manifests }: { game: GameView; ui?: BoardUi; manifests?: LoadedManifests }) {
  return (
    <ThemeProvider manifests={manifests}>
      <CardViewerProvider>
        <Panel game={game} ui={ui} />
      </CardViewerProvider>
    </ThemeProvider>
  );
}
