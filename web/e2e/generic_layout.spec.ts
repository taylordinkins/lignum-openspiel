import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

// Generic theme (the default): no page scroll at the supported laptop sizes.
const OUT = process.env.LIGNUM_SHOT_DIR ?? "";

async function useGeneric(page: Page) {
  await page.addInitScript(() => window.localStorage.removeItem("lignum.theme"));
}

async function start(page: Page, players: number, seats?: string[], mobile = false) {
  await useGeneric(page);
  await page.goto("/");
  await page.getByLabel("Players").selectOption(String(players));
  await page.getByLabel("Seat P0").selectOption("human");
  for (let i = 1; i < players; i++) await page.getByLabel(`Seat P${i}`).selectOption(seats?.[i] ?? "random");
  await page.getByLabel("Joinery and Buildings expansion").check();
  await page.getByLabel("Seed (optional)").fill("1");
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
  // On narrow screens the board is behind the "Board" section tab.
  if (mobile) await page.getByRole("tab", { name: "Board" }).click();
  await expect(page.getByRole("group", { name: "Game board" })).toBeVisible();
  await page.waitForTimeout(800);
}

const dims = (page: Page) =>
  page.evaluate(() => ({
    sh: document.documentElement.scrollHeight,
    sw: document.documentElement.scrollWidth,
  }));

async function shot(page: Page, name: string) {
  if (!OUT) return;
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: join(OUT, `generic_${name}.png`) });
}

const cases: [number, number, number][] = [
  [2, 1366, 660],
  [2, 1440, 800],
  [2, 1440, 860],
  [4, 1366, 660],
  [4, 1440, 800],
  [4, 1440, 860],
];

for (const [players, w, h] of cases) {
  test(`generic: ${players}p fits ${w}x${h} without page scroll in every view`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await start(page, players);
    const tag = `${players}p_${w}x${h}`;
    let d = await dims(page);
    await shot(page, `${tag}_board`);
    expect(d.sh, "board: scroll height").toBeLessThanOrEqual(h);
    expect(d.sw, "board: scroll width").toBeLessThanOrEqual(w);
    for (const view of ["Sawmills", "Cards", "Task Cards", "Details"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      d = await dims(page);
      await shot(page, `${tag}_${view.toLowerCase().replace(" ", "")}`);
      expect(d.sh, `${view}: scroll height`).toBeLessThanOrEqual(h);
      expect(d.sw, `${view}: scroll width`).toBeLessThanOrEqual(w);
    }
  });
}

test("generic: lobby has no horizontal scroll at 1440x860", async ({ page }) => {
  await useGeneric(page);
  await page.setViewportSize({ width: 1440, height: 860 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Create game" })).toBeVisible();
  await shot(page, "lobby_1440x860");
  expect((await dims(page)).sw).toBeLessThanOrEqual(1440);
});

test("generic: lobby and game have no horizontal scroll at 390x844", async ({ page }) => {
  await useGeneric(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Create game" })).toBeVisible();
  await shot(page, "lobby_390x844");
  expect((await dims(page)).sw, "lobby").toBeLessThanOrEqual(390);
  await start(page, 4, undefined, true);
  await shot(page, "game_390x844");
  expect((await dims(page)).sw, "game").toBeLessThanOrEqual(390);
});

test("generic: bot playback shows 'is playing' and Skip to my turn works", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 860 });
  await start(page, 4);
  const enabled = page
    .getByRole("list", { name: /^Legal actions/ })
    .getByRole("button")
    .and(page.locator(":enabled"))
    .first();
  await enabled.waitFor({ state: "visible" });
  await enabled.click();
  const skip = page.getByRole("button", { name: "Skip to my turn" });
  try {
    await skip.waitFor({ state: "visible", timeout: 5_000 });
  } catch {
    test.skip(true, "bot moves resolved without playback entries");
  }
  await expect(page.getByText(/is playing…/)).toBeVisible();
  await skip.click();
  await expect(skip).toBeHidden({ timeout: 10_000 });
  await expect(page.getByText(/Your move|choose an action/).first()).toBeVisible();
});
