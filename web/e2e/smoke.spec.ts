import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const SEED = "1";

async function newGame(page: Page, players: number, seats: string[], seed = SEED) {
  await page.goto("/");
  await page.getByLabel("Players").selectOption(String(players));
  for (let i = 0; i < players; i++) {
    await page.getByLabel(`Seat P${i}`).selectOption(seats[i]!);
  }
  await page.getByLabel("Seed (optional)").fill(seed);
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
}

const actionButtons = (page: Page) =>
  page.getByRole("list", { name: /^Legal actions/ }).getByRole("button");

/** Click the first enabled legal action until the game is over (or the move cap is hit). */
async function playToEnd(page: Page, cap: number): Promise<number> {
  const over = page.getByLabel("Game over");
  const enabled = actionButtons(page).and(page.locator(":enabled")).first();
  let moves = 0;
  for (; moves < cap; moves++) {
    if (await over.isVisible()) break;
    try {
      await enabled.waitFor({ state: "visible", timeout: 500 });
    } catch {
      continue; // bot thinking or game just ended; re-check
    }
    await enabled.click({ timeout: 2_000 }).catch(() => {});
  }
  return moves;
}

test("2-player game against the random bot reaches game over", async ({ page }) => {
  test.setTimeout(300_000);
  await newGame(page, 2, ["human", "random"]);
  const started = Date.now();
  const moves = await playToEnd(page, 5000);
  console.log(`full game: ${moves} loop iterations, ${Math.round((Date.now() - started) / 1000)}s`);
  const over = page.getByLabel("Game over");
  await expect(over).toBeVisible();
  expect(moves).toBeLessThan(5000);
  await expect(over.getByText(/^(P\d wins|Tie: P\d)/)).toBeVisible();
  await expect(over.getByText(/^Returns: P0 -?\d+(\.\d+)?, P1 -?\d+(\.\d+)?/)).toBeVisible();
});

test("export and import round-trip a finished game", async ({ page }) => {
  test.setTimeout(300_000);
  await newGame(page, 2, ["human", "random"], "2");
  await playToEnd(page, 5000);
  const over = page.getByLabel("Game over");
  await expect(over).toBeVisible();
  const returns = await over.getByText(/^Returns: /).innerText();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export replay" }).click();
  const path = await (await downloadPromise).path();
  expect(JSON.parse(readFileSync(path, "utf8"))).toBeTruthy();
  await page.getByLabel(/Import replay/).setInputFiles(path);
  // Import is only wired when the app passes onImported; the new game must show the same result.
  await expect(page.getByLabel("Game over").getByText(/^Returns: /)).toHaveText(returns);
});

test("report dialog submits and shows an id", async ({ page }) => {
  await newGame(page, 2, ["human", "random"]);
  await page.getByRole("button", { name: "Report a problem" }).click();
  const dialog = page.getByRole("dialog", { name: "Report a problem" });
  await dialog.getByLabel("Note").fill("e2e smoke report");
  await dialog.getByRole("button", { name: "Submit report" }).click();
  await expect(dialog.getByRole("status")).toContainText(/Report id: \S+/);
});

test("hotseat: curtain appears on seat change and hides the previous pick", async ({ page }) => {
  await newGame(page, 3, ["human", "human", "human"]);
  const curtain = page.getByRole("dialog", { name: "Hand-off" });
  await expect(curtain).toHaveCount(0);
  await expect(page.getByText("Current player: P0 (human)")).toBeVisible();

  // P0 picks area 2 (a hidden pick); the screen must be covered for P1.
  await page.getByRole("button", { name: "Pick cutting area 2", exact: true }).click();
  await expect(curtain).toBeVisible();
  await expect(curtain.getByText("Pass to P1")).toBeVisible();
  const covered = await page.locator("body").innerText();
  expect(covered).not.toMatch(/Pick cutting area|Action log|Your move|area 2|Cutting areas/);
  expect(await page.getByRole("button", { name: /^Pick cutting area/ }).count()).toBe(0);

  await curtain.getByRole("button", { name: "Click when ready" }).click();
  await expect(curtain).toHaveCount(0);
  await expect(page.getByText("Current player: P1 (human)")).toBeVisible();
  await expect(page.getByText("Cutting areas")).toBeVisible();

  // P1 picks; the curtain moves on to P2.
  await page.getByRole("button", { name: /^Pick cutting area/ }).first().click();
  await expect(curtain.getByText("Pass to P2")).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(/Pick cutting area|Action log/);
});
