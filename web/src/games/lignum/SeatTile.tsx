/** The seat's colour tile with its label ("P0"); colour is never the only seat cue. */
export default function SeatTile({ seat, label }: { seat: number; label?: string }) {
  return (
    <span className="seat-tile" data-seat={seat}>
      {label || `P${seat}`}
    </span>
  );
}
