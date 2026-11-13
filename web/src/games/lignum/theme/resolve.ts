import type { LoadedManifests, ResolvedSprite, SpriteEntry, ThemeManifest, ThemeId } from "./types";

export const FALLBACK_THEME: ThemeId = "generic";

/** Selected theme -> generic -> undefined. An unknown theme id behaves like a missing theme. */
export function resolveSprite(
  themeId: string,
  spriteId: string,
  manifests: LoadedManifests,
): ResolvedSprite | undefined {
  const own = (manifests as Record<string, Record<string, ResolvedSprite> | undefined>)[themeId];
  return own?.[spriteId] ?? manifests[FALLBACK_THEME]?.[spriteId];
}

/** Index a manifest by sprite id, attaching URLs from `urls` (keyed by `file`). Entries without a file are dropped. */
export function indexManifest(
  theme: ThemeId,
  manifest: ThemeManifest | undefined,
  urls: Record<string, string>,
): Record<string, ResolvedSprite> | undefined {
  if (!manifest || !Array.isArray(manifest.assets)) return undefined;
  const out: Record<string, ResolvedSprite> = {};
  for (const e of manifest.assets as SpriteEntry[]) {
    const src = urls[e.file];
    if (src !== undefined) out[e.id] = { ...e, src, theme };
  }
  return out;
}

/** Generic is the default; official is chosen only when it is the sole loaded theme. */
export function defaultTheme(manifests: LoadedManifests): ThemeId {
  return manifests.generic || !manifests.official ? "generic" : "official";
}
