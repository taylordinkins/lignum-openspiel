export type CardKind = "task" | "placement" | "winter" | "pw" | "building" | "craftwork" | "loan";

const slug = (s: string, sep: string): string => s.trim().toLowerCase().replace(/[\s_-]+/g, sep);

/** Sprite id for a card from the id or name the view gives (e.g. "task 05" -> "task-05"). */
export function cardSpriteId(kind: CardKind, name: string): string {
  switch (kind) {
    case "building":
      return `building-${slug(name, "_")}`;
    case "pw":
      return name.toLowerCase().startsWith("pw") ? slug(name, "-") : `pw-${slug(name, "-")}`;
    case "craftwork":
      return `craftwork-${slug(name, "-")}`;
    default:
      return slug(name, "-");
  }
}
