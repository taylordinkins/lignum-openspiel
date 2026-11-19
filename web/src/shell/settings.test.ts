import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BOT_PACE_DEFAULT,
  SETTINGS_KEY,
  clampPace,
  defaultSettings,
  getSettings,
  loadSettings,
  parseSettings,
  resetSettingsCache,
  updateSettings,
} from "./settings";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  resetSettingsCache();
});

describe("settings", () => {
  it("defaults to a 0.8 s bot pace", () => {
    expect(defaultSettings()).toEqual({ botPace: BOT_PACE_DEFAULT });
    expect(BOT_PACE_DEFAULT).toBe(0.8);
    window.localStorage.removeItem(SETTINGS_KEY);
    expect(loadSettings()).toEqual({ botPace: 0.8 });
  });

  it("persists updates to localStorage and notifies readers", () => {
    window.localStorage.removeItem(SETTINGS_KEY);
    resetSettingsCache();
    updateSettings({ botPace: 1.2 });
    expect(JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "{}")).toEqual({ botPace: 1.2 });
    resetSettingsCache();
    expect(getSettings()).toEqual({ botPace: 1.2 });
  });

  it("clamps the pace to 0..2 s in 0.1 s steps; bad values fall back", () => {
    expect(clampPace(-1)).toBe(0);
    expect(clampPace(9)).toBe(2);
    expect(clampPace(0.84)).toBe(0.8);
    expect(clampPace("x")).toBe(0.8);
    expect(parseSettings(null)).toEqual(defaultSettings());
    window.localStorage.setItem(SETTINGS_KEY, "{not json");
    expect(loadSettings()).toEqual(defaultSettings());
  });

  it("survives a storage that throws (private mode, quota)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    resetSettingsCache();
    expect(getSettings()).toEqual(defaultSettings());
    expect(updateSettings({ botPace: 0 }).botPace).toBe(0);
    expect(getSettings().botPace).toBe(0);
  });
});
