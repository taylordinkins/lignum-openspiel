import { useState, type CSSProperties, type ReactNode } from "react";
import type { GameView } from "../../../shell/useGame";
import type { BoardUi } from "../../registry";
import { useTheme } from "../theme/ThemeProvider";
import type { LignumSeatView, LignumView } from "../types";
import "./sawmill.css";
import type { TargetAction } from "./clickTargets";
import { GENERIC_PADS, PADS, type PadLayout } from "./sawmillLayout";
import { sawmillSections } from "./sectionTargets";
import { buildingEffect } from "../cards/cardInfo";
import { cardSpriteId } from "../cards/spriteIds";

const KINDS = ["firewood", "softwood", "hardwood"];
const EQUIP = ["saw", "wagon", "raft", "sledge"];
const CRAFT = ["board", "shingle", "stake", "reed", "joker"];
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const num = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) ? x : 0);
const nums = (x: unknown): number[] => arr(x).map(num);
const str = (x: unknown): string => (typeof x === "string" ? x : "");
const pct = (n: number): string => `${(n * 100).toFixed(2)}%`;
const plural = (n: number, w: string): string => `${n} ${w}${n === 1 ? "" : "s"}`;

/** One thing shown in a region: a sprite (if the theme has it), a count and the words for the aria-label. */
interface Item {
  sprite?: string;
  n: number;
  text: string;
  off?: boolean;
}

const UNMILLED = "log";
const MILLED = "milled";

/**
 * Per-kind counts (kind index 0..2) as items, `piece-<kind>-<form>` sprites. Form "disk" is unmilled
 * wood (labelled "log") and "log" is milled wood (labelled "milled"); the sprite ids keep the
 * rulebook names (R-007) and each theme draws them as it likes.
 */
function kindItems(counts: unknown, kinds: string[], form: "disk" | "log", noun: string, offset = 0): Item[] {
  const c = nums(counts);
  return kinds.flatMap((k, i) => {
    const n = c[i + offset] ?? 0;
    return n > 0 ? [{ sprite: `piece-${k}-${form}`, n, text: `${n} ${k} ${n === 1 || noun === MILLED ? noun : noun + "s"}` }] : [];
  });
}

interface RegionSpec {
  key: string;
  name: string;
  items: Item[];
  /** Overrides the item-derived description. */
  desc?: string;
  cls?: string;
  /** Short text under the items (building effect), clamped; the full text is the tooltip. */
  caption?: string;
}

function Items({ items }: { items: Item[] }) {
  const { sprite } = useTheme();
  return (
    <>
      {items.map((it, i) => {
        const s = it.sprite ? sprite(it.sprite) : undefined;
        return (
          <span key={i} className={`lgs-i${it.off ? " lgs-off" : ""}`} data-testid="lgs-item" title={it.text}>
            {s && <img src={s.src} alt="" />}
            {it.n > 1 || !s ? <span>{s ? it.n : it.text}</span> : null}
          </span>
        );
      })}
    </>
  );
}

/** Click-to-act state for the viewer's own pad: legal actions per section, popover and hover link. */
interface Hot {
  sections: Record<string, TargetAction[]>;
  hover: number | null;
  open: string | null;
  setOpen: (k: string | null) => void;
  onAct: (id: number) => void;
}

