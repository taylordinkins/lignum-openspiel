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
    <div className="lg-curtain" role="dialog" aria-modal="true" aria-label="Hand-off">
      <p>Pass to P{seat}</p>
      <button type="button" onClick={onReveal} disabled={disabled} autoFocus>
        Click when ready
      </button>
    </div>
  );
}
