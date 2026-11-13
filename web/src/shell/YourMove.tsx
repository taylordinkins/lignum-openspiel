import ActionList from "./ActionList";
import type { LegalAction } from "./useGame";

interface Props {
  /** True when a human seat is to act and the game is not over. */
  humanTurn: boolean;
  /** Seat description of whoever acts when it is not the human's turn, e.g. "P1 (random)". */
  waitingFor: string | null;
  /** Game-specific phase text, shown under the heading. */
  phase?: string;
  actions: LegalAction[];
  busy: boolean;
  onAct: (id: number) => void;
  labelFor?: (a: LegalAction) => string;
  onHover?: (id: number | null) => void;
  describe?: (a: LegalAction) => string | undefined;
}

/** The primary call to action: what the human should do now, or a muted waiting state. */
export default function YourMove({
  humanTurn,
  waitingFor,
  phase,
  actions,
  busy,
  onAct,
  labelFor,
  onHover,
  describe,
}: Props) {
  if (!humanTurn) {
    return (
      <section className="lg-move" data-state="waiting" aria-label="Your move" role="region">
        <h2>{waitingFor ? `Waiting for ${waitingFor}…` : "Waiting…"}</h2>
      </section>
    );
  }
  return (
    <section className="lg-move" data-state="active" aria-label="Your move" role="region">
      <h2>Your move: choose an action</h2>
      {phase && <p className="lg-move-sub">Phase: {phase}</p>}
      <p className="lg-move-hint">Highlighted spots on the board and sawmill do the same; hover a button to find its spot.</p>
      <ActionList
        actions={actions}
        disabled={busy}
        onAct={onAct}
        labelFor={labelFor}
        onHover={onHover}
        describe={describe}
      />
    </section>
  );
}
