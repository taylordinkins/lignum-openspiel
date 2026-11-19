import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { resetSettingsCache, SETTINGS_KEY } from "./shell/settings";

// Tests run with no bot pacing (immediate); tests of the pacing logic set their own settings.
beforeEach(() => {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ botPace: 0 }));
  } catch {
    // no storage in this environment
  }
  resetSettingsCache();
});
