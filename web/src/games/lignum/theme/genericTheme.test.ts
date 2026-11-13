import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { indexManifest, resolveSprite } from "./resolve";
import type { LoadedManifests, ThemeManifest } from "./types";

const root = resolve(__dirname, "../../../../..");
const read = (p: string): ThemeManifest => JSON.parse(readFileSync(resolve(root, p), "utf8"));
const officialPath = "third_party/art/manifest.json";
const genericManifest = read("assets/generic/manifest.json");
const urls = Object.fromEntries(genericManifest.assets.map((a) => [a.file, `/g/${a.file}`]));
const loaded: LoadedManifests = {
  official: indexManifest("official", undefined, {}),
  generic: indexManifest("generic", genericManifest, urls),
};

describe("generic theme", () => {
  it("resolves the extra ids the board needs", () => {
    for (const id of ["board-joinery", "player-extension", "foreman", "pawn-0", "pawn-3", "piece-hardwood-log"]) {
      expect(resolveSprite("generic", id, loaded)).toMatchObject({ theme: "generic" });
    }
  });

  it.skipIf(!existsSync(resolve(root, officialPath)))("resolves every official id", () => {
    for (const a of read(officialPath).assets) {
      expect(resolveSprite("generic", a.id, loaded), a.id).toMatchObject({ category: a.category, theme: "generic" });
      if (a.width) {
        const g = genericManifest.assets.find((x) => x.id === a.id)!;
        expect([g.width, g.height], `${a.id} size`).toEqual([a.width, a.height]);
      }
    }
  });
});
