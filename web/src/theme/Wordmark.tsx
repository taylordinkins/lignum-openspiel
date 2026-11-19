import { IconTree } from "./icons";

/** "Lignum" in the display face, italic, with a small fir-tree mark. No image assets. */
export function Wordmark({ size = "sm" }: { size?: "sm" | "lg" }) {
  const lg = size === "lg";
  return (
    <span
      className={`wordmark wordmark-${size}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: lg ? "0.3em" : "0.25em",
        fontFamily: "var(--font-display)",
        fontStyle: "italic",
        fontWeight: 700,
        fontSize: lg ? "var(--fs-hero)" : "var(--fs-lg)",
        lineHeight: 1,
        color: "var(--forest-dark)",
      }}
    >
      <span style={{ display: "inline-flex", color: "var(--forest)", fontSize: "0.75em" }}>
        <IconTree width="1em" height="1em" />
      </span>
      Lignum
    </span>
  );
}
