import { useState, type CSSProperties, type ReactNode } from "react";
import type { GameView } from "../../../shell/useGame";
import type { BoardUi } from "../../registry";
import { useTheme } from "../theme/ThemeProvider";
import type { LignumPathLocation, LignumView } from "../types";
import "./board.css";
import type { ClickTarget } from "./clickTargets";
import { boardTargets } from "./sectionTargets";
import { LAYOUTS, foodAnchor, woodAnchor, type Pt, type SideLayout } from "./layout";
import { seatColor } from "./seatColors";
import { BoardCards, Trackers } from "./Trackers";
import { taskCards } from "../CardsPanel";
import { useLastChange } from "./lastChange";

const KINDS = ["firewood", "softwood", "hardwood"];
const SLOTS = ["A", "B", "C", "D"];
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const num = (x: unknown): number | undefined => (typeof x === "number" && Number.isFinite(x) ? x : undefined);
const flat = (x: unknown): number[] => (Array.isArray(x) ? x.flatMap(flat) : num(x) !== undefined ? [x as number] : []);
const pct = (n: number): string => `${(n * 100).toFixed(2)}%`;
const at = (p: Pt, w?: number, h?: number): CSSProperties => ({
  left: pct(p.x),
  top: pct(p.y),
  ...(w !== undefined && h !== undefined ? { width: pct(w), height: pct(h) } : {}),
});
const tokenIcon = (kind: string): string =>
  kind === "$1" ? "icon-dollar" : kind === "X marker" ? "icon-x" : `icon-${kind}`;

/** Seat-coloured pawn sprite; falls back to a coloured disc if the theme lacks it. */
function Pawn({ seat, title }: { seat: number; title: string }) {
  const { sprite } = useTheme();
  const s = sprite(`pawn-${seat}`);
  return s ? (
    <img className="lgb-pawn" src={s.src} alt={title} />
  ) : (
    <span className="lgb-pawn" role="img" aria-label={title} style={{ background: seatColor(seat), borderRadius: "50%", aspectRatio: "1" }} />
  );
}

function Region({ label, pos, children, className }: { label: string; pos: CSSProperties; children?: ReactNode; className?: string }) {
  return (
    <div className={`lgb-r${className ? " " + className : ""}`} role="group" aria-label={label} style={pos}>
      {children}
    </div>
  );
}

