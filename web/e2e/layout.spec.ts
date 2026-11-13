import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

// The official theme needs a local third_party/art and VITE_LIGNUM_OFFICIAL_THEME=1.
const ART = join(process.cwd(), "..", "third_party", "art", "manifest.json");
const OFFICIAL = existsSync(ART) && process.env.VITE_LIGNUM_OFFICIAL_THEME === "1";
const OUT = process.env.LIGNUM_SHOT_DIR ?? "";

async function start(page: Page, players: number) {
  // Generic is the default theme; pick official before the app reads the stored choice.
  await page.addInitScript(() => window.localStorage.setItem("lignum.theme", "official"));
  await page.goto("/");
  await page.getByLabel("Players").selectOption(String(players));
  await page.getByLabel("Seat P0").selectOption("human");
  for (let i = 1; i < players; i++) await page.getByLabel(`Seat P${i}`).selectOption("random");
  await page.getByLabel("Joinery and Buildings expansion").check();
  await page.getByLabel("Seed (optional)").fill("1");
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
  await expect(page.getByRole("group", { name: "Game board" })).toBeVisible();
  await page.waitForTimeout(800);
}

const cases: [string, number, number, number][] = [
  ["2p_1366x660", 2, 1366, 660],
  ["2p_1440x800", 2, 1440, 800],
  ["4p_1366x660", 4, 1366, 660],
];

for (const [name, players, w, h] of cases) {
  test(`fits the viewport without page scroll: ${name}`, async ({ page }) => {
    test.skip(!OFFICIAL, "official theme not enabled (needs third_party/art and VITE_LIGNUM_OFFICIAL_THEME=1)");
    await page.setViewportSize({ width: w, height: h });
    await start(page, players);
    const dims = await page.evaluate(() => ({
      sh: document.documentElement.scrollHeight,
      sw: document.documentElement.scrollWidth,
    }));
    if (OUT) {
      mkdirSync(OUT, { recursive: true });
      await page.screenshot({ path: join(OUT, `ui_9a_${name}.png`) });
    }
    expect(dims.sh, "document scroll height").toBeLessThanOrEqual(h);
    expect(dims.sw, "document scroll width").toBeLessThanOrEqual(w);
    for (const view of ["Sawmills", "Cards", "Details"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      const d = await page.evaluate(() => ({ sh: document.documentElement.scrollHeight, sw: document.documentElement.scrollWidth }));
      if (OUT) await page.screenshot({ path: join(OUT, `ui_9a_${name}_${view.toLowerCase()}.png`) });
      expect(d.sh, `${view}: document scroll height`).toBeLessThanOrEqual(h);
      expect(d.sw, `${view}: document scroll width`).toBeLessThanOrEqual(w);
    }
  });
}