function SectionHot({ name, id, acts, box, hot }: { name: string; id: string; acts: TargetAction[]; box: PadLayout["regions"][string]; hot: Hot }) {
  const multi = acts.length > 1 || /^(Hire|Buy)/.test(acts[0]!.label); // hiring and buying show their choices
  const lit = hot.hover !== null && acts.some((a) => a.id === hot.hover);
  return (
    <div className="lgs-hot-wrap" style={{ left: pct(box.x), top: pct(box.y), width: pct(box.w), height: pct(box.h) }}>
      <button
        type="button"
        className={`lgs-hot${lit ? " lgs-hot-lit" : ""}`}
        data-testid={`hot-${id}`}
        aria-label={multi ? `Board: ${name}: ${acts.length} actions` : `Board: ${acts[0]!.label}`}
        aria-haspopup={multi ? "true" : undefined}
        aria-expanded={multi ? hot.open === id : undefined}
        onClick={() => (multi ? hot.setOpen(hot.open === id ? null : id) : hot.onAct(acts[0]!.id))}
      />
      {multi && hot.open === id && (
        <div className={`lgs-pop${box.y > 0.5 ? " lgs-pop-up" : ""}`} role="group" aria-label={`Board: ${name} actions`}>
          {acts.map((a) => (
            <button key={a.id} type="button" className={hot.hover === a.id ? "lgs-hot-lit" : undefined} aria-label={`Board: ${a.label}`} onClick={() => hot.onAct(a.id)}>
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Pad({ pad, spriteId, altId, seat, specs, cls, hot }: { pad: keyof typeof PADS; spriteId: string; altId?: string; seat: string; specs: RegionSpec[]; cls?: string; hot?: Hot }) {
  const { sprite } = useTheme();
  const bg = (altId ? sprite(altId) : undefined) ?? sprite(spriteId);
  const layout: PadLayout = bg?.theme === "generic" ? GENERIC_PADS[pad] : PADS[pad];
  return (
    <div className={`lgs-pad${cls ? " " + cls : ""}`} style={{ aspectRatio: `${layout.width} / ${layout.height}`, ["--lgs-r" as string]: layout.width / layout.height }}>
      {bg && <img className="lgs-img" src={bg.src} alt="" data-theme={bg.theme} />}
      {specs.map((r) => {
        const b = layout.regions[r.key];
        if (!b) return null;
        const style: CSSProperties = { left: pct(b.x), top: pct(b.y), width: pct(b.w), height: pct(b.h) };
        return (
          <div key={r.key} className={`lgs-r${r.cls ? " " + r.cls : ""}`} role="group" aria-label={`${seat} ${r.name}: ${r.desc ?? (r.items.map((i) => i.text).join(", ") || "empty")}`} style={style}>
            <Items items={r.items} />
            {r.caption && (
              <span className="lgs-cap" title={r.caption} data-testid="lgs-building-effect">
                {r.caption}
              </span>
            )}
          </div>
        );
      })}
      {hot &&
        specs.map((r) => {
          const acts = hot.sections[r.key];
          const b = layout.regions[r.key];
          return acts && b ? <SectionHot key={r.key} id={r.key} name={r.name} acts={acts} box={b} hot={hot} /> : null;
        })}
    </div>
  );
}

/** Hired-worker meeple sprites: bearer green, woodcutter brown, sawyer white (joiner yellow, extension). */
export const WORKER_SPRITES = { b: "worker-bearer", w: "worker-woodcutter", s: "worker-sawyer" } as const;
const WORKER_NAMES = { b: "bearer", w: "woodcutter", s: "sawyer" } as const;

export function workerItems(hired: { b?: number; w?: number; s?: number }): Item[] {
  return (["b", "w", "s"] as const)
    .map((k) => ({ k, n: num(hired[k]) }))
    .filter((i) => i.n > 0)
    .map((i) => ({ sprite: WORKER_SPRITES[i.k], n: i.n, text: plural(i.n, WORKER_NAMES[i.k]) }));
}

function sawmillSpecs(s: LignumSeatView, v: LignumView, seat: number): RegionSpec[] {
  const kinds = arr(v.kind_names).map(str).filter(Boolean);
  const K = kinds.length === 3 ? kinds : KINDS;
  const equipSlots = arr(v.equip_slots).map(str);
  const eq = nums(s.equip);
  const craftOrder = arr(v.craft_order).map(str);
  const craft = nums(s.held_craft);
  const hired = s.hired ?? {};
  const huts = s.huts ?? {};
  const fod = nums(s.fodder);
  const food = num(s.food);
  const dry = arr(s.dry);
  const area = (i: number): RegionSpec => {
    const a = arr(dry[i]);
    const items = [...kindItems(a, K, "disk", UNMILLED), ...kindItems(a, K, "log", MILLED, 3)];
    return { key: `dry${i + 1}`, name: `drying area ${i + 1}`, items };
  };
  const named = (counts: number[], names: string[], fallback: string[], pre: string, noun: string): Item[] =>
    (names.length ? names : fallback).flatMap((n, i) => ((counts[i] ?? 0) > 0 ? [{ sprite: `${pre}${n}`, n: counts[i]!, text: `${counts[i]} ${n}${noun}` }] : []));
  return [
    { key: "river", name: "river", items: kindItems(s.river, K, "disk", UNMILLED) },
    { key: "sawing", name: "sawing", items: kindItems(s.sawing, K, "disk", UNMILLED) },
    {
      key: "sale",
      name: "sale area",
      items: [...kindItems(s.sale, K, "disk", UNMILLED), ...kindItems(s.sale_logs, K, "log", MILLED)],
    },
    area(0),
    area(1),
    area(2),
    { key: "store", name: "storage", items: kindItems(s.store, K, "log", MILLED) },
    {
      key: "equip",
      name: "equipment",
      items: (equipSlots.length ? equipSlots : EQUIP).flatMap((n, i) => ((eq[i] ?? 0) > 0 ? [{ sprite: `icon-${n}`, n: eq[i]!, text: `${eq[i]} ${n}` }] : [])),
    },
    { key: "craft", name: "held craftwork", items: named(craft, craftOrder, CRAFT, "craftwork-", "") },
    { key: "food", name: "food storage", items: food > 0 ? [{ sprite: "icon-food", n: food, text: `${food} food` }] : [] },
    {
      key: "hired",
      name: "hired workers",
      items: workerItems(hired),
      cls: "lgs-hired",
    },
    {
      key: "mill",
      name: "mill worker",
      items: [{ sprite: `mill-worker-${seat}`, n: 1, text: "mill worker", off: !!s.mill_used }],
      desc: s.mill_used ? "used, away from the worker area" : "in the worker area",
      cls: "lgs-mill",
    },
    {
      key: "huts",
      name: "huts",
      items: (["drying", "food", "worker"] as const).flatMap((k) => (num(huts[k]) > 0 ? [{ sprite: "icon-hut", n: num(huts[k]), text: `${num(huts[k])} ${k} hut${num(huts[k]) === 1 ? "" : "s"}` }] : [])),
    },
    {
      key: "fodder",
      name: "fodder slots",
      // Printed left to right as 2 then 3; fod[0] is the value-3 slot, fod[1] the value-2 slot.
      items: [[2, 1], [3, 0]].map(([val, i]) => ({ sprite: "icon-fodder", n: 1, text: `value ${val} ${fod[i!] ? "filled" : "empty"}`, off: !fod[i!] })),
      desc: [[3, 0], [2, 1]].map(([val, i]) => `value ${val} ${fod[i!] ? "filled" : "empty"}`).join(", "), // read-out order unchanged
    },
  ];
}

const NO_SLOT = -1;

function extensionSpecs(s: LignumSeatView, v: LignumView): RegionSpec[] {
  const K = arr(v.kind_names).map(str).filter(Boolean);
  const kinds = K.length === 3 ? K : KINDS;
  const slots = nums(s.joinery_wood);
  const joiners = num(s.joiners);
  const slotText = slots.map((k, i) => `slot ${i + 1} ${k === NO_SLOT || kinds[k] === undefined ? "empty" : kinds[k]}`);
  const ss = s.small_storage ?? { kind: null, spent: false };
  const names = arr(s.building_names).map(str);
  return [
    {
      key: "joinery",
      name: "joinery",
      items: [
        ...(joiners > 0 ? [{ sprite: "worker-joiner", n: joiners, text: plural(joiners, "joiner") }] : []),
        ...slots.flatMap((k) => (kinds[k] !== undefined ? [{ sprite: `piece-${kinds[k]}-log`, n: 1, text: kinds[k]! }] : [])),
      ],
      desc: `${plural(joiners, "joiner")}; joinery wood ${slotText.join(", ") || "none"}`,
    },
    {
      key: "buildings",
      name: "buildings",
      items: [],
      desc: names.join(", ") || "none",
    },
    ...[0, 1].map((i) => ({
      key: `building_slot_${i + 1}`,
      name: `building space ${i + 1}`,
      items: names[i] ? [{ sprite: cardSpriteId("building", names[i]!), n: 1, text: names[i]! }] : [],
      cls: "lgs-bslot",
      caption: names[i] ? buildingEffect(names[i]!) : undefined,
    })),
    {
      key: "small_storage",
      name: "small storage",
      items: ss.kind ? [{ sprite: `piece-${ss.kind}-log`, n: 1, text: ss.kind }] : [],
      desc: ss.spent ? "spent" : (ss.kind ?? "empty"),
    },
  ];
}

/** Money, loans, woodpile, held tasks and plans: no box of their own on the official pad, so shown as a ledger row. */
function Ledger({ s, v, seat }: { s: LignumSeatView; v: LignumView; seat: string }) {
  const { sprite } = useTheme();
  const loans = num(s.loans);
  const cards = arr(v.tasks?.cards) as NonNullable<NonNullable<LignumView["tasks"]>["cards"]>;
  const ids = nums(s.held_tasks);
  const held = ids.map((k, i) => {
    const c = cards.find((x) => x?.index === k);
    return { name: str(arr(s.held_task_ids)[i]) || `task ${k}`, reward: c?.reward, reqs: arr(c?.requirements) as { text?: string; filled?: boolean }[] };
  });
  const plans = arr(s.plans) as NonNullable<LignumSeatView["plans"]>;
  const loanSprite = (id: string, i: number) => {
    const sp = sprite(id);
    return sp ? <img key={i} src={sp.src} alt="" /> : <span key={i} className="lgs-chip">{id}</span>;
  };
  const group = (name: string, desc: string, kids: ReactNode) => (
    <div role="group" aria-label={`${seat} ${name}: ${desc}`}>
      <strong>{name}:</strong> {kids}
    </div>
  );
  return (
    <div className="lgs-ledger">
      {group("money", `$${num(s.money)}`, <span>${num(s.money)}</span>)}
      {group(
        "loans",
        String(loans),
        loans > 0 ? (
          <>
            {Array.from({ length: Math.floor(loans / 2) }, (_, i) => loanSprite("loan-back", i))}
            {loans % 2 === 1 && loanSprite("loan", -1)}
            <span>{loans}</span>
          </>
        ) : (
          <span>0</span>
        ),
      )}
      {group(
        "held tasks",
        held.map((h) => `${h.name}${h.reqs.length ? ` (${h.reqs.map((r) => `${str(r.text)} ${r.filled ? "filled" : "open"}`).join("; ")})` : ""}`).join(", ") || "none",
        held.length ? (
          held.map((h, i) => (
            <span key={i}>
              {h.name}
              {h.reward !== undefined && ` $${h.reward}`}{" "}
              {h.reqs.map((r, j) => (
                <span key={j} className={`lgs-chip${r.filled ? " lgs-done" : ""}`} title={str(r.text)}>
                  {str(r.text)} {r.filled ? "✓" : "✗"}
                </span>
              ))}
            </span>
          ))
        ) : (
          <span>none</span>
        ),
      )}
      {group(
        "planned work",
        plans.map((p) => `${str(p?.name)} (pair ${num(p?.pair)}, round ${num(p?.target)})`).join(", ") || "none",
        plans.length ? plans.map((p, i) => <span key={i} className="lgs-chip">{str(p?.name)} {num(p?.pair)}/{num(p?.target)}</span>) : <span>none</span>,
      )}
    </div>
  );
}

/** The seat's held wood (public, R-028), shown above the boards. */
function Woodpile({ s, v, seat }: { s: LignumSeatView; v: LignumView; seat: string }) {
  const K = arr(v.kind_names).map(str).filter(Boolean);
  const wp = kindItems(s.woodpile, K.length === 3 ? K : KINDS, "disk", UNMILLED);
  return (
    <div className="lgs-woodpile" role="group" aria-label={`${seat} woodpile: ${wp.map((i) => i.text).join(", ") || "empty"}`}>
      <strong>Woodpile</strong>
      {wp.length ? <Items items={wp} /> : <span className="lgs-empty">empty</span>}
    </div>
  );
}

/** Sawmill pad for any seat (public information, R-028) with a tab strip to switch seats. */
export default function Sawmill({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const v = (game.view ?? {}) as LignumView;
  const seats = arr(v.seats) as (LignumSeatView | null)[];
  const [pick, setPick] = useState<number | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  if (seats.length === 0) return null;
  const idx = pick !== null && pick < seats.length ? pick : Math.min(num(v.seat), seats.length - 1);
  const s: LignumSeatView = seats[idx] ?? {};
  const label = str(s.label) || `P${idx}`;
  const joinery = v.game?.joinery === true;
  const hot: Hot | undefined =
    ui?.canAct && ui.onAct && idx === v.seat
      ? {
          sections: sawmillSections(game.legal_actions ?? []),
          hover: ui.hoverAction,
          open,
          setOpen,
          onAct: (id) => {
            setOpen(null);
            void ui.onAct?.(id);
          },
        }
      : undefined;
  return (
    <section className="lgs" aria-label="Sawmill pads">
      <div className="lgs-tabs" role="group" aria-label="Choose seat">
        {seats.map((t, i) => {
          const l = str(t?.label) || `P${i}`;
          return (
            <button key={i} type="button" className="lgs-tab" aria-pressed={i === idx} aria-label={`Show ${l} sawmill`} onClick={() => setPick(i)}>
              {l} ${num(t?.money)}
              {i === v.seat ? " (you)" : ""}
            </button>
          );
        })}
      </div>
      <Woodpile s={s} v={v} seat={label} />
      <div className="lgs-pads" role="group" aria-label={`${label} sawmill`} style={{ ["--lgs-sum" as string]: PADS.sawmill.width / PADS.sawmill.height + (joinery ? PADS.extension.width / PADS.extension.height : 0) }}>
        <Pad pad="sawmill" spriteId="sawmill" altId="sawmill-plain" seat={label} specs={sawmillSpecs(s, v, idx)} hot={hot} />
        {joinery && <Pad pad="extension" spriteId="player-extension" seat={label} specs={extensionSpecs(s, v)} cls="lgs-ext" hot={hot} />}
      </div>
      <Ledger s={s} v={v} seat={label} />
    </section>
  );
}
