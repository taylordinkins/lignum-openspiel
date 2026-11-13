import { useEffect, useState } from "react";
import "./layout.css";
import { api } from "../api/client";
import Curtain from "./Curtain";
import ActionLog from "./ActionLog";
import ImportButton from "./ImportButton";
import { getPlugin, type BoardUi } from "../games/registry";
import ReportDialog from "./ReportDialog";
import TabBar, { type ScreenTab } from "./TabBar";
import YourMove from "./YourMove";
import { thinkingText } from "./seatTypes";
import { deriveViewSeat, SeatViewContext } from "./viewSeat";
import {
  errorText,
  currentPlayer,
  DEFAULT_POLL,
  isTerminal,
  legalActions,
  useGame,
  type GameView,
  type PollIntervals,
} from "./useGame";

interface Props {
  gameId: string;
  pollMs?: PollIntervals;
  onExit?: () => void;
  /** Called with the new game id after a replay import. */
  onImported?: (gameId: string) => void;
  /**
   * Hotseat hand-off hook (unit 8's curtain). `onSeatChange` fires whenever the viewed seat
   * changes; while `revealed` is false the board and action list are hidden. Defaults to true.
   */
  onSeatChange?: (seat: number) => void;
  revealed?: boolean;
}

async function downloadExport(gameId: string): Promise<void> {
  const { data, error } = await api.GET("/api/games/{game_id}/export", {
    params: { path: { game_id: gameId } },
  });
  if (!data) throw new Error(errorText(error));
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `lignum-${gameId}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const isTerminalGame = (g: GameView | null): boolean => g !== null && isTerminal(g);

const dollars = (n: number): string => (n < 0 ? `-$${-n}` : `$${n}`);

function GameOver({ game }: { game: GameView }) {
  const winners = game.winners ?? [];
  const final = game.view.final;
  return (
    <div aria-label="Game over">
      <h2>Game over</h2>
      {winners.length === 1 && <p>P{winners[0]} wins</p>}
      {winners.length > 1 && <p>Tie: {winners.map((p) => `P${p}`).join(", ")} win</p>}
      {game.returns && (
        <p>Returns: {game.returns.map((r, i) => `P${i} ${r}`).join(", ")}</p>
      )}
      {Array.isArray(final) && (
        <p>
          Final dollars:{" "}
          {(final as number[]).map((d, i) => `P${i} ${dollars(d)}`).join(", ")}
        </p>
      )}
    </div>
  );
}

export default function GameScreen({
  gameId,
  pollMs = DEFAULT_POLL,
  onExit,
  onImported,
  onSeatChange,
  revealed = true,
}: Props) {
  const [gameName, setGameName] = useState("");
  // Seat whose view is requested (null = server default, i.e. the seat to move).
  const [viewSeat, setViewSeat] = useState<number | null>(null);
  const { game: raw, error, busy, act, actBatch, goBack, rewind, retry, botThinking, autoNote } = useGame(
    gameId,
    pollMs,
    { autoAdvance: getPlugin(gameName).autoAdvance, seat: viewSeat },
  );
  // Data rendered for another seat than the viewed one is treated as loading (no private leak).
  const game = raw !== null && viewSeat !== null && raw.seat !== viewSeat ? null : raw;
  const mismatch = raw !== null && game === null;
  if (raw && raw.game !== gameName) setGameName(raw.game);
  const derivedSeat = raw ? deriveViewSeat(raw, viewSeat) : null;
  if (derivedSeat !== null && derivedSeat !== viewSeat) setViewSeat(derivedSeat);
  // Hotseat curtain: covered whenever the viewed human seat differs from the last acknowledged one.
  const [ackSeat, setAckSeat] = useState<number | null>(null);
  if (viewSeat !== null && ackSeat === null) setAckSeat(viewSeat);
  const hotseat = raw !== null && raw.seats.filter((s) => s === "human").length > 1;
  const covered =
    hotseat && !isTerminalGame(raw) && viewSeat !== null && ackSeat !== null && viewSeat !== ackSeat;
  const showBoard = revealed && !covered;
  useEffect(() => {
    if (viewSeat !== null) onSeatChange?.(viewSeat);
  }, [viewSeat, onSeatChange]);

  const [tab, setTab] = useState<ScreenTab>("play");
  const [hoverAction, setHoverAction] = useState<number | null>(null);
  const [reporting, setReporting] = useState(false);
  const [rewindTo, setRewindTo] = useState("0");
  const [exportError, setExportError] = useState<string | null>(null);
  const rewindValid = /^\d+$/.test(rewindTo.trim());
  const plugin = getPlugin(game?.game ?? "");
  const over = game !== null && isTerminal(game);
  const cp = game ? currentPlayer(game) : null;
  const humanTurn = game !== null && cp !== null && game.seats[cp] === "human" && !game.bot_thinking;

  const phase = game ? plugin.phaseLabel?.(game) : undefined;
  const ui: BoardUi | undefined = game
    ? {
        hoverAction,
        canAct: !over && humanTurn && !busy && showBoard,
        onAct: (id) => act(id),
        onActBatch: (ids) => actBatch(ids),
        viewSeat,
      }
    : undefined;

  return (
    <SeatViewContext.Provider value={{ viewSeat, revealed: showBoard }}>
      <section className="lg-screen" data-tab={tab}>
        <div className="lg-topbar">
          {onExit && (
            <button type="button" onClick={onExit}>
              Lobby
            </button>
          )}
          {game && (
            <p className="lg-status-line">
              Game {game.id} · seats: {game.seats.map((s, i) => `P${i} ${s}`).join(", ")}
            </p>
          )}
          {game && (
            <div role="toolbar" aria-label="Game tools">
              <button
                type="button"
                disabled={busy || game.history_length === 0}
                onClick={() => void goBack()}
              >
                Back
              </button>
              {game.dev_mode && (
                <span>
                  <label>
                    Rewind to player action{" "}
                    <input
                      value={rewindTo}
                      onChange={(e) => setRewindTo(e.target.value)}
                      inputMode="numeric"
                      size={4}
                    />
                  </label>{" "}
                  <button
                    type="button"
                    disabled={busy || !rewindValid}
                    onClick={() => void rewind(Number(rewindTo.trim()))}
                  >
                    Rewind
                  </button>
                </span>
              )}
              <button
                type="button"
                onClick={() => {
                  setExportError(null);
                  downloadExport(gameId).catch((e: unknown) =>
                    setExportError(e instanceof Error ? e.message : "Export failed"),
                  );
                }}
              >
                Export replay
              </button>
              {onImported && <ImportButton onImported={onImported} />}
              <button type="button" onClick={() => setReporting(true)}>
                Report a problem
              </button>
            </div>
          )}
        </div>
        {exportError && <p role="alert">Export error: {exportError}</p>}
        {error && <p role="alert">Error: {error}</p>}
        {!game && !error && !covered && <p>Loading…</p>}
        {raw && covered && viewSeat !== null && (
          <Curtain seat={viewSeat} disabled={mismatch} onReveal={() => setAckSeat(viewSeat)} />
        )}
        {game && ui && !covered && (
          <>
            {reporting && <ReportDialog gameId={gameId} onClose={() => setReporting(false)} />}
            <TabBar value={tab} onChange={setTab} />
            <div className="lg-grid">
              <div className="lg-pane-board">
                {showBoard ? plugin.renderBoard(game, ui) : <p>Board hidden.</p>}
              </div>
              <div className="lg-side">
                <div className="lg-pane-play">
                  {botThinking && cp !== null && (
                    <p role="status">{thinkingText(game.seats[cp] ?? "", cp)}</p>
                  )}
                  {game.bot_error && !over && (
                    <div role="alert">
                      Bot error: {game.bot_error}{" "}
                      <button
                        type="button"
                        onClick={() => void retry()}
                      >
                        Retry
                      </button>
                    </div>
                  )}
                  {autoNote && !over && <p role="status">{autoNote} (only legal action)</p>}
                  {over ? (
                    <GameOver game={game} />
                  ) : (
                    cp !== null && (
                      <>
                        <YourMove
                          humanTurn={humanTurn && showBoard}
                          waitingFor={
                            humanTurn ? null : `P${cp} (${game.seats[cp]})`
                          }
                          phase={phase}
                          actions={legalActions(game)}
                          busy={busy}
                          onAct={(id) => void act(id)}
                          labelFor={(a) => plugin.actionLabel?.(game, a) ?? a.label}
                          onHover={setHoverAction}
                          describe={(a) => plugin.actionHelp?.(game, a)}
                        />
                        <p>
                          Current player: P{cp} ({game.seats[cp]})
                        </p>
                      </>
                    )
                  )}
                </div>
                <div className="lg-log lg-pane-log">
                  <h3>Action log</h3>
                  <ActionLog history={game.history} actorStyle={plugin.seatStyle} />
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </SeatViewContext.Provider>
  );
}
