/** Seat-filtered Lignum view (server/adapters/lignum.py). Every key is optional: parse defensively. */
export type LignumCounts3 = [number, number, number];

export interface LignumPathLocation {
  number: number;
  kind: string;
  name: string;
  capacity: number;
  /** Seats whose foreman stands here. */
  foremen: number[];
  /** Pieces on offer: a count (bearers, woodcutters, fodder, joiner), {free, paid} (sawyers), else null. */
  pool?: number | { free: number; paid: number } | null;
  /** Token lying on a token spot (null elsewhere). */
  token?: { spot: number; kind: string | null; taken: boolean } | null;
}

export interface LignumSeatView {
  label?: string;
  money?: number;
  loans?: number;
  joiners?: number;
  food?: number;
  hired?: { b?: number; w?: number; s?: number };
  /** True while the mill worker is away from the worker area (used this round). */
  mill_used?: boolean;
  cut_used?: number;
  woodpile?: number[];
  river?: number[];
  sawing?: number[];
  sale?: number[];
  sale_logs?: number[];
  store?: number[];
  /** Drying areas 1..3, each a per-piece count list. */
  dry?: number[][];
  joinery_wood?: number[];
  equip?: number[];
  /** Craftwork counts in craft_order (joker last). */
  held_craft?: number[];
  held_tasks?: number[];
  held_task_ids?: string[];
  fodder?: number[];
  buildings?: number[];
  building_names?: string[];
  small_storage?: { kind: string | null; spent: boolean };
  huts?: { drying?: number; food?: number; worker?: number };
  plans?: { card: number; name: string; pair: number; target: number }[];
  plans_left?: number;
}

export interface LignumTaskCard {
  index: number;
  id: string;
  reward: number;
  requirements: {
    kind?: string;
    milled?: boolean;
    drying?: number;
    text: string;
    filled: boolean;
  }[];
}

export interface LignumWinterCard {
  year?: number;
  /** Sprite id, winter-<year>-<card>. */
  id?: string;
  food?: number;
  heating?: number;
}

/** Components of one seat's final dollars: money + wood_sale + river_sale + joinery_sale + office + tasks + loan_repay = final. */
export interface LignumSeatScore {
  /** Money held before the final sale (remainder; includes cash from final-sale loans). */
  money?: number;
  /** Sale and drying areas, R-081 step 1. */
  wood_sale?: number;
  /** One river kind, R-081 step 2. */
  river_sale?: number;
  /** Covered joinery pieces, R-082. */
  joinery_sale?: number;
  /** Office building, R-116. */
  office?: number;
  /** Completed task rewards, R-081 step 4. */
  tasks?: number;
  tasks_done?: string[];
  loans?: number;
  /** Negative or zero, R-083. */
  loan_repay?: number;
  final?: number;
}

export interface LignumView {
  equip_slots?: string[];
  kind_names?: string[];
  craft_order?: string[];
  seat?: number;
  private?: { pick?: number | null };
  game?: { players?: number; joinery?: boolean };
  /** Repayment by number of loans held (R-077). */
  loan_repayment?: number[];
  round?: number;
  phase?: string;
  phase_label?: string;
  is_terminal?: boolean;
  chance?: boolean;
  current_player?: number | null;
  picks?: unknown[];
  picked?: number[];
  high_areas?: number[];
  area_wood?: unknown[];
  area_food?: unknown[];
  turn_order?: unknown[];
  clearing?: unknown[];
  foreman?: unknown[];
  seats?: LignumSeatView[];
  placement?: { discarded?: number[]; discarded_ids?: string[] };
  path?: {
    boys?: number;
    women?: number;
    sf?: number;
    sp?: number;
    fodder?: number;
    joiner?: number;
    locations?: LignumPathLocation[];
    /** Seat in each clearing slot A..D, null if empty. */
    clearing_slots?: (number | null)[];
    tokens?: { spot: number; location: number; kind: string | null; taken: boolean }[];
  };
  tasks?: {
    row?: unknown[];
    row_ids?: string[];
    filled?: unknown[];
    filled_ids?: string[];
    cards?: LignumTaskCard[];
  };
  fodder_values?: number[];
  pw?: {
    row?: number[];
    names?: string[];
    cards?: { index: number; name: string; seasons: number[] }[];
  };
  buildings?: { supply?: number[]; names?: string[] };
  huts?: {
    built?: number;
    spent?: number;
    open?: { tokens: string[]; areas: string[] } | null;
  };
  craft?: { pile?: number[]; removed?: number[] };
  winter?: { order?: unknown[]; pay?: unknown; sf_due?: unknown; cards?: LignumWinterCard[]; card_ids?: string[] };
  log?: { round: number; picks: unknown[] }[];
  returns?: number[] | null;
  final?: number[] | null;
  winners?: number[] | null;
  /** Per-seat final-dollar components, terminal only (R-081..R-083). */
  score?: LignumSeatScore[] | null;
}

/** Phase name in which seats make hidden cutting-area picks. */
export const PICK_PHASE = "PK";
