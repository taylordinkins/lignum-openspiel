import type { ReactNode } from "react";
import type { GameView } from "../../shell/useGame";
import type { BoardUi } from "../registry";
import CutAllPanel from "./CutAllPanel";
import { PICK_PHASE, type LignumSeatView, type LignumView } from "./types";

/** Render any loosely typed value as plain text (never JSON). */
export function fmt(x: unknown): string {
  if (x === null || x === undefined) return "-";
  if (typeof x === "number" || typeof x === "string") return String(x);
  if (typeof x === "boolean") return x ? "yes" : "no";
  if (Array.isArray(x)) return x.length === 0 ? "-" : x.map(fmt).join(", ");
  if (typeof x === "object")
    return Object.entries(x as Record<string, unknown>)
      .map(([k, v]) => `${k} ${fmt(v)}`)
      .join("; ");
  return "-";
}

const seatName = (x: unknown): string =>
  typeof x === "number" ? `P${x}` : fmt(x);
const seatList = (xs: unknown): string =>
  Array.isArray(xs) && xs.length > 0 ? xs.map(seatName).join(", ") : "-";
const dollars = (n: number): string => (n < 0 ? `-$${-n}` : `$${n}`);
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);

function flat(x: unknown): number[] {
  if (typeof x === "number") return x >= 0 ? [x] : [];
  if (Array.isArray(x)) return x.flatMap(flat);
  return [];
}

