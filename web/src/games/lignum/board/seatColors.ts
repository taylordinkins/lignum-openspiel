/** Seat colours; match the generic pawn sprites (tools/make_generic_theme.py SEATS). */
export const SEAT_COLORS = ["#c0392b", "#2e6fb5", "#2e8b57", "#d4a017"] as const;
export const seatColor = (seat: number): string => SEAT_COLORS[seat % SEAT_COLORS.length] ?? "#555555";
