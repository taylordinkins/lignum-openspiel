import data from "../cardData.json";
import type { CardKind } from "./spriteIds";

/** Text a card shows in the viewer; every value comes from data/components via cardData.json. */
export interface CardInfo {
  title: string;
  lines: string[];
}

interface Rec {
  id: string;
  name?: string;
  reward?: number;
  requirements?: { kind: string; milled: boolean; drying: number }[];
  areas?: Record<string, string[]>;
  food_areas?: number[];
  year?: number;
  halves?: Record<string, { food: number; heating: number }>;
  seasons?: string[];
  params?: Record<string, number | Record<string, number>>;
}
const D = data as unknown as Record<string, Rec[]>;

const norm = (s: string): string => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
const cap = (s: string): string => (s ? s[0]!.toUpperCase() + s.slice(1) : s);
const words = (s: string): string => cap(s.replace(/_/g, " "));

function find(list: string, id: string, prefix = ""): Rec | undefined {
  const n = norm(id);
  return D[list]?.find((r) => r.id === n || r.id === prefix + n || (r.name !== undefined && norm(r.name) === n));
}

function paramText(v: number | Record<string, number>): string {
  return typeof v === "number" ? String(v) : Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(", ");
}

/** Readable description of a card, or undefined when the data has no entry for it. */
export function cardInfo(kind: CardKind, id: string): CardInfo | undefined {
  if (kind === "task") {
    const r = find("tasks", id);
    if (!r) return undefined;
    return {
      title: `Task ${r.id.replace("task_", "")}`,
      lines: [
        `Reward: $${r.reward}`,
        ...(r.requirements ?? []).map((q) => `${cap(q.kind)}, ${q.milled ? "milled" : "unmilled (log)"}, drying stage ${q.drying}`),
      ],
    };
  }
  if (kind === "placement") {
    const r = find("placement", id);
    if (!r) return undefined;
    return {
      title: `Placement card ${r.id.replace("placement_", "")}`,
      lines: [
        ...Object.entries(r.areas ?? {}).map(([a, w]) => `Cutting area ${a}: ${w.join(", ")}`),
        `1 food in cutting areas ${(r.food_areas ?? []).join(" and ")}`,
      ],
    };
  }
  if (kind === "winter") {
    const r = find("winter", id);
    if (!r) return undefined;
    return {
      title: `Winter card, year ${r.year}`,
      lines: Object.entries(r.halves ?? {}).map(([h, c]) => `${cap(h)} half: food ${c.food}, heating ${c.heating}`),
    };
  }
  if (kind === "pw") {
    const r = find("planned_work", id, "pw_");
    if (!r) return undefined;
    return {
      title: `Planned work: ${r.name}`,
      lines: [`Seasons: ${(r.seasons ?? []).map(cap).join(", ")}`, ...Object.entries(r.params ?? {}).map(([k, v]) => `${words(k)}: ${paramText(v)}`)],
    };
  }
  if (kind === "building") {
    const r = find("buildings", id);
    if (!r) return undefined;
    return { title: `Building: ${r.name}`, lines: Object.entries(r.params ?? {}).map(([k, v]) => `${words(k)}: ${paramText(v)}`) };
  }
  return undefined;
}

/** One-line effect text of a building, from the data params (empty when the data has none). */
export function buildingEffect(id: string): string {
  const r = find("buildings", id);
  return r ? Object.entries(r.params ?? {}).map(([k, v]) => `${words(k)}: ${paramText(v)}`).join("; ") : "";
}
