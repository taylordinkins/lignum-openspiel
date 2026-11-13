import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { loadManifests } from "./loadManifests";
import { defaultTheme, resolveSprite } from "./resolve";
import type { LoadedManifests, ResolvedSprite, ThemeId } from "./types";

export interface ThemeValue {
  themeId: ThemeId;
  setThemeId: (id: ThemeId) => void;
  /** Themes whose manifests loaded. */
  available: ThemeId[];
  sprite: (spriteId: string) => ResolvedSprite | undefined;
}

export const THEME_STORAGE_KEY = "lignum.theme";

/** Stored per-viewer choice if it names a loaded theme (storage may be blocked, hence try/catch). */
function storedTheme(loaded: LoadedManifests): ThemeId | undefined {
  try {
    const v = window.localStorage.getItem(THEME_STORAGE_KEY);
    if ((v === "official" || v === "generic") && loaded[v]) return v;
  } catch {
    /* storage unavailable */
  }
  return undefined;
}

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({
  children,
  manifests,
  initialTheme,
}: {
  children: ReactNode;
  manifests?: LoadedManifests;
  /** Theme to start on when no stored choice applies (falls back to the default if not loaded). */
  initialTheme?: ThemeId;
}) {
  const loaded = useMemo(() => manifests ?? loadManifests(), [manifests]);
  const [themeId, setTheme] = useState<ThemeId>(
    () => storedTheme(loaded) ?? (initialTheme && loaded[initialTheme] ? initialTheme : defaultTheme(loaded)),
  );
  const setThemeId = useCallback((id: ThemeId) => {
    setTheme(id);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, id);
    } catch {
      /* storage unavailable: the choice lasts for this session only */
    }
  }, []);
  const value = useMemo<ThemeValue>(
    () => ({
      themeId,
      setThemeId,
      available: (Object.keys(loaded) as ThemeId[]).filter((k) => loaded[k]),
      sprite: (id) => resolveSprite(themeId, id, loaded),
    }),
    [themeId, loaded, setThemeId],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const v = useContext(ThemeContext);
  if (!v) throw new Error("useTheme must be used inside <ThemeProvider>");
  return v;
}
