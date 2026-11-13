import { useTheme } from "../theme/ThemeProvider";
import { useCardViewer } from "./CardViewer";
import { seatColor } from "../board/seatColors";
import { cardSpriteId, type CardKind } from "./spriteIds";

export interface CardProps {
  kind: CardKind;
  /** Id or name from the view; mapped to a sprite id unless `spriteId` is given. */
  id: string;
  spriteId?: string;
  /** Text shown (and read out) when no sprite resolves: reward, requirements, etc. */
  detail?: string;
  /** Marks a completed / filled card. */
  done?: boolean;
  /** Planned-work pair tokens placed on this card: seat and pair number. */
  tokens?: { seat: number; pair: number }[];
  /** Highlights the card as the one in play now (e.g. planned work resolving this round). */
  current?: boolean;
  /** Plain click enlarges the card (only for cards that are not action targets). */
  clickOpens?: boolean;
}

/** One card: its sprite when the theme has one, else a text box with the id and details. */
export default function Card({ kind, id, spriteId, detail, done, tokens, current, clickOpens, set, index, setTitle }: CardProps & { set?: CardProps[]; index?: number; setTitle?: string }) {
  const { sprite } = useTheme();
  const viewer = useCardViewer();
  const self: CardProps = { kind, id, spriteId, detail, done, tokens, current };
  const enlarge = () => viewer?.open(set ?? [self], set ? (index ?? 0) : 0, setTitle);
  const sp = sprite(spriteId ?? cardSpriteId(kind, id));
  const label = `${kind} ${id}${detail ? `: ${detail}` : ""}${done ? " (done)" : ""}${current ? " (current)" : ""}`;
  return (
    <figure className={`lgc-card${done ? " lgc-done" : ""}${current ? " lgc-current" : ""}${clickOpens ? " lgc-click" : ""}`} aria-label={label} data-kind={kind} data-testid="lgc-card" onClick={(e) => (e.shiftKey || clickOpens) && enlarge()}>
      {sp ? (
        <img src={sp.src} alt={sp.alt || label} title={label} data-theme={sp.theme} />
      ) : (
        <figcaption className="lgc-text" data-testid="lgc-fallback">
          <strong>{id}</strong>
          {detail && <span>{detail}</span>}
        </figcaption>
      )}
      {viewer && (
        <button type="button" className="lgc-mag" aria-label={`Enlarge ${kind} ${id}`} title="Enlarge card (or Shift-click it)" onClick={(e) => { e.stopPropagation(); enlarge(); }}>
          +
        </button>
      )}
      {tokens && tokens.length > 0 && (
        <span className="lgb-ptok" aria-label={tokens.map((t) => `P${t.seat} pair ${t.pair}`).join(", ")}>
          {tokens.map((t, i) => (
            <span key={i} style={{ background: seatColor(t.seat) }} title={`P${t.seat} pair token ${t.pair}`}>{t.pair}</span>
          ))}
        </span>
      )}
    </figure>
  );
}
