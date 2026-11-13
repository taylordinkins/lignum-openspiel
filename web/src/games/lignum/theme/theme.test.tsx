import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from "./ThemeProvider";
import { defaultTheme, indexManifest, resolveSprite } from "./resolve";
import type { LoadedManifests, ThemeManifest } from "./types";

const entry = (id: string, file: string) => ({ id, category: "tiles", alt: id, file });
const official: ThemeManifest = { assets: [entry("board", "boards/board.webp"), entry("gone", "x/gone.webp")] };
const generic: ThemeManifest = { assets: [entry("board", "board.svg"), entry("fallback", "fb.svg")] };
const urls = (m: ThemeManifest, p: string) => Object.fromEntries(m.assets.map((a) => [a.file, p + a.file]));

const both: LoadedManifests = {
  // "gone" has no file on disk, so it must be dropped and fall back.
  official: indexManifest("official", official, { "boards/board.webp": "/o/board.webp" }),
  generic: indexManifest("generic", generic, urls(generic, "/g/")),
};

describe("resolveSprite", () => {
  it("official hit", () => {
    expect(resolveSprite("official", "board", both)).toMatchObject({ src: "/o/board.webp", theme: "official" });
  });
  it("official miss falls back to generic", () => {
    expect(resolveSprite("official", "fallback", both)).toMatchObject({ src: "/g/fb.svg", theme: "generic" });
    expect(resolveSprite("official", "gone", both)).toBeUndefined();
  });
  it("both miss -> undefined", () => {
    expect(resolveSprite("official", "nope", both)).toBeUndefined();
  });
  it("official manifest absent -> generic only", () => {
    const m: LoadedManifests = { official: indexManifest("official", undefined, {}), generic: both.generic };
    expect(resolveSprite("official", "board", m)?.theme).toBe("generic");
    expect(defaultTheme(m)).toBe("generic");
    expect(defaultTheme(both)).toBe("generic");
    expect(defaultTheme({ official: both.official })).toBe("official");
  });
  it("unknown theme id uses generic", () => {
    expect(resolveSprite("sepia", "board", both)?.theme).toBe("generic");
    expect(resolveSprite("sepia", "board", {})).toBeUndefined();
  });
});

describe("useTheme", () => {
  it("defaults to generic when official is absent and resolves through context", () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider manifests={{ generic: both.generic }}>{children}</ThemeProvider>
    );
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.themeId).toBe("generic");
    expect(result.current.sprite("fallback")?.src).toBe("/g/fb.svg");
  });
});

describe("theme choice persistence", () => {
  const wrapper = ({ children }: { children: ReactNode }) => <ThemeProvider manifests={both}>{children}</ThemeProvider>;
  afterEach(() => window.localStorage.clear());

  it("defaults to generic and remembers a switch", () => {
    const { result, unmount } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.themeId).toBe("generic");
    act(() => result.current.setThemeId("official"));
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("official");
    unmount();
    expect(renderHook(() => useTheme(), { wrapper }).result.current.themeId).toBe("official");
  });

  it("ignores a stored theme that is not loaded, and survives blocked storage", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "official");
    const only = ({ children }: { children: ReactNode }) => <ThemeProvider manifests={{ generic: both.generic }}>{children}</ThemeProvider>;
    expect(renderHook(() => useTheme(), { wrapper: only }).result.current.themeId).toBe("generic");
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const setSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.themeId).toBe("generic");
    act(() => result.current.setThemeId("official"));
    expect(result.current.themeId).toBe("official");
    spy.mockRestore();
    setSpy.mockRestore();
  });
});
