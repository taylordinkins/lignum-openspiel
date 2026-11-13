import raw from "./sawmillLayout.json";

/** Sawmill / player-extension region boxes as fractions (0..1) of their image; x/y are the box centre. */
export interface PadBox {
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface PadLayout {
  width: number;
  height: number;
  regions: Record<string, PadBox>;
}
type RawPad = { width: number; height: number; regions: Record<string, PadBox> };

function norm(r: RawPad): PadLayout {
  const regions: Record<string, PadBox> = {};
  for (const [k, b] of Object.entries(r.regions))
    regions[k] = { label: b.label, x: b.x / r.width, y: b.y / r.height, w: b.w / r.width, h: b.h / r.height };
  return { width: r.width, height: r.height, regions };
}

export const PADS = { sawmill: norm(raw.sawmill as RawPad), extension: norm(raw.extension as RawPad) };
/** Evenly gridded boxes for the generic theme's drawn pads (same keys; the official photos keep PADS). */
export const GENERIC_PADS = { sawmill: norm(raw.sawmill_generic as RawPad), extension: norm(raw.extension_generic as RawPad) };
