import { useEffect, useState, type ReactNode } from "react";
import "./layout.css";
import { api } from "../api/client";
import { usePlayback } from "./playback";
import { useSettings } from "./settings";
import Curtain from "./Curtain";
import ActionLog from "./ActionLog";
import ImportButton from "./ImportButton";
import PromptBar from "./PromptBar";
import { Wordmark } from "../theme/Wordmark";
import { IconArrowLeft, IconClose, IconDownload, IconFlag, IconSkip, IconSliders } from "../theme/icons";
import { getPlugin, type BoardUi } from "../games/registry";
import ReportDialog from "./ReportDialog";
import SettingsDialog from "./SettingsDialog";
import TabBar, { type ScreenTab } from "./TabBar";
import YourMove from "./YourMove";
import { seatKindName, thinkingText } from "./seatTypes";
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
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
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

function Crown() {
  return (
    <span className="lg-crown">
      <svg viewBox="0 0 20 20" width="14" height="14" fill="currentColor" aria-hidden="true">
        <path d="M2 6l4 4 4-6 4 6 4-4-2 10H4z" />
      </svg>
      Winner
    </span>
  );
}

function GameOver({ game, onExit, onExport }: { game: GameView; onExit?: () => void; onExport: () => void }) {
  const winners = game.winners ?? [];
  const final = Array.isArray(game.view.final) ? (game.view.final as number[]) : null;
  const returns = game.returns ?? null;
  const n = game.seats.length;
  const score = (p: number): number => final?.[p] ?? returns?.[p] ?? 0;
  const at = (arr: number[], i: number): number => arr[i] as number;
  const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => score(b) - score(a) || a - b);
  const rank: number[] = [];
  order.forEach((p, i) => {
    const prev = order[i - 1];
    rank.push(prev !== undefined && score(prev) === score(p) ? (rank[i - 1] as number) : i + 1);
  });
  return (
    <div aria-label="Game over" className="panel-framed lg-over">
      <p className="eyebrow">Game over</p>
      {winners.length === 1 && <h2>P{winners[0]} wins</h2>}
      {winners.length > 1 && <h2>Tie: {winners.map((p) => `P${p}`).join(", ")} win</h2>}
      <ol className="lg-over-list">
        {order.map((p, i) => (
          <li key={p} className="lg-over-row" data-winner={winners.includes(p)}>
            <span className="lg-over-rank">{rank[i]}</span>
            <span className="seat-tile" data-seat={p}>
              P{p}
            </span>
            <span>{winners.includes(p) && <Crown />}</span>
            <span className="lg-over-money" data-neg={final !== null && at(final, p) < 0} aria-hidden="true">
              {final ? dollars(at(final, p)) : (returns?.[p] ?? "")}
            </span>
          </li>
        ))}
      </ol>
      {returns && <p className="lg-over-ret">Returns: {returns.map((r, i) => `P${i} ${r}`).join(", ")}</p>}
      {final && (
        <p className="sr-only">Final dollars: {final.map((d, i) => `P${i} ${dollars(d)}`).join(", ")}</p>
      )}
      <p className="muted">Scoring breakdown in Details.</p>
      <div className="lg-over-actions">
        <button type="button" className="btn" onClick={onExport}>
          Download replay
        </button>
        {onExit && (
          <button type="button" className="btn btn-primary" onClick={onExit}>
            New game
          </button>
        )}
      </div>
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
  const [settings] = useSettings();
  // Forced-move auto-advance waits until playback has caught up (no input while behind).
  const [holdAuto, setHoldAuto] = useState(false);
  const {
    game: latest,
    error,
    busy,
    act,
    actBatch,
    goBack,
    rewind,
    retry,
    autoNote,
    fetchFrame,
  } = useGame(gameId, pollMs, {
    autoAdvance: holdAuto ? undefined : getPlugin(gameName).autoAdvance,
    seat: viewSeat,
  });
  // Bot moves are shown one at a time at the bot pace; `raw` is the shown view, which may lag.
  const pb = usePlayback(latest, { pace: settings.botPace, fetchFrame });
  const behind = pb.behind;
  const raw = pb.shown;
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

  useEffect(() => setHoldAuto(behind), [behind]);

  const [tab, setTab] = useState<ScreenTab>("play");
  const [hoverAction, setHoverAction] = useState<number | null>(null);
  const [reporting, setReporting] = useState(false);
  const [rewindTo, setRewindTo] = useState("0");
  const [exportError, setExportError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [dismissedErr, setDismissedErr] = useState<string | null>(null);
  const doExport = () => {
    setExportError(null);
    downloadExport(gameId).catch((e: unknown) =>
      setExportError(e instanceof Error ? e.message : "Export failed"),
    );
  };
  const rewindValid = /^\d+$/.test(rewindTo.trim());
  const plugin = getPlugin(game?.game ?? "");
  const over = game !== null && isTerminal(game);
  const cp = game ? currentPlayer(game) : null;
  const humanTurn = game !== null && cp !== null && game.seats[cp] === "human" && !game.bot_thinking && !behind;

  const botThinking = game !== null && !over && (game.bot_thinking || behind);
  const canSkip =
    game !== null && !over && (behind || latest?.bot_thinking === true) && game.seats.includes("human");
  // While behind, the bot named is the actor of the next entry still to be shown.
  const nextActor = behind && game && latest ? latest.history[game.history_length]?.actor : null;
  const playing = nextActor !== null && nextActor !== undefined ? nextActor : cp;
  const skipSlot = canSkip ? (
    <button type="button" className="btn btn-sm lg-skip" onClick={pb.skip} disabled={pb.skipping}>
      <IconSkip /> Skip to my turn
    </button>
  ) : undefined;

  const phase = game ? plugin.phaseLabel?.(game) : undefined;
  const seatName = (p: number): string => `P${p} (${seatKindName(game?.seats[p] ?? "")})`;
  const ui: BoardUi | undefined = game
    ? {
        hoverAction,
        canAct: !over && humanTurn && !busy && showBoard,
        onAct: (id) => act(id),
        onActBatch: (ids) => actBatch(ids),
        viewSeat,
      }
    : undefined;

  const tool = (label: string, icon: ReactNode, onClick: () => void) => (
    <span className="tip" data-tip={label}>
      <button type="button" className="btn btn-sm btn-icon btn-ghost" aria-label={label} onClick={onClick}>
        {icon}
      </button>
    </span>
  );
  let prompt = "";
  if (game) {
    if (over) prompt = "The game has ended";
    else if (behind && playing !== null) prompt = `${seatName(playing)} is playing…`;
    else if (cp === null) prompt = "Waiting…";
    else if (humanTurn && showBoard) prompt = "Your move: choose an action";
    else prompt = `Waiting for ${seatName(cp)}…`;
  }

  const toast = (text: string, dismiss: () => void) => (
    <p role="alert" className="toast" key={text}>
      <span>{text}</span>
      <button
        type="button"
        className="btn btn-sm btn-icon toast-x"
        aria-label="Dismiss error"
        onClick={dismiss}
      >
        <IconClose />
      </button>
    </p>
  );
  const toastList = [
    error && error !== dismissedErr ? toast(`Error: ${error}`, () => setDismissedErr(error)) : null,
    exportError ? toast(`Export error: ${exportError}`, () => setExportError(null)) : null,
  ];
  const inBoard = game !== null && ui !== undefined && !covered;
  const toasts = toastList.some(Boolean) && (
    <div className={inBoard ? "lg-toasts" : "lg-toasts lg-toasts-fixed"}>{toastList}</div>
  );

  return (
    <SeatViewContext.Provider value={{ viewSeat, revealed: showBoard }}>
      <section className="lg-screen" data-tab={tab}>
        {reporting && <ReportDialog gameId={gameId} onClose={() => setReporting(false)} />}
        {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} />}
        {!(game && ui && !covered) && toasts}
        {!game && !error && !covered && (
          <p className="lg-loading">
            <span className="spinner" aria-hidden="true" />
            Loading…
          </p>
        )}
        {raw && covered && viewSeat !== null && (
          <Curtain seat={viewSeat} disabled={mismatch} onReveal={() => setAckSeat(viewSeat)} />
        )}
        {game && ui && !covered && (
          <>
            <TabBar value={tab} onChange={setTab} />
            <div className="lg-grid">
              <div className="lg-prompt-wrap">
                <PromptBar
                  seat={over ? null : cp}
                  title={phase}
                  prompt={prompt}
                  waiting={botThinking && !over}
                  thinking={playing !== null ? thinkingText(game.seats[playing] ?? "", playing) : undefined}
                  onBack={() => void goBack()}
                  backDisabled={busy || game.history_length === 0}
                  skipSlot={skipSlot}
                />
              </div>
              <div className="lg-pane-board">
                {showBoard ? plugin.renderBoard(game, ui) : <p>Board hidden.</p>}
                {toasts}
              </div>
              <div className="lg-side">
                <div className="lg-side-head">
                  <div className="lg-side-title">
                    <Wordmark size="sm" />
                    {onExit && (
                      <button type="button" className="btn btn-sm btn-ghost" onClick={onExit}>
                        <IconArrowLeft /> Lobby
                      </button>
                    )}
                  </div>
                  <div role="toolbar" aria-label="Game tools" className="lg-toolbar">
                    {tool("Export replay", <IconDownload />, doExport)}
                    {onImported && <ImportButton onImported={onImported} variant="icon" />}
                    {tool("Report a problem", <IconFlag />, () => setReporting(true))}
                    {tool("Settings", <IconSliders />, () => setSettingsOpen(true))}
                  </div>
                  <p className="lg-status-line muted" title={statusLine(game)}>
                    {statusLine(game)}
                  </p>
                  {game.dev_mode && (
                    <details className="lg-dev">
                      <summary>Dev</summary>
                      <div className="lg-rewind">
                        <label>
                          Rewind to player action{" "}
                          <input
                            value={rewindTo}
                            onChange={(e) => setRewindTo(e.target.value)}
                            inputMode="numeric"
                            size={4}
                          />
                        </label>
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={busy || !rewindValid}
                          onClick={() => void rewind(Number(rewindTo.trim()))}
                        >
                          Rewind
                        </button>
                      </div>
                    </details>
                  )}
                </div>
                <div className="lg-pane-play">
                  {game.bot_error && !over && (
                    <div role="alert" className="alert">
                      Bot error: {game.bot_error}{" "}
                      <button type="button" className="btn btn-sm" onClick={() => void retry()}>
                        Retry
                      </button>
                    </div>
                  )}
                  {autoNote && !over && (
                    <p role="status" className="note">
                      {autoNote} (only legal action)
                    </p>
                  )}
                  {over ? (
                    <GameOver game={game} onExit={onExit} onExport={doExport} />
                  ) : (
                    cp !== null && (
                      <>
                        {humanTurn && showBoard && (
                          <YourMove
                            humanTurn
                            waitingFor={null}
                            actions={legalActions(game)}
                            busy={busy}
                            onAct={(id) => void act(id)}
                            labelFor={(a) => plugin.actionLabel?.(game, a) ?? a.label}
                            onHover={setHoverAction}
                            describe={(a) => plugin.actionHelp?.(game, a)}
                          />
                        )}
                        <p className="sr-only">
                          Current player: P{cp} ({game.seats[cp]})
                        </p>
                      </>
                    )
                  )}
                </div>
                {plugin.renderSeats && showBoard && (
                  <div className="lg-pane-seats">{plugin.renderSeats(game, ui)}</div>
                )}
                <div className="lg-log lg-pane-log card">
                  <h3 className="eyebrow">Action log</h3>
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

const statusLine = (g: GameView): string =>
  `Game ${g.id} · seats: ${g.seats.map((s, i) => `P${i} ${s}`).join(", ")}`;
