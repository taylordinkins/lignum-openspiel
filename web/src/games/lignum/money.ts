/** Dollars as shown to players and screen readers: "$5", "-$5". */
export const dollars = (n: number): string => (n < 0 ? `-$${-n}` : `$${n}`);