export default function Board({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const [open, setOpen] = useState<string | null>(null);
  const { sprite } = useTheme();
  const v = (game.view ?? {}) as LignumView;
  const joinery = v.game?.joinery === true;
  const side = joinery ? "joinery" : "base";
  const L = LAYOUTS[side];
  const boardSprite = (joinery ? sprite("board-joinery") : undefined) ?? sprite("board");
  const high = flat(v.high_areas);
  const picks = arr(v.picks).map(flat);
  const own = num(v.private?.pick);
  const foreman = arr(v.foreman).map(num);
  const locs = arr(v.path?.locations) as Partial<LignumPathLocation>[];
  const slots = v.path?.clearing_slots;
  // Prefer the path occupancy fields; fall back to the flat foreman/clearing/tokens arrays.
  const clearing: (number | undefined)[] = Array.isArray(slots) ? slots.map(num) : flat(v.clearing);
  const turn = flat(v.turn_order);
  const tokens = v.path?.tokens ?? [];
  const changed = useLastChange(v);
  const lastCls = (on: boolean, base?: string): string | undefined => [base, on ? "lgb-last" : ""].filter(Boolean).join(" ") || undefined;
  const locAt = (n: number) => locs.find((l) => l?.number === n);

  const seatsAt = (n: number): number[] => {
    const l = locAt(n);
    return l && Array.isArray(l.foremen) ? flat(l.foremen) : foreman.flatMap((p, s) => (p === n ? [s] : []));
  };

  return (
    <div className="lgb" role="group" aria-label="Game board" data-side={side} style={{ aspectRatio: `${L.width} / ${L.height}`, ["--lgb-r" as string]: L.width / L.height }}>
      {boardSprite && <img className="lgb-img" src={boardSprite.src} alt="" data-theme={boardSprite.theme} />}

      {L.areas.map((a) => {
        const i = a.n - 1;
        const wood = arr(arr(v.area_wood)[i]).map((c) => num(c) ?? 0);
        const food = num(arr(v.area_food)[i]) ?? 0;
        const isHigh = high.includes(i);
        const bits = KINDS.flatMap((k, ki) => ((wood[ki] ?? 0) > 0 ? [`${wood[ki]} ${k}`] : []));
        if (food > 0) bits.push(`${food} food`);
        const seats = [...new Set([...picks.flatMap((p, s) => (p.includes(i) ? [s] : [])), ...(own === i && v.seat !== undefined ? [v.seat] : [])])];
        const label = `Cutting area ${a.n}${isHigh ? " (high wood)" : ""}: ${bits.join(", ") || "empty"}${
          seats.length ? `; picked by ${seats.map((s) => `P${s}`).join(", ")}` : ""
        }`;
        return (
          <Region key={a.n} label={label} pos={at(a, a.w, a.h)} className={lastCls(changed.areas.includes(a.n), isHigh ? "lgb-high" : undefined)}>
            {KINDS.map((k, ki) => {
              const c = wood[ki] ?? 0;
              const s = sprite(`piece-${k}-disk`);
              if (c <= 0) return null;
              return (
                <span key={k} className="lgb-piece" style={{ position: "absolute", transform: "translate(-50%,-50%)", ...relTo(woodAnchor(a, ki), a) }}>
                  {s && <img src={s.src} alt="" />}
                  <span className="lgb-badge" aria-hidden="true">{c}</span>
                </span>
              );
            })}
            {food > 0 && (
              <span className="lgb-piece" style={{ position: "absolute", transform: "translate(-50%,-50%)", ...relTo(foodAnchor(a), a) }}>
                {sprite("icon-food") && <img src={sprite("icon-food")?.src} alt="" />}
                <span className="lgb-badge" aria-hidden="true">{food}</span>
              </span>
            )}
            <span style={{ position: "absolute", transform: "translate(-50%,-50%)", display: "flex", gap: "0.2cqw", ...relTo(a.token, a) }}>
              {seats.map((s) => (
                <Pawn key={s} seat={s} title={`P${s} cutting token`} />
              ))}
            </span>
          </Region>
        );
      })}

      {Object.entries(L.locations).map(([k, loc]) => {
        const n = Number(k);
        const here = seatsAt(n);
        const tok = locAt(n)?.token ?? tokens.find((t) => t.location === n);
        const pool = poolOf(locAt(n));
        const kindText = tok ? (tok.taken ? "taken" : (tok.kind ?? "taken")) : undefined;
        const label =
          `Location ${n}` +
          (kindText ? `, token spot: ${kindText}` : "") +
          (here.length ? `; foremen: ${here.map((s) => `P${s}`).join(", ")}` : "");
        return (
          <Region key={n} label={label} pos={at(loc, loc.w, loc.h)} className={lastCls(changed.locs.includes(n))}>
            {here.map((s) => (
              <Pawn key={s} seat={s} title={`P${s} foreman`} />
            ))}
            {pool && (
              <span className="lgb-pool" role="img" aria-label={`Location ${n} ${pool.text}`} data-testid={`pool-${n}`}>
                {pool.short}
              </span>
            )}
          </Region>
        );
      })}

      {Object.entries(L.locations).flatMap(([k, loc]) => {
        const tok = locAt(Number(k))?.token ?? tokens.find((t) => t.location === Number(k));
        if (!tok || tok.taken || !tok.kind) return [];
        return [<TokenChip key={`t${k}`} kind={tok.kind} pos={loc.spot ?? loc} />];
      })}

      <Region label={`Location 0 (start): ${seatsAt(0).map((s) => `P${s}`).join(", ") || "no foremen"}`} pos={at(L.start, L.start.w, L.start.h)} className={lastCls(changed.locs.includes(0), "lgb-start")}>
        {seatsAt(0).map((s) => (
          <Pawn key={s} seat={s} title={`P${s} foreman`} />
        ))}
      </Region>

      {L.clearing.map((p, i) => {
        const s = clearing[i];
        return (
          <Region key={i} label={`Clearing slot ${SLOTS[i]}: ${s !== undefined ? `P${s}` : "empty"}`} pos={at(p)} className={lastCls(changed.clearing.includes(i))}>
            {s !== undefined ? <Pawn seat={s} title={`P${s} foreman`} /> : <span className="lgb-slot" aria-hidden="true" />}
          </Region>
        );
      })}

      {L.turn.map((p, i) => {
        const s = turn[i];
        return (
          <Region key={i} label={`Starting player position ${i + 1}: ${s !== undefined ? `P${s}` : "none"}`} pos={at(p)}>
            {s !== undefined && <Pawn seat={s} title={`P${s} turn order`} />}
          </Region>
        );
      })}

      <Trackers v={v} L={L} />
      <BoardCards v={v} L={L} tasks={taskCards(v, arr(v.tasks?.row), [])} joinery={joinery} />

      {ui?.canAct && ui.onAct && (
        <Hotspots
          targets={boardTargets(game.legal_actions ?? [], v.seat !== undefined ? foreman[v.seat] : undefined)}
          L={L}
          clearingFilled={clearing.filter((c) => c !== undefined).length}
          open={open}
          setOpen={setOpen}
          hover={ui.hoverAction}
          onAct={(id) => {
            setOpen(null);
            void ui.onAct?.(id);
          }}
        />
      )}
    </div>
  );
}

/** Pieces on offer at a location (bearers, woodcutters, fodder, joiner, sawyers); undefined if none or malformed. */
function poolOf(l?: Partial<LignumPathLocation>): { short: string; text: string } | undefined {
  const p = l?.pool;
  const noun: Record<string, string> = { bearers: "bearers", woodcutters: "woodcutters", fodder: "fodder", joiner: "joiners" };
  if (typeof p === "number" && Number.isFinite(p) && l?.kind && noun[l.kind]) return { short: String(p), text: `pool: ${p} ${noun[l.kind]}` };
  if (p && typeof p === "object" && "free" in p) {
    const f = num(p.free) ?? 0;
    const d = num(p.paid) ?? 0;
    return { short: `${f}+${d}`, text: `pool: ${f} free sawyers, ${d} paid sawyers` };
  }
  return undefined;
}

const TOKEN_SPOT = 0.034;

/** Fractional centre and size of a target's hotspot on the board image. */
function hotRect(t: ClickTarget, L: SideLayout, clearingFilled: number): { x: number; y: number; w: number; h: number } | undefined {
  const r = t.region;
  if (r.type === "area") return L.areas.find((a) => a.n === r.n);
  const square = (p: Pt) => ({ x: p.x, y: p.y, w: TOKEN_SPOT, h: (TOKEN_SPOT * L.width) / L.height });
  if (r.type === "clearing") {
    const p = L.clearing[Math.min(clearingFilled, L.clearing.length - 1)];
    return p && square(p);
  }
  const loc = L.locations[r.n];
  if (!loc) return undefined;
  return loc.w !== undefined && loc.h !== undefined ? { x: loc.x, y: loc.y, w: loc.w, h: loc.h } : square(loc.spot ?? loc);
}

function Hotspots({
  targets, L, clearingFilled, open, setOpen, hover, onAct,
}: {
  targets: ClickTarget[];
  L: SideLayout;
  clearingFilled: number;
  open: string | null;
  setOpen: (k: string | null) => void;
  hover: number | null;
  onAct: (id: number) => void;
}) {
  return (
    <>
      {targets.map((t) => {
        const rect = hotRect(t, L, clearingFilled);
        if (!rect) return null;
        const lit = hover !== null && t.actions.some((a) => a.id === hover);
        const multi = t.actions.length > 1 || /^(Hire|Buy)/.test(t.actions[0]!.label); // hiring and buying show their choices
        const only = t.actions[0]!;
        const label = multi ? `Board: ${t.label}: ${t.actions.length} actions` : `Board: ${only.label}`;
        return (
          <div key={t.key} className="lgb-hot-wrap" style={at(rect, rect.w, rect.h)}>
            <button
              type="button"
              className={`lgb-hot${lit ? " lgb-hot-lit" : ""}`}
              data-testid={`hot-${t.key}`}
              aria-label={label}
              aria-haspopup={multi ? "true" : undefined}
              aria-expanded={multi ? open === t.key : undefined}
              onClick={() => (multi ? setOpen(open === t.key ? null : t.key) : onAct(only.id))}
            />
            {multi && open === t.key && (
              <div className="lgb-pop" role="group" aria-label={`Board: ${t.label} actions`}>
                {t.actions.map((a) => (
                  <button key={a.id} type="button" className={hover === a.id ? "lgb-hot-lit" : undefined} aria-label={`Board: ${a.label}`} onClick={() => onAct(a.id)}>
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

/** Position inside a region box, given an absolute fractional anchor. */
function relTo(p: Pt, box: { x: number; y: number; w: number; h: number }): CSSProperties {
  return { left: pct((p.x - box.x) / box.w + 0.5), top: pct((p.y - box.y) / box.h + 0.5) };
}

function TokenChip({ kind, pos }: { kind: string; pos: Pt }) {
  const { sprite } = useTheme();
  const s = sprite(tokenIcon(kind));
  return (
    <span className="lgb-r lgb-chip" style={at(pos)} data-testid="path-token">
      {s ? <img src={s.src} alt={`${kind} token`} /> : <span className="lgb-chip-text">{kind}</span>}
    </span>
  );
}
