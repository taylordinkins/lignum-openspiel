export type ThemeId = "official" | "generic";

/** One sprite as written in a theme's manifest.json (extra fields are ignored). */
export interface SpriteEntry {
  id: string;
  category: string;
  alt: string;
  /** Path relative to the theme directory. */
  file: string;
  width?: number;
  height?: number;
}

export interface ThemeManifest {
  assets: SpriteEntry[];
}

/** A manifest entry plus the URL the bundler serves its file from. */
export interface ResolvedSprite extends SpriteEntry {
  src: string;
  /** Theme that actually supplied the sprite (differs from the selection on fallback). */
  theme: ThemeId;
}

/** Loaded themes; a theme is absent when its manifest is missing (scrubbed clone). */
export type LoadedManifests = Partial<Record<ThemeId, Record<string, ResolvedSprite>>>;
