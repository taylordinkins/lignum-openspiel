import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { join } from "node:path";

// The official theme needs a local third_party/art and VITE_LIGNUM_OFFICIAL_THEME=1.
const ART = join(process.cwd(), "..", "third_party", "art", "manifest.json");
const OFFICIAL = existsSync(ART) && process.env.VITE_LIGNUM_OFFICIAL_THEME === "1";

test("full official-theme game with joinery reaches the scoring breakdown", async ({ page }) => {
  test.skip(!OFFICIAL, "official theme not enabled (needs third_party/art and VITE_LIGNUM_OFFICIAL_THEME=1)");
  test.setTimeout(420_000);

  const consoleErrors: string[] = [];
  const badImages: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.request().resourceType() === "image" && r.status() >= 400) badImages.push(`${r.status()} ${r.url()}`);
  });
  page.on("requestfailed", (r) => {
    if (r.resourceType() === "image") badImages.push(`failed ${r.url()}`);
  });

  // Generic is the default theme; pick official before the app reads the stored choice.
  await page.addInitScript(() => window.localStorage.setItem("lignum.theme", "official"));
  await page.goto("/");
  await page.getByLabel("Players").selectOption("2");
  await page.getByLabel("Seat P0").selectOption("human");
  await page.getByLabel("Seat P1").selectOption("random");
  const joinery = page.getByLabel("Joinery and Buildings expansion");
  await joinery.check();
  await page.getByLabel("Seed (optional)").fill("1");
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();

  // Collect fallback sprites and check seat labels as the game goes.
  const fallbacks = new Set<string>();
  const official = new Set<string>();
  const scan = async () => {
    const imgs = await page.locator("img").evaluateAll((els) =>
      (els as HTMLImageElement[]).map((i) => ({
        src: i.src,
        ok: !i.complete || i.naturalWidth > 0,
      })),
    );
    for (const i of imgs) {
      if (!i.ok) badImages.push(`broken ${i.src}`);
      const name = decodeURIComponent(i.src).split(/third_party\/art\/|assets\/generic\//).pop()!.split("?")[0]!;
      if (i.src.includes("assets/generic")) fallbacks.add(name);
      else if (i.src.includes("third_party/art")) official.add(name);
    }
  };

  const over = page.getByLabel("Game over");
  const enabled = page
    .getByRole("list", { name: /^Legal actions/ })
    .getByRole("button")
    .and(page.locator(":enabled"))
    .first();
  let moves = 0;
  for (; moves < 5000; moves++) {
    if (await over.isVisible()) break;
    if (moves % 25 === 0) await scan();
    try {
      await enabled.waitFor({ state: "visible", timeout: 500 });
    } catch {
      continue;
    }
    await enabled.click({ timeout: 2_000 }).catch(() => {});
  }
  expect(moves).toBeLessThan(5000);
  await expect(over).toBeVisible();
  await scan();

  const result = page.getByRole("region", { name: "Result" }).first();
  await expect(page.getByRole("table", { name: "Final scores" })).toBeVisible();
  await expect(result).toBeVisible();
  const body = await page.locator("body").innerText();
  expect(body).toMatch(/\bP0\b/);
  expect(body).not.toMatch(/Player [0-9]/);

  console.log(`official sprites seen: ${official.size}`);
  console.log(`generic fallbacks seen (${fallbacks.size}): ${[...fallbacks].sort().join(", ")}`);
  expect(official.size, "official sprites should load").toBeGreaterThan(0);
  expect(badImages, "broken image requests").toEqual([]);
  expect(consoleErrors, "console errors").toEqual([]);
});
