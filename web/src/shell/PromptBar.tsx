import type { ReactNode } from "react";
import { IconUndo } from "../theme/icons";

interface Props {
  /** Seat to act (null when the game is over or no one acts). */
  seat: number | null;
  /** Phase title in the display face. */
  title?: string;
  /** One-sentence prompt under the title. */
  prompt: string;
  /** True while a bot is thinking: shows a spinner and announces `thinking`. */
  waiting?: boolean;
  thinking?: string;
  onBack?: () => void;
  backDisabled?: boolean;
  /** Reserved for a future "Skip to my turn" button, shown only while waiting on a bot. */
  skipSlot?: ReactNode;
}

/** Banner over the board: whose turn it is, the phase, what to do, and Back. */
export default function PromptBar({
  seat,
  title,
  prompt,
  waiting,
  thinking,
  onBack,
  backDisabled,
  skipSlot,
}: Props) {
  return (
    <div className="lg-prompt card" data-seat={seat ?? undefined}>
      <span className="lg-prompt-band" aria-hidden="true" />
      {seat !== null && (
        <span className="seat-tile" data-seat={seat} aria-hidden="true">
          P{seat}
        </span>
      )}
      <div className="lg-prompt-text">
        {title && <h2 className="lg-prompt-title">{title}</h2>}
        <p className="lg-prompt-line">
          {waiting && (
            <span className="spinner" role="status">
              <span className="sr-only">{thinking}</span>
            </span>
          )}
          <span>{prompt}</span>
        </p>
      </div>
      <div className="lg-prompt-actions">
        {waiting && skipSlot}
        {onBack && (
          <button type="button" className="btn btn-sm" disabled={backDisabled} onClick={onBack}>
            <IconUndo /> Back
          </button>
        )}
      </div>
    </div>
  );
}
