import type { CSSProperties } from "react";
import type { CardProps } from "../cards/Card";
import CardStrip from "../cards/CardStrip";
import type { LignumView } from "../types";
import { seatColor } from "./seatColors";
import type { Rect, SideLayout } from "./layout";

const SEASONS = ["spring", "summer", "fall", "winter"] as const;
const pct = (n: number): string => `${(n * 100).toFixed(2)}%`;
const box = (r: Rect): CSSProperties => ({ left: pct(r.x), top: pct(r.y), width: pct(r.w), height: pct(r.h) });

/** Round 1..8 -> season and year (R-033). */
export function seasonOf(round: number): { season: (typeof SEASONS)[number]; year: 1 | 2 } | undefined {
  if (!Number.isInteger(round) || round < 1 || round > 8) return undefined;
  return { season: SEASONS[(round - 1) % 4]!, year: round > 4 ? 2 : 1 };
}

/**
 * Where the phase marker sits on the printed phase track: a numbered wood-work or winter phase box,
 * the winter label (WS, NB), or the season legend for the pre-wood-work phases of a seasonal round.
 */
export function phaseTarget(phase: string | undefined, round: number | undefined): string | undefined {
  if (!phase) return undefined;
  if (/^(W[1-7]|N[1-6])$/.test(phase)) return phase;
  if (phase === "SF") return "N6";
  if (phase === "WS" || phase === "NB") return "winter";
  const s = seasonOf(round ?? 0);
  if (["RS", "PK", "TR"].includes(phase) && s && s.season !== "winter") return s.season;
  return undefined;
}

const cap = (s: string): string => s[0]!.toUpperCase() + s.slice(1);

/** One-line readout of the current year, season, round and the planned work resolving now. */
export function roundSummary(v: LignumView): string {
  const round = typeof v.round === "number" ? v.round : undefined;
  const s = seasonOf(round ?? 0);
  if (!s || round === undefined) return "";
  const now = [...new Set(activePlans(v).filter((p) => p.target === round).map((p) => p.name))];
  return `Year ${s.year}, ${cap(s.season)} (round ${round})${now.length ? `; planned work now: ${now.join(", ")}` : ""}`;
}

/** Marker overlays on the printed phase track and round rows, with the phase / round as tooltip. */
export function Trackers({ v, L }: { v: LignumView; L: SideLayout }) {
  const T = L.trackers;
  const round = typeof v.round === "number" ? v.round : undefined;
  const target = phaseTarget(v.phase, round);
  const pr = target ? (T.phase[target] ?? T.legend[target as "spring"]) : undefined;
  const label = (v.phase_label ?? "").replace(/^\S+ · /, "") || v.phase;
  const s = seasonOf(round ?? 0);
  const sr = round !== undefined && s ? T.season[String(round)] : undefined;
  const roundText = s ? `Round ${round}: ${cap(s.season)}, year ${s.year}` : "";
  return (
    <>
      {pr && <div className="lgb-mark lgb-mark-phase" role="img" style={box(pr)} aria-label={`Phase: ${label}`} title={`Phase: ${label}`} data-testid="phase-marker" data-at={target} />}
      {activePlans(v).map((p, i, all) => {
        const r = T.season[String(p.target)];
        if (!r) return null;
        const k = all.slice(0, i).filter((q) => q.target === p.target).length + 1;
        const txt = `P${p.seat} ${p.name}: pair ${p.pair}, round ${p.target}`;
        return (
          <div key={i} className="lgb-mark lgb-mark-ptok" role="img" aria-label={txt} title={txt} data-testid="plan-token" style={{ ...box({ ...r, x: r.x - r.w * 1.1 * k }), background: seatColor(p.seat) }}>
            {p.pair}
          </div>
        );
      })}
      {sr && (
        <div className="lgb-mark lgb-mark-row" style={box({ x: sr.x, y: sr.y, w: sr.w * 1.7, h: sr.h * 1.35 })} data-testid="round-row" aria-hidden="true" />
      )}
      {sr && (
        <div className="lgb-mark lgb-mark-round" role="img" style={box(sr)} aria-label={roundText} title={roundText} data-testid="round-marker">
          {round}
        </div>
      )}
    </>
  );
}

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const str = (x: unknown): string => (typeof x === "string" ? x : "");

type Plan = { seat: number; name: string; pair: number; target: number };

/** Planned-work placements still active (target round not yet over), all seats (R-087: public). */
export function activePlans(v: LignumView): Plan[] {
  const round = typeof v.round === "number" ? v.round : 0;
  const seats = arr(v.seats) as { plans?: { name?: unknown; pair?: unknown; target?: unknown }[] }[];
  return seats.flatMap((s, seat) =>
    arr(s?.plans).flatMap((p) => {
      const q = p as { name?: unknown; pair?: unknown; target?: unknown };
      const target = typeof q.target === "number" ? q.target : 0;
      return target >= round ? [{ seat, name: str(q.name), pair: typeof q.pair === "number" ? q.pair : 0, target }] : [];
    }),
  );
}

function CardsAt({ title, r, cards: raw, className }: { title: string; r: Rect; cards: CardProps[]; className?: string }) {
  if (raw.length === 0) return null;
  const cards = raw.map((c) => ({ ...c, clickOpens: true }));
  return (
    <div className={`lgb-cl${className ? " " + className : ""}`} style={box(r)}>
      <CardStrip title={title} cards={cards} />
    </div>
  );
}

/** Compact task, planned-work, building-supply and winter cards at their printed board locations; click or the magnifier opens the viewer. */
export function BoardCards({ v, L, tasks, joinery }: { v: LignumView; L: SideLayout; tasks: CardProps[]; joinery: boolean }) {
  const C = L.trackers.cards;
  const plans = activePlans(v);
  const round = typeof v.round === "number" ? v.round : 0;
  const pw: CardProps[] = arr(v.pw?.cards).map((c) => {
    const id = str((c as { name?: unknown } | null)?.name);
    const mine = plans.filter((p) => p.name === id);
    return { kind: "pw" as const, id, tokens: mine.map((p) => ({ seat: p.seat, pair: p.pair })), current: mine.some((p) => p.target === round), clickOpens: true };
  });
  const buildings: CardProps[] = arr(v.buildings?.names).map((n) => ({ kind: "building" as const, id: str(n) }));
  const winters = arr(v.winter?.cards) as { year?: number; food?: number; heating?: number }[];
  return (
    <>
      <CardsAt title="Task row" r={C.tasks} cards={tasks} className="lgb-cl-up" />
      <CardsAt title="Planned-work row" r={C.pw} cards={pw} className="lgb-cl-up" />
      {joinery && <CardsAt title="Building supply" r={C.buildings} cards={buildings} className="lgb-cl-tile" />}
      {winters.map((w, i) => {
        const r = C.winter[(w.year ?? 1) - 1];
        const id = str(arr(v.winter?.card_ids)[i]) || `winter ${w.year}`;
        return r ? <CardsAt key={id} title={`Winter card, year ${w.year}`} r={r} cards={[{ kind: "winter", id, detail: `food ${w.food ?? 0}, heating ${w.heating ?? 0}` }]} /> : null;
      })}
    </>
  );
}