function Dl({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="lg-dl">
      {rows.map(([k, v]) => (
        <div key={k} className="lg-dl-row">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Header({ v }: { v: LignumView }) {
  const mover =
    typeof v.current_player === "number" ? `P${v.current_player}` : "-";
  return (
    <section aria-label="Overview">
      <h3>Round {fmt(v.round)}</h3>
      <Dl
        rows={[
          ["Phase", fmt(v.phase_label ?? v.phase)],
          [
            "To move",
            v.is_terminal ? "game over" : v.chance ? "chance" : mover,
          ],
          [
            "High-wood areas",
            arr(v.high_areas)
              .map((a) => (typeof a === "number" ? a + 1 : fmt(a)))
              .join(", ") || "-",
          ],
          ["Turn order", seatList(v.turn_order)],
          ["Clearing order", seatList(v.clearing)],
          [
            "Foreman",
            arr(v.foreman)
              .map((f, i) => `P${i} ${fmt(f)}`)
              .join(", ") || "-",
          ],
        ]}
      />
    </section>
  );
}

function Areas({ v }: { v: LignumView }) {
  const picks = arr(v.picks);
  const wood = arr(v.area_wood);
  const food = arr(v.area_food);
  const high = arr(v.high_areas);
  const viewer = v.seat;
  const own = v.private?.pick;
  const picked = arr(v.picked).filter(
    (s): s is number => typeof s === "number",
  );
  const others = picked.filter((s) => s !== viewer);
  return (
    <section aria-label="Cutting areas">
      <h3>Cutting areas</h3>
      <table className="lg-table">
        <thead>
          <tr>
            <th>Area</th>
            <th>Wood</th>
            <th>Food</th>
            <th>Revealed picks</th>
          </tr>
        </thead>
        <tbody>
          {[0, 1, 2, 3, 4, 5].map((a) => {
            const by = picks.flatMap((p, seat) =>
              flat(p).includes(a) ? [`P${seat}`] : [],
            );
            return (
              <tr key={a}>
                <th scope="row">
                  {a + 1}
                  {high.includes(a) ? " (high)" : ""}
                </th>
                <td>{fmt(wood[a])}</td>
                <td>{fmt(food[a])}</td>
                <td>{by.join(", ") || "-"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {typeof own === "number" && <p>Your hidden pick: area {own + 1}</p>}
      {v.phase === PICK_PHASE && (
        <p>
          {others.length > 0
            ? others.map((s) => `P${s} has picked`).join("; ")
            : "No other seat has picked yet"}
        </p>
      )}
    </section>
  );
}

/** "name n" pairs from a count list and its engine-supplied names; falls back to bare numbers. */
function labelled(
  counts: unknown,
  names: string[] | undefined,
  opts: { plural?: boolean; zeros?: boolean } = {},
): string {
  if (!Array.isArray(counts) || !names || names.length !== counts.length)
    return fmt(counts);
  const parts = names
    .map((n, i) => [n, counts[i]] as const)
    .filter(([, c]) => opts.zeros || c !== 0)
    .map(([n, c]) => `${opts.plural ? n + "s" : n} ${fmt(c)}`);
  return parts.length === 0 ? "-" : parts.join(", ");
}

const SEAT_COLS: [string, (s: LignumSeatView, v: LignumView) => string][] = [
  ["Money", (s) => (typeof s.money === "number" ? dollars(s.money) : "-")],
  ["Loans", (s) => fmt(s.loans)],
  ["Joiners", (s) => fmt(s.joiners)],
  ["Food", (s) => fmt(s.food)],
  [
    "Hired b/w/s",
    (s) =>
      `${fmt(s.hired?.b ?? 0)}/${fmt(s.hired?.w ?? 0)}/${fmt(s.hired?.s ?? 0)}`,
  ],
  ["Woodpile", (s, v) => labelled(s.woodpile, v.kind_names)],
  ["River", (s, v) => labelled(s.river, v.kind_names)],
  ["Sawing", (s, v) => labelled(s.sawing, v.kind_names)],
  ["Sale area (log)", (s, v) => labelled(s.sale, v.kind_names)],
  ["Sale area (milled)", (s, v) => labelled(s.sale_logs, v.kind_names)],
  ["Drying", (s) => fmt(s.dry)],
  ["Storage", (s, v) => labelled(s.store, v.kind_names)],
  ["Joinery wood", (s) => fmt(s.joinery_wood)],
  [
    "Equipment",
    (s, v) => labelled(s.equip, v.equip_slots, { plural: true, zeros: true }),
  ],
  ["Held craft", (s, v) => labelled(s.held_craft, v.craft_order)],
  ["Held tasks", (s) => fmt(s.held_task_ids)],
  ["Fodder slots (3, 2)", (s) => fmt(s.fodder)],
  ["Buildings", (s) => fmt(s.building_names)],
  [
    "Small Storage Area",
    (s) =>
      s.small_storage
        ? (s.small_storage.kind ?? (s.small_storage.spent ? "spent" : "-"))
        : "-",
  ],
  [
    "Huts (drying/food/worker)",
    (s) =>
      `${fmt(s.huts?.drying ?? 0)}/${fmt(s.huts?.food ?? 0)}/${fmt(s.huts?.worker ?? 0)}`,
  ],
  [
    "Planned work",
    (s) =>
      (s.plans ?? [])
        .map((p) => `${p.name} (pair ${p.pair}, round ${p.target})`)
        .join("; ") || "-",
  ],
];

function Seats({ v }: { v: LignumView }) {
  const seats = arr(v.seats) as LignumSeatView[];
  return (
    <section aria-label="Seats">
      <h3>Seats</h3>
      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr>
              <th />
              {seats.map((_, i) => (
                <th key={i} scope="col">
                  P{i}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SEAT_COLS.map(([name, f]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                {seats.map((s, i) => (
                  <td key={i}>{f(s ?? {}, v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Track({ v }: { v: LignumView }) {
  const p = v.path ?? {};
  return (
    <section aria-label="Path">
      <h3>Path and supply</h3>
      <Dl
        rows={[
          ["Bearers", fmt(p.boys)],
          ["Woodcutters", fmt(p.women)],
          ["Sawyers ($0)", fmt(p.sf)],
          ["Sawyers ($1)", fmt(p.sp)],
          ["Fodder", fmt(p.fodder)],
          ["Joiner", fmt(p.joiner)],
        ]}
      />
      <h4>Token spots</h4>
      <ul aria-label="Token spots">
        {(p.tokens ?? []).map((t) => (
          <li key={t.spot}>
            Spot {t.spot} (Location {t.location}): {t.taken ? "taken" : t.kind}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Tasks({ v }: { v: LignumView }) {
  const t = v.tasks ?? {};
  const w = v.winter ?? {};
  return (
    <>
      <section aria-label="Task cards">
        <h3>Task cards</h3>
        <Dl
          rows={[
            ["Row", fmt(t.row_ids)],
            ["Filled", fmt(t.filled_ids)],
            ...(t.cards ?? []).map((c): [string, string] => [
              c.id,
              `$${c.reward}: ` +
                c.requirements
                  .map((r) => r.text + (r.filled ? " (filled)" : ""))
                  .join("; "),
            ]),
          ]}
        />
      </section>
      <section aria-label="Planned work and buildings">
        <h3>Planned work and buildings</h3>
        <Dl
          rows={[
            ["Planned work cards", fmt(v.pw?.names)],
            ["Building supply", fmt(v.buildings?.names)],
            [
              "Huts built / spent",
              `${fmt(v.huts?.built ?? 0)} / ${fmt(v.huts?.spent ?? 0)}`,
            ],
          ]}
        />
      </section>
      <section aria-label="Winter">
        <h3>Winter</h3>
        <Dl
          rows={[
            ["Order", seatList(w.order)],
            ["Pay", fmt(w.pay)],
            ["Shortfall money due", fmt(w.sf_due)],
            ...arr(w.cards).map((c): [string, string] => {
              const card = c as {
                year?: number;
                food?: number;
                heating?: number;
              };
              return [
                `Winter ${fmt(card.year)}`,
                `food ${fmt(card.food)}, heating ${fmt(card.heating)}`,
              ];
            }),
          ]}
        />
      </section>
    </>
  );
}

function Result({ v }: { v: LignumView }) {
  if (!v.is_terminal) return null;
  const final = arr(v.final) as number[];
  const winners = arr(v.winners);
  return (
    <section aria-label="Result">
      <h3>Final result</h3>
      <Dl
        rows={[
          [
            "Final dollars",
            final.map((d, i) => `P${i} ${dollars(d)}`).join(", ") || "-",
          ],
          ["Winners", seatList(winners)],
        ]}
      />
    </section>
  );
}

export default function TextBoard({ game, ui }: { game: GameView; ui?: BoardUi }) {
  const v = game.view as LignumView;
  return (
    <div className="lg-textboard" aria-label="Game state">
      <Header v={v} />
      <Result v={v} />
      <CutAllPanel game={game} ui={ui} />
      <Areas v={v} />
      <Seats v={v} />
      <Track v={v} />
      <Tasks v={v} />
    </div>
  );
}
