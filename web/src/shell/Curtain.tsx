/** Hotseat hand-off cover: shown instead of the board, actions and log. */
export default function Curtain({
  seat,
  onReveal,
  disabled = false,
}: {
  seat: number;
  onReveal: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="lg-curtain" data-seat={seat} role="dialog" aria-modal="true" aria-label="Hand-off">
      <div className="lg-curtain-card panel-framed">
        <p className="eyebrow">Hotseat hand-off</p>
        <span className="lg-curtain-tile" aria-hidden="true">
          P{seat}
        </span>
        <p className="lg-curtain-title">Pass to P{seat}</p>
        <p className="lg-curtain-sub">Hidden picks stay covered until P{seat} is ready.</p>
        <button
          type="button"
          className="btn btn-primary btn-lg"
          onClick={onReveal}
          disabled={disabled}
          autoFocus
        >
          Click when ready
        </button>
      </div>
    </div>
  );
}
