import { createElement } from "react";
import type { GamePlugin } from "../registry";
import BoardPanel from "./BoardPanel";
import SeatPanels from "./SeatPanels";
import type { LignumView } from "./types";

export const lignumPlugin: GamePlugin = {
  id: "lignum",
  title: "Lignum",
  phaseLabel: (g) => {
    const v = g.view;
    if (typeof v.phase_label === "string") return v.phase_label;
    return typeof v.phase === "string" ? v.phase : undefined;
  },
  /** "Take task 07" gains the card's reward and requirements from the view (R-028). */
  actionLabel: (g, a) => {
    const card = (g.view as LignumView).tasks?.cards?.find(
      (c) => a.label === `Take ${c.id}`,
    );
    if (!card) return a.label;
    const reqs = card.requirements.map((r) => r.text).join("; ");
    return `${a.label} ($${card.reward}: ${reqs})`;
  },
  renderBoard: (g, ui) => createElement(BoardPanel, { game: g, ui }),
  renderSeats: (g, ui) => createElement(SeatPanels, { game: g, ui }),
};
