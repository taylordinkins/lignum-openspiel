import { indexManifest } from "./resolve";
import type { LoadedManifests, ThemeId, ThemeManifest } from "./types";

// third_party/ and assets/ sit outside web/. Globs that match nothing are fine, so a
// scrubbed clone (no third_party/) still builds; the official theme is then just absent.
// third_party/ is not in the repository; with a local copy, the official theme is offered only
// when VITE_LIGNUM_OFFICIAL_THEME=1 is set for the Vite dev server or build.
const OFFICIAL_ENABLED = import.meta.env.VITE_LIGNUM_OFFICIAL_THEME === "1";
const officialManifest = import.meta.glob<ThemeManifest>("../../../../../third_party/art/manifest.json", {
  eager: true,
  import: "default",
});
const officialFiles = import.meta.glob<string>("../../../../../third_party/art/**/*.{webp,png,jpg,jpeg,svg,gif}", {
  eager: true,
  import: "default",
  query: "?url",
});
const genericManifest = import.meta.glob<ThemeManifest>("../../../../../assets/generic/manifest.json", {
  eager: true,
  import: "default",
});
const genericFiles = import.meta.glob<string>("../../../../../assets/generic/**/*.{webp,png,jpg,jpeg,svg,gif}", {
  eager: true,
  import: "default",
  query: "?url",
});

function urlsByFile(files: Record<string, string>, marker: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [path, url] of Object.entries(files)) out[path.slice(path.indexOf(marker) + marker.length)] = url;
  return out;
}

export function loadManifests(): LoadedManifests {
  const out: LoadedManifests = {};
  const themes: [ThemeId, Record<string, ThemeManifest>, Record<string, string>][] = [
    ["official", OFFICIAL_ENABLED ? officialManifest : {}, urlsByFile(OFFICIAL_ENABLED ? officialFiles : {}, "third_party/art/")],
    ["generic", genericManifest, urlsByFile(genericFiles, "assets/generic/")],
  ];
  for (const [id, manifests, urls] of themes) {
    const idx = indexManifest(id, Object.values(manifests)[0], urls);
    if (idx) out[id] = idx;
  }
  return out;
}
