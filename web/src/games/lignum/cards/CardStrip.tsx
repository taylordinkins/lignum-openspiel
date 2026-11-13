import { useCardViewer } from "./CardViewer";
import Card, { type CardProps } from "./Card";
import "./cards.css";

/** A titled, wrapping row of cards; renders nothing when the list is empty and `showEmpty` is off. */
export default function CardStrip({ title, cards, showEmpty }: { title: string; cards: CardProps[]; showEmpty?: boolean }) {
  const viewer = useCardViewer();
  if (cards.length === 0 && !showEmpty) return null;
  return (
    <div className="lgc-strip" role="group" aria-label={title}>
      <strong className="lgc-title">
        {title}
        {viewer && cards.length > 0 && (
          <button type="button" className="lgc-browse" aria-label={`Browse ${title}`} onClick={() => viewer.open(cards, 0, title)}>
            Browse
          </button>
        )}
      </strong>
      {cards.length === 0 ? <span className="lgc-none">none</span> : cards.map((c, i) => <Card key={`${c.id}-${i}`} {...c} set={cards} index={i} setTitle={title} />)}
    </div>
  );
}
