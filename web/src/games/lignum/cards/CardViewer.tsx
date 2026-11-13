import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTheme } from "../theme/ThemeProvider";
import type { CardProps } from "./Card";
import { cardInfo } from "./cardInfo";
import { cardSpriteId } from "./spriteIds";
import "./cards.css";

interface Opener {
  /** Open the viewer on `set[index]`; the arrow keys then step through `set`. */
  open: (set: CardProps[], index: number, title?: string) => void;
}

const Ctx = createContext<Opener | null>(null);
/** Null outside a CardViewerProvider (the enlarge buttons are then hidden). */
export const useCardViewer = (): Opener | null => useContext(Ctx);

/** Full text for a card: data-derived lines when known, else the detail the view gave. */
export function describe(c: CardProps): { title: string; lines: string[] } {
  const info = cardInfo(c.kind, c.id);
  const lines = info?.lines ?? (c.detail ? [c.detail] : []);
  return { title: info?.title ?? c.id, lines: c.done ? [...lines, "Completed"] : lines };
}

function Viewer({ set, index, title, setIndex, onClose }: { set: CardProps[]; index: number; title?: string; setIndex: (i: number) => void; onClose: () => void }) {
  const { sprite } = useTheme();
  const ref = useRef<HTMLDivElement>(null);
  const c = set[index]!;
  const sp = sprite(c.spriteId ?? cardSpriteId(c.kind, c.id));
  const d = describe(c);
  const step = useCallback((n: number) => setIndex((index + n + set.length) % set.length), [index, set.length, setIndex]);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <div className="lgv-back" onClick={onClose} data-testid="card-viewer-backdrop">
      <div
        ref={ref}
        className="lgv"
        role="dialog"
        aria-modal="true"
        aria-label={`Card viewer: ${d.title}`}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          else if (e.key === "ArrowRight") step(1);
          else if (e.key === "ArrowLeft") step(-1);
          else return;
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        <div className="lgv-head">
          <strong>{title ? `${title}: ` : ""}{index + 1} of {set.length}</strong>
          <button type="button" onClick={onClose} aria-label="Close card viewer">Close (Esc)</button>
        </div>
        <div className="lgv-body">
          {set.length > 1 && <button type="button" className="lgv-nav" onClick={() => step(-1)} aria-label="Previous card">{"<"}</button>}
          {sp && <img className="lgv-img" src={sp.src} alt={sp.alt || d.title} data-theme={sp.theme} />}
          <div className="lgv-text">
            <h3>{d.title}</h3>
            <ul>
              {d.lines.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
            {c.tokens && c.tokens.length > 0 && <p>Planned by {c.tokens.map((t) => `P${t.seat} (pair ${t.pair})`).join(", ")}</p>}
          </div>
          {set.length > 1 && <button type="button" className="lgv-nav" onClick={() => step(1)} aria-label="Next card">{">"}</button>}
        </div>
        <p className="lgv-hint">Arrow keys step through the set, Esc closes. Enlarge any card with its magnifier button, or Shift-click it.</p>
      </div>
    </div>
  );
}

export function CardViewerProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ set: CardProps[]; index: number; title?: string } | null>(null);
  const prev = useRef<Element | null>(null);
  const open = useCallback((set: CardProps[], index: number, title?: string) => {
    if (set.length === 0) return;
    prev.current = document.activeElement;
    setState({ set, index: Math.min(Math.max(index, 0), set.length - 1), title });
  }, []);
  const close = useCallback(() => {
    setState(null);
    (prev.current as HTMLElement | null)?.focus?.();
  }, []);
  const value = useMemo(() => ({ open }), [open]);
  return (
    <Ctx.Provider value={value}>
      {children}
      {state && <Viewer {...state} setIndex={(i) => setState({ ...state, index: i })} onClose={close} />}
    </Ctx.Provider>
  );
}
