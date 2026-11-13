# ruff: noqa: E501  (inline SVG markup reads better on one line)
"""Generate the original flat-vector art in ``assets/generic/`` (PLAN.md §5.6, D11, D21, task 9f).

Writes one SVG per sprite plus ``manifest.json`` in the same shape as the official
``third_party/art/manifest.json``. Every official id is covered at the official size, and board
regions are drawn from ``web/.../board/layout.json`` / ``sawmillLayout.json`` so the interactive
layers sit on the right spots. Card faces are rendered from ``data/components/*.yaml``; nothing
here hard-codes a card value. Output is deterministic; re-run after editing this file:
``uv run python -m tools.make_generic_theme [--out DIR]``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "generic"
OFFICIAL = ROOT / "third_party" / "art" / "manifest.json"
COMPONENTS = ROOT / "data" / "components"
BUILDINGS = COMPONENTS / "buildings.yaml"
LAYOUT = ROOT / "web" / "src" / "games" / "lignum" / "board" / "layout.json"
PAD_LAYOUT = ROOT / "web" / "src" / "games" / "lignum" / "board" / "sawmillLayout.json"

CARD = (420, 629)
INK = "#2a2118"
INK_SOFT = "#5b4a35"
PAPER = "#f7efd9"
PAPER_DARK = "#e6d6b2"
GOLD = "#d9a441"
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

SEATS = ("#c0392b", "#2e6fb5", "#2e8b57", "#d4a017")
WORKERS = {"bearer": "#3a9a4a", "woodcutter": "#8b5a2b", "sawyer": "#f4f4f0", "joiner": "#e8c020"}
# kind -> (disk side, disk top, beam front)
WOOD = {
    "firewood": ("#cfb77f", "#efe0b4", "#dcbf80"),
    "softwood": ("#6f6e2c", "#9a9843", "#9c4f2e"),
    "hardwood": ("#25221f", "#47423c", "#2b2825"),
}
CRAFT = ("board", "shingle", "stake", "reed", "joker")
ACCENT = {
    "placement": "#8a6a3b", "tasks": "#3f7d4e", "winter": "#3f6f9b", "planned_work": "#b9792f",
    "loan": "#8d3b3b", "buildings": "#6b5b45", "craftwork": "#7a6a3a",
}  # fmt: skip
SEASON_COLOR = {"spring": "#5aa469", "summer": "#e6c04f", "fall": "#c8483c", "winter": "#4f86c6"}
SEASON_LETTER = {"spring": "S", "summer": "S", "fall": "F", "winter": "W"}


# ---------------------------------------------------------------- small helpers
def svg(w: int, h: int, body: str, extra: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"{extra}{body}</svg>\n"
    )


def text(
    x: float, y: float, s: str, size: float, fill: str = INK, weight: str = "bold",
    family: str = SANS, anchor: str = "middle", extra: str = "",
) -> str:  # fmt: skip
    return (
        f'<text x="{x:g}" y="{y:g}" font-family="{family}" font-size="{size:g}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="central"{extra}>{escape(s)}</text>'
    )


def title(s: str) -> str:
    return s.replace("-", " ").replace("_", " ").title()


def wrap(s: str, width: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def shade(hex_color: str, f: float) -> str:
    """Scale a #rrggbb colour towards black (f<1) or white (f>1)."""
    c = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    c = [round(v * f) for v in c] if f <= 1 else [round(v + (255 - v) * (f - 1)) for v in c]
    return "#" + "".join(f"{v:02x}" for v in c)


def place(inner: str, x: float, y: float, w: float, h: float, box: float = 96) -> str:
    """Draw a glyph authored in a ``box`` x ``box`` square into the rect (x, y, w, h)."""
    return (
        f'<svg x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" viewBox="0 0 {box:g} {box:g}" '
        f'preserveAspectRatio="xMidYMid meet">{inner}</svg>'
    )


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((COMPONENTS / name).read_text())
    return data


# ---------------------------------------------------------------- glyphs (96 x 96 boxes)
def beam(w: float, h: float, color: str) -> str:
    """A squared-off timber seen from above-right: used for milled wood (labelled "Milled")."""
    d = w * 0.14
    top, end = shade(color, 1.25), shade(color, 0.72)
    return (
        f'<polygon points="0,{d:g} {d:g},0 {w:g},0 {w - d:g},{d:g}" fill="{top}"/>'
        f'<rect x="0" y="{d:g}" width="{w - d:g}" height="{h - d:g}" fill="{color}"/>'
        f'<polygon points="{w - d:g},{d:g} {w:g},0 {w:g},{h - d:g} {w - d:g},{h:g}" fill="{end}"/>'
        f'<path d="M{w * 0.1:g} {h * 0.55:g}H{w * 0.55:g}M{w * 0.2:g} {h * 0.8:g}H{w * 0.7:g}" stroke="{shade(color, 0.8)}" stroke-width="{max(1.2, h * 0.05):g}" stroke-linecap="round" fill="none"/>'
        f'<path d="M0 {d:g}L{d:g} 0H{w:g}V{h - d:g}L{w - d:g} {h:g}H0Z" fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="{max(1.2, h * 0.04):g}" stroke-linejoin="round"/>'
    )


def disk(w: float, h: float, kind: str) -> str:
    """A round puck seen from above: used for unmilled wood (labelled "Log")."""
    side, top, _ = WOOD[kind]
    rx, ry = w / 2 - 1, h * 0.36
    cx, cy_top, cy_bot = w / 2, h * 0.38, h * 0.62
    return (
        f'<ellipse cx="{cx:g}" cy="{cy_bot:g}" rx="{rx:g}" ry="{ry:g}" fill="{side}"/>'
        f'<rect x="{cx - rx:g}" y="{cy_top:g}" width="{2 * rx:g}" height="{cy_bot - cy_top:g}" fill="{side}"/>'
        f'<ellipse cx="{cx:g}" cy="{cy_top:g}" rx="{rx:g}" ry="{ry:g}" fill="{top}"/>'
        f'<ellipse cx="{cx:g}" cy="{cy_top:g}" rx="{rx * 0.62:g}" ry="{ry * 0.62:g}" fill="none" stroke="{side}" stroke-opacity=".55" stroke-width="{max(1, h * 0.05):g}"/>'
        f'<ellipse cx="{cx:g}" cy="{cy_top:g}" rx="{rx * 0.26:g}" ry="{ry * 0.26:g}" fill="none" stroke="{side}" stroke-opacity=".55" stroke-width="{max(1, h * 0.05):g}"/>'
        f'<path d="M{cx - rx:g} {cy_top:g}V{cy_bot:g}A{rx:g} {ry:g} 0 0 0 {cx + rx:g} {cy_bot:g}V{cy_top:g}" fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="{max(1.2, h * 0.04):g}"/>'
        f'<ellipse cx="{cx:g}" cy="{cy_top:g}" rx="{rx:g}" ry="{ry:g}" fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="{max(1.2, h * 0.04):g}"/>'
    )


def meeple(fill: str, stroke: str = INK, sw: float = 4) -> str:
    return (
        '<path d="M50 5C60 5 66 11 66 19C66 25 62 29 58 32C66 34 76 37 84 41C94 45 98 51 94 57C90 63 82 61 76 59L70 57C72 67 80 80 88 90C90 94 88 98 82 98L62 98C56 98 54 91 50 85C46 91 44 98 38 98L18 98C12 98 10 94 12 90C20 80 28 67 30 57L24 59C18 61 10 63 6 57C2 51 6 45 16 41C24 37 34 34 42 32C38 29 34 25 34 19C34 11 40 5 50 5Z" '
        f'transform="translate(0 -2)" fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}" stroke-linejoin="round"/>'
    )


def g_axe() -> str:
    return (
        f'<path d="M30 86L62 22" stroke="#8a5a2b" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M52 14C70 8 86 16 90 34C76 36 66 34 58 38Z" fill="#9aa5ad" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
    )


def g_saw() -> str:
    teeth = "".join(f"L{14 + i * 8} {66 + (4 if i % 2 else 0)}" for i in range(1, 10))
    return (
        f'<path d="M12 56L84 36L86 56L14 66{teeth[:0]}Z" fill="#c9d0d4" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
        f'<path d="M14 66L84 56" stroke="{INK}" stroke-width="2" stroke-dasharray="3 3"/>'
        f'<rect x="70" y="26" width="22" height="34" rx="8" transform="rotate(-12 81 43)" fill="#8a5a2b" stroke="{INK}" stroke-width="4"/>'
    )


def g_wagon() -> str:
    return (
        f'<rect x="16" y="34" width="54" height="26" rx="4" fill="#a8743a" stroke="{INK}" stroke-width="4"/>'
        f'<path d="M70 48L92 40" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
        f'<circle cx="30" cy="68" r="13" fill="#d7b27a" stroke="{INK}" stroke-width="4"/><circle cx="30" cy="68" r="4" fill="{INK}"/>'
        f'<circle cx="58" cy="68" r="13" fill="#d7b27a" stroke="{INK}" stroke-width="4"/><circle cx="58" cy="68" r="4" fill="{INK}"/>'
    )


def g_sledge() -> str:
    return (
        f'<path d="M8 62C8 76 22 78 34 78H84C92 78 92 66 82 68" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M20 62V44M50 72V44M78 70V44" stroke="#8a5a2b" stroke-width="6" stroke-linecap="round"/>'
        f'<rect x="12" y="34" width="72" height="12" rx="4" fill="#a8743a" stroke="{INK}" stroke-width="4"/>'
    )


def g_raft() -> str:
    logs = "".join(
        f'<rect x="12" y="{20 + i * 15}" width="72" height="12" rx="6" fill="#a8743a" stroke="{INK}" stroke-width="3.5"/>'
        f'<circle cx="80" cy="{26 + i * 15}" r="4" fill="#e8c98f"/>'
        for i in range(4)
    )
    return (
        logs
        + f'<path d="M30 14V82M60 14V82" stroke="{INK_SOFT}" stroke-width="3" stroke-dasharray="2 4"/>'
    )


def g_hut() -> str:
    return (
        f'<path d="M12 46L48 14L84 46Z" fill="#b5532f" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
        f'<rect x="20" y="46" width="56" height="38" fill="#e7d3a1" stroke="{INK}" stroke-width="4"/>'
        f'<rect x="40" y="58" width="16" height="26" fill="#7a4a24" stroke="{INK}" stroke-width="3"/>'
        f'<rect x="62" y="22" width="9" height="18" fill="#8a7a68" stroke="{INK}" stroke-width="3"/>'
    )


def g_cube(color: str = "#4faa4f") -> str:
    return (
        f'<polygon points="48,10 84,28 48,46 12,28" fill="{shade(color, 1.3)}"/>'
        f'<polygon points="12,28 48,46 48,86 12,66" fill="{color}"/>'
        f'<polygon points="84,28 48,46 48,86 84,66" fill="{shade(color, 0.72)}"/>'
        f'<path d="M48 10L84 28V66L48 86L12 66V28Z" fill="none" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/><path d="M12 28L48 46L84 28M48 46V86" stroke="{INK}" stroke-width="3" fill="none"/>'
    )


def g_wheat() -> str:
    grains = "".join(
        f'<ellipse cx="{48 + s * 12}" cy="{18 + i * 14}" rx="6" ry="11" transform="rotate({s * 28} {48 + s * 12} {18 + i * 14})" fill="#e3b84b" stroke="{INK}" stroke-width="2.5"/>'
        for i in range(4)
        for s in (-1, 1)
    )
    return (
        f'<path d="M48 90V20" stroke="#8a6a2a" stroke-width="5" stroke-linecap="round"/>{grains}'
        f'<ellipse cx="48" cy="10" rx="6" ry="11" fill="#e3b84b" stroke="{INK}" stroke-width="2.5"/>'
    )


def g_coin(label: str = "$", fill: str = "#e8c547", rim: str = "#b8902a") -> str:
    return (
        f'<circle cx="48" cy="48" r="43" fill="{rim}" stroke="{INK}" stroke-width="4"/>'
        f'<circle cx="48" cy="48" r="34" fill="{fill}" stroke="{shade(rim, 0.7)}" stroke-width="3"/>'
        + text(48, 50, label, 40 if len(label) < 3 else 30, INK, family=SERIF)
    )


def g_star(fill: str = "#f0c24a") -> str:
    return f'<path d="M48 8L59 36L90 38L66 57L74 88L48 71L22 88L30 57L6 38L37 36Z" fill="{fill}" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'


def g_reed() -> str:
    out = ""
    for dx, tilt in ((-18, -8), (0, 0), (18, 8)):
        x = 48 + dx
        out += (
            f'<path d="M{x} 90L{x + tilt} 18" stroke="#6f8f3f" stroke-width="5" stroke-linecap="round"/>'
            f'<rect x="{x + tilt - 6}" y="8" width="12" height="32" rx="6" fill="#8a5a2b" stroke="{INK}" stroke-width="3" transform="rotate({tilt} {x + tilt} 24)"/>'
        )
    return out


def g_stake() -> str:
    return (
        f'<path d="M30 88L70 18L80 24L40 94Z" fill="#c8985a" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
        f'<path d="M30 88L34 76L42 84Z" fill="{INK}"/>'
    )


def g_shingle() -> str:
    rows = ""
    for r in range(3):
        for c in range(3):
            x = 8 + c * 28 + (14 if r % 2 else 0)
            rows += f'<path d="M{x} {18 + r * 22}h26v14a13 13 0 0 1 -26 0Z" fill="{("#a8743a", "#8a5a2b")[(r + c) % 2]}" stroke="{INK}" stroke-width="3"/>'
    return rows


def g_plank() -> str:
    return (
        f'<g transform="rotate(-25 48 48)"><rect x="4" y="32" width="88" height="32" rx="3" fill="#dcbf80" stroke="{INK}" stroke-width="4"/>'
        '<path d="M12 44H70M20 54H82" stroke="#b28f4f" stroke-width="3" stroke-linecap="round"/></g>'
    )


def g_x() -> str:
    return (
        f'<path d="M20 20L76 76M76 20L20 76" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>'
        '<path d="M20 20L76 76M76 20L20 76" stroke="#d94a3a" stroke-width="9" stroke-linecap="round"/>'
    )


def g_sun() -> str:
    rays = "".join(
        f'<path d="M48 8V20" stroke="#e0a020" stroke-width="6" stroke-linecap="round" transform="rotate({a} 48 48)"/>'
        for a in range(0, 360, 45)
    )
    return rays + f'<circle cx="48" cy="48" r="20" fill="#f5c542" stroke="{INK}" stroke-width="4"/>'


def g_flame() -> str:
    return (
        f'<path d="M48 8C58 28 78 38 76 62C74 80 62 90 48 90C34 90 22 80 20 62C20 50 28 44 34 36C34 46 40 50 44 50C40 34 44 20 48 8Z" fill="#e6602a" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M48 48C54 58 62 62 60 72C58 80 54 84 48 84C42 84 38 80 36 72C36 62 44 58 48 48Z" fill="#f5c542"/>'
    )


def g_task() -> str:
    return (
        f'<rect x="20" y="10" width="56" height="76" rx="6" fill="{PAPER}" stroke="{INK}" stroke-width="4"/>'
        f'<path d="M30 30H66M30 46H66M30 62H52" stroke="{INK_SOFT}" stroke-width="5" stroke-linecap="round"/>'
    )


def g_log() -> str:
    return (
        '<rect x="6" y="26" width="76" height="44" rx="8" fill="#a8743a" stroke="#2a2118" stroke-width="4"/>'
        '<ellipse cx="78" cy="48" rx="12" ry="22" fill="#e8c98f" stroke="#2a2118" stroke-width="4"/>'
        '<ellipse cx="78" cy="48" rx="5" ry="10" fill="none" stroke="#a8743a" stroke-width="3"/>'
    )


ICON_GLYPH = {
    "board": g_plank, "dollar": g_coin, "fodder": g_wheat, "food": g_cube, "hut": g_hut,
    "joker": g_star, "mill-worker": lambda: meeple("#c0392b"), "raft": g_raft, "reed": g_reed,
    "saw": g_saw, "shingle": g_shingle, "sledge": g_sledge, "stake": g_stake, "wagon": g_wagon,
    "x": g_x,
}  # fmt: skip

# Fallback sizes for the official ids, used when third_party/art is absent (scrubbed clone).
ICON_SIZE = {
    "board": (96, 95), "dollar": (96, 93), "firewood": (96, 58), "fodder": (96, 163),
    "food": (96, 109), "hardwood": (96, 51), "hut": (96, 96), "joker": (96, 97),
    "mill-worker": (96, 84), "raft": (96, 95), "reed": (96, 98), "saw": (96, 96),
    "shingle": (96, 94), "sledge": (96, 96), "softwood": (96, 57), "stake": (96, 94),
    "wagon": (96, 98), "x": (96, 95),
}  # fmt: skip


CRAFT_ICONS = {"board", "stake", "shingle", "reed", "joker"}


def icon(w: int, h: int, kind: str) -> str:
    if kind in WOOD:
        return svg(w, h, beam(w - 2, h - 2, WOOD[kind][2]).replace("<polygon", "<polygon", 1))
    inner = ICON_GLYPH.get(kind, g_star)()
    if kind in CRAFT_ICONS:  # craftwork reads apart from equipment: light-pink backing
        back = (
            f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="{min(w, h) * 0.22:g}" '
            f'fill="#f8d3dc" stroke="{INK}" stroke-width="3"/>'
        )
        return svg(w, h, back + place(inner, w * 0.1, h * 0.1, w * 0.8, h * 0.8))
    return svg(w, h, place(inner, 0, 0, w, h))


# ---------------------------------------------------------------- tokens
def disk_sprite(w: int, h: int, kind: str) -> str:
    return svg(w, h, disk(w, h, kind))


def log_sprite(w: int, h: int, kind: str) -> str:
    return svg(w, h, beam(w - 2, h - 2, WOOD[kind][2]))


def pawn(color: str, label: str, w: int = 62, h: int = 112) -> str:
    cx = w / 2
    body = (
        f'<ellipse cx="{cx:g}" cy="{h - 12}" rx="{w * 0.44:g}" ry="9" fill="{shade(color, 0.6)}" stroke="{INK}" stroke-width="3"/>'
        f'<path d="M{w * 0.14:g} {h - 14}C{w * 0.2:g} {h * 0.55:g} {w * 0.36:g} {h * 0.5:g} {w * 0.38:g} {h * 0.42:g}H{w * 0.62:g}C{w * 0.64:g} {h * 0.5:g} {w * 0.8:g} {h * 0.55:g} {w * 0.86:g} {h - 14}Z" fill="{color}" stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>'
        f'<circle cx="{cx:g}" cy="{h * 0.27:g}" r="{w * 0.27:g}" fill="{shade(color, 1.15)}" stroke="{INK}" stroke-width="3.5"/>'
        f'<ellipse cx="{cx - w * 0.08:g}" cy="{h * 0.22:g}" rx="{w * 0.07:g}" ry="{w * 0.05:g}" fill="#fff" fill-opacity=".55"/>'
    )
    return svg(w, h, body + text(cx, h * 0.68, label, w * 0.3, "#ffffff"))


def worker(color: str, w: int, h: int, badge: str = "") -> str:
    inner = meeple(color)
    if badge:
        inner += (
            f'<circle cx="50" cy="56" r="17" fill="#fff" stroke="{INK}" stroke-width="4"/>'
            + text(50, 57, badge, 22, INK)
        )
    return svg(w, h, place(inner, 0, 0, w, h, 100))


def coin(size: int, label: str) -> str:
    return svg(size, size, place(g_coin(label, "#dfe3e6", "#a5adb4"), 0, 0, size, size))


def token_disc(size: int, fill: str, inner: str) -> str:
    c = size / 2
    return svg(
        size,
        size,
        f'<circle cx="{c:g}" cy="{c:g}" r="{c - 6:g}" fill="{fill}" stroke="{INK}" stroke-width="7"/>'
        f'<circle cx="{c:g}" cy="{c:g}" r="{c - 22:g}" fill="none" stroke="{INK}" stroke-opacity=".3" stroke-width="4"/>'
        + inner,
    )


def craft_tile(w: int, h: int, kind: str) -> str:
    base = f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="14" fill="#f8d3dc" stroke="{INK}" stroke-width="4"/>'
    if kind == "back":
        return svg(
            w, h,
            base + "".join(f'<path d="M12 {14 + i * 18}H{w - 12}" stroke="#c8985a" stroke-width="3" stroke-opacity=".7"/>' for i in range(5))
            + text(w / 2, h / 2, "?", h * 0.5, "#8a5a2b", family=SERIF),
        )  # fmt: skip
    glyph = {
        "board": g_plank,
        "shingle": g_shingle,
        "stake": g_stake,
        "reed": g_reed,
        "joker": g_star,
    }[kind]()
    return svg(w, h, base + place(glyph, 10, 8, w - 20, h - 16))


def cutting_token(w: int, h: int, front: bool) -> str:
    inner = (
        place(g_axe(), w * 0.22, h * 0.2, w * 0.56, h * 0.6)
        if front
        else text(w / 2, h / 2, "?", h * 0.5, "#e8e0c8", family=SERIF)
    )
    return token_disc(w, "#9ec27f" if front else "#5f7a4a", inner).replace(
        f'height="{w}" viewBox="0 0 {w} {w}"', f'height="{h}" viewBox="0 0 {w} {w}"', 1
    )


def woodpile(w: int, h: int) -> str:
    out = f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="22" fill="#e7d7b0" stroke="{INK}" stroke-width="6"/>'
    r = 34
    cols = [(0, 5), (1, 4), (2, 3)]
    y = h - 70
    for row, n in cols:
        for i in range(n):
            x = w / 2 + (i - (n - 1) / 2) * (2 * r + 4)
            yy = y - row * (2 * r - 6)
            out += (
                f'<circle cx="{x:g}" cy="{yy:g}" r="{r}" fill="#c18a4a" stroke="{INK}" stroke-width="4"/>'
                f'<circle cx="{x:g}" cy="{yy:g}" r="{r * 0.62:g}" fill="none" stroke="#8a5a2b" stroke-width="3"/>'
                f'<circle cx="{x:g}" cy="{yy:g}" r="{r * 0.26:g}" fill="none" stroke="#8a5a2b" stroke-width="3"/>'
            )
    return svg(w, h, out + text(w / 2, 40, "Woodpile", 34, INK, family=SERIF))


# ---------------------------------------------------------------- cards (text rendered from data)
def card_frame(cat: str, head: str, sub: str = "") -> str:
    w, h = CARD
    acc = ACCENT.get(cat, INK_SOFT)
    body = f'<rect x="5" y="5" width="{w - 10}" height="{h - 10}" rx="30" fill="{PAPER}" stroke="{INK}" stroke-width="6"/>'
    body += (
        f'<path d="M5 35A30 30 0 0 1 35 5H{w - 35}A30 30 0 0 1 {w - 5} 35V118H5Z" fill="{acc}"/>'
    )
    body += f'<rect x="20" y="20" width="{w - 40}" height="{h - 40}" rx="18" fill="none" stroke="{INK}" stroke-opacity=".25" stroke-width="3"/>'
    body += f'<path d="M5 118H{w - 5}" stroke="{INK}" stroke-width="4"/>'
    body += text(w / 2, 60, head, 46, "#fff8e6", family=SERIF, extra=' font-style="italic"')
    if sub:
        body += text(w / 2, 97, sub, 24, "#f3e6c4", "normal")
    return body


def card_svg(body: str) -> str:
    return svg(*CARD, body)


def kv_lines(params: dict[str, Any]) -> list[str]:
    return [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in params.items()]


def task_card(c: dict[str, Any]) -> str:
    num = c["id"].split("_")[-1]
    body = card_frame("tasks", "Task", f"No. {num}")
    body += place(g_coin(str(c["reward"]), "#e8c547", "#b8902a"), 150, 140, 120, 120)
    body += text(210, 278, "Reward", 22, INK_SOFT, "normal")
    reqs = c["requirements"]
    y0 = 346
    gap = min(66, 240 // max(1, len(reqs)))
    for i, r in enumerate(reqs):
        y = y0 + i * gap
        body += f'<rect x="44" y="{y - 24:g}" width="332" height="{gap - 8:g}" rx="14" fill="{PAPER_DARK}" stroke="{INK}" stroke-opacity=".4" stroke-width="2"/>'
        sprite = beam(46, 28, WOOD[r["kind"]][2]) if r["milled"] else disk(46, 30, r["kind"])
        body += place(sprite, 58, y - 14, 46, 32, 46).replace(
            'viewBox="0 0 46 46"', 'viewBox="0 0 46 32"'
        )
        body += text(
            116,
            y + 2,
            title(r["kind"]) + (" milled" if r["milled"] else " log"),
            23,
            INK,
            anchor="start",
        )
        body += text(366, y + 2, f"Dry {r['drying']}", 22, INK_SOFT, "normal", anchor="end")
    return card_svg(body)


def placement_card(c: dict[str, Any]) -> str:
    body = card_frame("placement", "Placement", c["id"].split("_")[-1])
    food = set(c["food_areas"])
    for n in range(1, 7):
        col, row = (n - 1) % 2, (n - 1) // 2
        x, y = 40 + col * 175, 140 + row * 150
        body += f'<rect x="{x}" y="{y}" width="165" height="138" rx="16" fill="{PAPER_DARK}" stroke="{INK}" stroke-opacity=".45" stroke-width="2"/>'
        body += text(x + 22, y + 22, str(n), 28, INK_SOFT, family=SERIF)
        pieces = c["areas"].get(n, [])
        for i, k in enumerate(pieces):
            body += place(
                disk(46, 30, k), x + 24 + (i % 3) * 48, y + 46 + (i // 3) * 34, 46, 32, 46
            ).replace('viewBox="0 0 46 46"', 'viewBox="0 0 46 32"')
        if n in food:
            body += place(g_cube(), x + 106, y + 8, 46, 46)
    return card_svg(body)


def winter_card(c: dict[str, Any]) -> str:
    body = card_frame("winter", "Winter", f"Year {c['year']}")
    for half, rot in (("top", 0), ("bottom", 180)):
        v = c["halves"][half]
        inner = f'<rect x="40" y="0" width="340" height="150" rx="16" fill="{PAPER_DARK}" stroke="{INK}" stroke-opacity=".45" stroke-width="2"/>'
        inner += place(g_cube(), 62, 24, 62, 62) + text(
            168, 58, str(v["food"]), 58, INK, family=SERIF, anchor="start"
        )
        inner += place(g_log(), 232, 24, 62, 62) + text(
            318, 58, str(v["heating"]), 58, INK, family=SERIF, anchor="start"
        )
        inner += text(210, 126, "food          heating", 20, INK_SOFT, "normal")
        y = 140 if half == "top" else 330
        body += (
            f'<g transform="translate(0 {y})"' + (" " if not rot else "") + f">{inner}</g>"
            if not rot
            else (f'<g transform="translate(420 {y + 150}) rotate(180)">{inner}</g>')
        )
    body += f'<path d="M30 314H{CARD[0] - 30}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 8"/>'
    return card_svg(body)


def pw_card(c: dict[str, Any]) -> str:
    body = card_frame("planned_work", c["name"], "Planned work")
    for i, s in enumerate(("spring", "summer", "fall", "winter")):
        on = s in c["seasons"]
        x = 75 + i * 90
        body += f'<circle cx="{x}" cy="190" r="32" fill="{SEASON_COLOR[s] if on else "#e8dcc0"}" stroke="{INK}" stroke-width="{4 if on else 2}" stroke-opacity="{1 if on else 0.35}"/>'
        body += text(x, 191, SEASON_LETTER[s], 30, "#fff" if on else "#b8a888", family=SERIF)
        body += text(x, 240, s, 17, INK_SOFT if on else "#b8a888", "normal")
    for i, line in enumerate(kv_lines(c["params"])):
        for j, seg in enumerate(wrap(line, 24)):
            body += text(210, 320 + i * 62 + j * 30, seg, 26, INK, "normal")
    body += text(210, 560, "$1 per token already on the card", 19, INK_SOFT, "normal")
    return card_svg(body)


def loan_card(front: bool) -> str:
    loans = load("setup.yaml")["loans"]
    body = card_frame("loan", "Loan", "front" if front else "back")
    if front:
        body += place(g_coin(f"${loans['amount_each']}", "#e8c547", "#b8902a"), 120, 160, 180, 180)
        body += text(210, 400, "Take", 28, INK_SOFT, "normal")
        body += text(210, 460, f"Repay ${loans['repayment'][1]} at the end", 28, INK, "normal")
    else:
        body += text(210, 300, "Repay", 30, INK_SOFT, "normal")
        body += text(210, 390, f"${loans['repayment'][2]}", 110, "#8d3b3b", family=SERIF)
        body += text(210, 480, "with two loans", 26, INK_SOFT, "normal")
    return card_svg(body)


def building_tile(b: dict[str, Any]) -> str:
    size = 192
    body = f'<rect x="4" y="4" width="{size - 8}" height="{size - 8}" rx="20" fill="{PAPER}" stroke="{INK}" stroke-width="5"/>'
    body += f'<rect x="12" y="12" width="{size - 24}" height="{size - 24}" rx="14" fill="none" stroke="{INK}" stroke-opacity=".2" stroke-width="2"/>'
    body += place(g_hut(), 56, 14, 80, 74)
    for i, seg in enumerate(wrap(b["name"], 14)[:2]):
        body += text(size / 2, 108 + i * 24, seg, 21, INK, family=SERIF)
    for i, line in enumerate(kv_lines(b.get("params", {}))[:1]):
        for j, seg in enumerate(wrap(line, 22)[:2]):
            body += text(size / 2, 160 + i * 18 + j * 16, seg, 13, INK_SOFT, "normal")
    return svg(size, size, body)


# ---------------------------------------------------------------- boards
DARK_STYLE = "<style>@media (prefers-color-scheme: dark){.dk{opacity:.42}}</style>"


def dark_overlay(w: int, h: int) -> str:
    return f'<rect class="dk" x="0" y="0" width="{w}" height="{h}" rx="24" fill="#0a1510" opacity="0"/>'


def scenery(w: int, h: int, seed: int) -> str:
    """Soft meadow, hills, a river and tree dots: the wood/forest backdrop of both board sides."""
    out = (
        '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fb27a"/><stop offset=".55" stop-color="#6f9a5f"/><stop offset="1" stop-color="#4f7a49"/></linearGradient></defs>'
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="24" fill="url(#sky)"/>'
        f'<path d="M0 {h * 0.34:g}C{w * 0.2:g} {h * 0.26:g} {w * 0.35:g} {h * 0.4:g} {w * 0.55:g} {h * 0.32:g}S{w * 0.9:g} {h * 0.28:g} {w:g} {h * 0.36:g}V{h:g}H0Z" fill="#7aa468" opacity=".55"/>'
        f'<path d="M0 {h * 0.78:g}C{w * 0.25:g} {h * 0.7:g} {w * 0.5:g} {h * 0.86:g} {w:g} {h * 0.74:g}V{h:g}H0Z" fill="#3f6a41" opacity=".5"/>'
        f'<path d="M{w * 0.42:g} {h * 0.34:g}C{w * 0.36:g} {h * 0.5:g} {w * 0.5:g} {h * 0.6:g} {w * 0.44:g} {h * 0.74:g}S{w * 0.5:g} {h * 0.9:g} {w * 0.56:g} {h:g}" fill="none" stroke="#7fb1cf" stroke-width="{w * 0.018:g}" stroke-linecap="round" opacity=".8"/>'
    )
    s = seed
    for _ in range(70):
        s = (s * 1103515245 + 12345) % 2147483648
        x = s % (w - 40) + 20
        s = (s * 1103515245 + 12345) % 2147483648
        y = s % (h - 40) + 20
        r = 7 + s % 7
        out += f'<path d="M{x} {y - r * 1.6:g}L{x + r} {y + r * 0.6:g}H{x - r}Z" fill="#2f5a3a" opacity=".45"/>'
    return out


def box(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = PAPER,
    stroke: str = INK,
    rx: float = 10,
    op: float = 1,
    sw: float = 3,
) -> str:
    return f'<rect x="{x - w / 2:g}" y="{y - h / 2:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw:g}"/>'


PHASE_W = (
    ("Cutting", g_axe),
    ("Log driving", g_raft),
    ("Transport", g_wagon),
    ("Sawing", g_saw),
    ("Task", g_task),
    ("Sale", g_coin),
    ("Drying", g_sun),
)
PHASE_N = (
    ("Cutting", g_axe),
    ("Transport", g_wagon),
    ("Sawing", g_saw),
    ("Task", g_task),
    ("Food", g_cube),
    ("Heating", g_flame),
)


def loc_kinds(side: str) -> dict[int, tuple[str, int]]:
    data = load("path.yaml")["sides"][side]["locations"]
    return {int(loc["number"]): (loc["kind"], int(loc["capacity"])) for loc in data}


def regions(side: str) -> str:
    """Board furniture drawn at the spots in web/.../board/layout.json (pixel space of the board image)."""
    lay = json.loads(LAYOUT.read_text())[side]
    kinds = loc_kinds(side)
    out = ""
    # supply path: dirt road threading the locations in order
    pts = [(lay["start"]["x"], lay["start"]["y"])] + [
        (loc["x"], loc["y"])
        for _, loc in sorted(lay["locations"].items(), key=lambda kv: int(kv[0]))
    ]
    path = "M" + "L".join(f"{x:g} {y:g}" for x, y in pts)
    out += f'<path d="{path}" fill="none" stroke="#e3cf9f" stroke-width="34" stroke-linecap="round" stroke-linejoin="round" opacity=".55"/>'
    out += f'<path d="{path}" fill="none" stroke="#b88d55" stroke-width="5" stroke-dasharray="3 12" stroke-linecap="round" stroke-linejoin="round" opacity=".8"/>'
    # cutting areas
    for a in lay["areas"]:
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        out += f'<ellipse cx="{x}" cy="{y}" rx="{w / 2 + 12:g}" ry="{h / 2 + 10:g}" fill="#3f6a41" opacity=".55"/>'
        out += f'<ellipse cx="{x}" cy="{y}" rx="{w / 2:g}" ry="{h / 2:g}" fill="#b07f4a" stroke="#6e4a26" stroke-width="5"/>'
        out += f'<ellipse cx="{x}" cy="{y - h * 0.08:g}" rx="{w * 0.4:g}" ry="{h * 0.34:g}" fill="#c99a62" opacity=".7"/>'
        out += text(
            x - w * 0.3,
            y - h * 0.3,
            str(a["n"]),
            44,
            "#fff3d6",
            family=SERIF,
            extra=f' stroke="{INK}" stroke-width="1.5"',
        )
    # path locations
    for k, loc in sorted(lay["locations"].items(), key=lambda kv: int(kv[0])):
        n = int(k)
        kind, cap = kinds.get(n, ("token_spot", 1))
        if "w" in loc:
            w, h = loc["w"], loc["h"]
            out += box(loc["x"], loc["y"], w, h, "#f2e4bf", INK, 12, 0.92)
            label = (
                "" if kind == "token_spot" else title(kind.replace("planned_work", "planned work"))
            )
            if label:
                out += text(
                    loc["x"],
                    loc["y"] - h / 2 - 10,
                    label,
                    19,
                    INK,
                    family=SERIF,
                    extra=' stroke="#f7efd9" stroke-width="4" paint-order="stroke"',
                )
            cols = 2 if cap > 1 and w >= h * 0.7 else 1
            r = min(w / (2 * cols) - 6, h / (2 * ((cap + cols - 1) // cols) or 1) - 6, 24)
            if r >= 9:
                for i in range(cap):
                    cx = loc["x"] + ((i % cols) - (cols - 1) / 2) * 2 * (r + 5)
                    rows = (cap + cols - 1) // cols
                    cy = loc["y"] + (i // cols - (rows - 1) / 2) * 2 * (r + 4)
                    out += f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="#d9b887" stroke="{INK}" stroke-width="2.5" stroke-opacity=".6"/>'
            out += f'<circle cx="{loc["x"] - w / 2 + 14:g}" cy="{loc["y"] - h / 2 + 14:g}" r="14" fill="#b5532f" stroke="{INK}" stroke-width="3"/>'
            out += text(loc["x"] - w / 2 + 14, loc["y"] - h / 2 + 15, str(n), 16, "#fff")
        else:
            out += f'<circle cx="{loc["x"]}" cy="{loc["y"]}" r="22" fill="#b5532f" stroke="{INK}" stroke-width="4"/>'
            out += text(loc["x"], loc["y"] + 1, str(n), 22 if n < 10 else 19, "#fff")
        if "spot" in loc:
            sx, sy = loc["spot"]["x"], loc["spot"]["y"]
            out += f'<circle cx="{sx}" cy="{sy}" r="30" fill="#e7d6a8" stroke="{INK}" stroke-width="3.5" stroke-opacity=".75"/>'
            out += f'<circle cx="{sx}" cy="{sy}" r="22" fill="none" stroke="#b88d55" stroke-width="2.5" stroke-dasharray="4 5"/>'
            out += f'<path d="M{loc["x"]} {loc["y"]}L{sx} {sy}" stroke="{INK}" stroke-width="3" stroke-opacity=".5" marker-end="none"/>'
    s = lay["start"]
    out += box(s["x"], s["y"], s["w"], s["h"], "#b07f4a", INK, 14) + text(
        s["x"],
        s["y"] + s["h"] / 2 + 16,
        "Start",
        20,
        INK,
        family=SERIF,
        extra=' stroke="#f7efd9" stroke-width="4" paint-order="stroke"',
    )
    out += text(s["x"], s["y"], "0", 46, "#fff3d6", family=SERIF)
    out += text(
        (lay["turn"][0]["x"] + lay["turn"][-1]["x"]) / 2,
        lay["turn"][0]["y"] - 44,
        "Starting player",
        26,
        "#fff3d6",
        family=SERIF,
        extra=f' stroke="{INK}" stroke-width="1" font-style="italic"',
    )
    for i, p in enumerate(lay["turn"]):
        out += (
            f'<circle cx="{p["x"]}" cy="{p["y"]}" r="26" fill="#5aa469" stroke="{INK}" stroke-width="4"/>'
            + text(p["x"], p["y"] + 1, str(i + 1), 28, "#fff")
        )
    cl = lay["clearing"]
    out += f'<rect x="{cl[0]["x"] - 40:g}" y="{cl[0]["y"] - 36:g}" width="{cl[-1]["x"] - cl[0]["x"] + 80:g}" height="72" rx="36" fill="#f2e4bf" fill-opacity=".9" stroke="{INK}" stroke-width="3.5"/>'
    for c, p in zip("ABCD", cl, strict=True):
        out += (
            f'<circle cx="{p["x"]}" cy="{p["y"]}" r="24" fill="#a98558" stroke="{INK}" stroke-width="3.5"/>'
            + text(p["x"], p["y"] + 1, c, 26, "#fff3d6", family=SERIF)
        )
    out += text(
        (cl[0]["x"] + cl[-1]["x"]) / 2,
        cl[0]["y"] + 56,
        "Forest clearing",
        21,
        "#fff3d6",
        family=SERIF,
        extra=f' stroke="{INK}" stroke-width=".8" font-style="italic"',
    )
    out += trackers(lay)
    return out


def trackers(lay: dict[str, Any]) -> str:
    t = lay["trackers"]
    out = ""
    ph = t["phase"]
    xs = [r["x"] for r in ph.values() if r["w"] < 70 or True]
    y = ph["W1"]["y"]
    h = ph["W1"]["h"]
    x0, x1 = (
        min(r["x"] for k, r in ph.items() if k != "winter") - 40,
        max(r["x"] for k, r in ph.items() if k != "winter") + 40,
    )
    out += f'<rect x="{x0 - 110:g}" y="{y - h / 2 - 22:g}" width="{x1 - x0 + 130:g}" height="{h + 44:g}" rx="16" fill="#b07f4a" stroke="{INK}" stroke-width="4"/>'
    out += text(
        x0 - 55, y - 20, "Phase", 21, "#fff3d6", family=SERIF, extra=' font-style="italic"'
    ) + text(x0 - 55, y + 4, "track", 21, "#fff3d6", family=SERIF, extra=' font-style="italic"')
    for name, rect in t["legend"].items():
        out += box(
            rect["x"], rect["y"], rect["w"], rect["h"], SEASON_COLOR[name], INK, 5, 1, 2
        ) + text(
            rect["x"], rect["y"] + 1, name.capitalize(), 14, "#fff" if name != "summer" else INK
        )
    for i, (lab, gl) in enumerate(PHASE_W, 1):
        r = ph[f"W{i}"]
        out += box(r["x"], r["y"], r["w"], r["h"], PAPER, INK, 6, 1, 2.5) + text(
            r["x"], r["y"] - r["h"] * 0.38, str(i), 14, INK_SOFT
        )
        out += place(
            gl(), r["x"] - r["w"] / 2 + 6, r["y"] - r["h"] / 2 + 20, r["w"] - 12, r["h"] * 0.42
        ) + text(r["x"], r["y"] + r["h"] * 0.36, lab if len(lab) < 9 else lab.split()[0], 11, INK)
    wt = ph["winter"]
    out += box(wt["x"], wt["y"], wt["w"], wt["h"], SEASON_COLOR["winter"], INK, 6, 1, 2.5) + text(
        wt["x"], wt["y"] + 1, "Winter", 16, "#fff"
    )
    for i, (lab, gl) in enumerate(PHASE_N, 1):
        r = ph[f"N{i}"]
        out += box(r["x"], r["y"], r["w"], r["h"], "#e2ecf5", INK, 6, 1, 2.5) + text(
            r["x"], r["y"] - r["h"] * 0.38, str(i), 14, INK_SOFT
        )
        out += place(
            gl(), r["x"] - r["w"] / 2 + 6, r["y"] - r["h"] / 2 + 20, r["w"] - 12, r["h"] * 0.42
        ) + text(r["x"], r["y"] + r["h"] * 0.36, lab, 11, INK)
    del xs
    # planned work and season rounds (right column)
    se = t["season"]
    sx = se["1"]["x"]
    top = se["1"]["y"] - 92
    bot = se["8"]["y"] + 62
    out += f'<rect x="{sx - 160:g}" y="{top:g}" width="{200:g}" height="{bot - top:g}" rx="16" fill="#b07f4a" stroke="{INK}" stroke-width="4"/>'
    out += text(
        sx - 60, top + 22, "Planned Work", 26, "#fff3d6", family=SERIF, extra=' font-style="italic"'
    )
    names = ("spring", "summer", "fall", "winter")
    for n in range(1, 9):
        r = se[str(n)]
        s = names[(n - 1) % 4]
        out += box(sx - 82, r["y"], 76, 46, SEASON_COLOR[s], INK, 7, 1, 2.5) + text(
            sx - 82, r["y"] + 1, s.capitalize(), 19, "#fff" if s != "summer" else INK, family=SERIF
        )
        out += box(sx, r["y"], 70, 46, "#f2e4bf", INK, 7, 0.95, 2.5) + text(
            sx, r["y"] + 1, f"R{n}", 15, INK_SOFT, "normal"
        )
    for yr, ry in ((1, se["1"]["y"] - 38), (2, se["5"]["y"] - 42)):
        out += text(sx - 118, ry, f"Year {yr}", 17, "#fff3d6", family=SERIF, anchor="start")
    out += text(
        sx - 60, bot - 18, "Final sale", 17, "#fff3d6", family=SERIF, extra=' font-style="italic"'
    )
    # card areas
    cd = t["cards"]
    for key, lab, col in (
        ("tasks", "Tasks", "#4f8c58"),
        ("pw", "Planned work", "#c8a43a"),
        ("buildings", "Buildings", "#8a6a3b"),
    ):
        r = cd[key]
        out += box(r["x"], r["y"], r["w"] + 14, r["h"] + 14, "#f2e4bf", col, 10, 0.55, 5)
        out += text(
            r["x"],
            r["y"] - r["h"] / 2 - 18,
            lab,
            17,
            INK,
            family=SERIF,
            extra=' stroke="#f7efd9" stroke-width="4" paint-order="stroke"',
        )
    return out


def sale_prices(setup: dict[str, Any], x: float, y: float, w: float) -> str:
    """Per-kind base prices (data wood_prices, R-058) printed in the lower part of the sale area."""
    pw = w + 100
    out = f'<rect x="{x - pw / 2:g}" y="{y + 8:g}" width="{pw:g}" height="{135:g}" rx="14" fill="#f7efd9" fill-opacity=".95" stroke="{INK}" stroke-width="4"/>'
    c_milled, c_un = x + 22, x + pw / 2 - 14  # right edges of the two price columns
    out += text(
        x - pw / 2 + 12, y + 32, "Sale price", 17, INK_SOFT, "normal", anchor="start", family=SERIF
    )
    out += text(c_milled, y + 32, "milled", 17, INK_SOFT, "normal", anchor="end", family=SERIF)
    out += text(c_un, y + 32, "unmilled", 17, INK_SOFT, "normal", anchor="end", family=SERIF)
    for i, (kind, p) in enumerate(setup["wood_prices"].items()):
        un = "-" if p["unmilled"] is None else f"${p['unmilled']}"
        yy = y + 66 + i * 31
        out += text(x - pw / 2 + 12, yy, title(kind), 24, INK, anchor="start", family=SERIF)
        out += text(c_milled, yy, f"${p['milled']}", 24, INK, anchor="end")
        out += text(c_un, yy, un, 24, INK, anchor="end")
    return out


def pad_regions(key: str) -> str:
    """Labelled panels at the spots in web/.../board/sawmillLayout.json (sawmill / extension)."""
    cols = {
        "fodder": "#d6a93a", "hired": "#c0392b", "mill": "#c0392b", "huts": "#6b5b45", "food": "#4f9a4f",
        "equip": "#8a6a3b", "craft": "#c8683a", "river": "#4f86c6", "store": "#6f7f8a", "sawing": "#8e969c",
        "sale": "#8a5a2b", "dry1": "#8a5a2b", "dry2": "#8a5a2b", "dry3": "#8a5a2b",
        "joinery": "#c9a22a", "buildings": "#8a5a2b", "building_slot_1": "#8a5a2b", "building_slot_2": "#8a5a2b",
        "small_storage": "#6b5b45",
    }  # fmt: skip
    out = ""
    setup = load("setup.yaml")
    for name, r in json.loads(PAD_LAYOUT.read_text())[key + "_generic"]["regions"].items():
        if key == "extension" and name == "buildings":
            continue  # the slots below carry the frames; this region is their union
        col = cols.get(name, INK_SOFT)
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        lab = r["label"]
        size = 24 if w >= 180 else 18
        lines = wrap(lab, max(6, int(w / (size * 0.5))))
        if name == "small_storage":
            out += f'<rect x="{x - w / 2:g}" y="{y - h / 2:g}" width="{w}" height="{h}" rx="22" fill="#f2e4bf" fill-opacity=".9" stroke="{col}" stroke-width="9" stroke-dasharray="26 14"/>'
            continue
        out += f'<rect x="{x - w / 2:g}" y="{y - h / 2:g}" width="{w}" height="{h}" rx="22" fill="#f2e4bf" fill-opacity=".9" stroke="{col}" stroke-width="9"/>'
        out += f'<rect x="{x - w / 2 + 12:g}" y="{y - h / 2 + 12:g}" width="{w - 24}" height="{h - 24}" rx="14" fill="none" stroke="{INK}" stroke-opacity=".2" stroke-width="2"/>'
        for j, seg in enumerate(lines):
            out += text(
                x,
                y - h / 2 + 30 + j * size * 1.15,
                seg,
                size,
                INK,
                family=SERIF,
                extra=' font-style="italic"',
            )
        if name == "sale":
            out += sale_prices(setup, x, y + h / 2, w)
        if name in ("dry1", "dry2", "dry3"):
            bonus = setup["drying_bonuses"][f"drying_{name[3]}"]
            if bonus:
                out += text(
                    x,
                    y + h / 2 + 34,
                    f"+{bonus}",
                    56,
                    "#fff3d6",
                    family=SERIF,
                    extra=f' stroke="{INK}" stroke-width="5" paint-order="stroke"',
                )
        gl = {
            "fodder": g_wheat,
            "food": g_cube,
            "mill": lambda: meeple("#c0392b"),
            "hired": lambda: meeple("#c0392b"),
            "huts": g_hut,
            "river": g_raft,
            "sawing": g_saw,
            "equip": g_wagon,
            "craft": g_reed,
        }.get(name)
        if gl and min(w, h) > 90:
            s = min(w, h) * 0.3
            out += f'<g opacity=".28">{place(gl(), x - s / 2, y + h * 0.05, s, s)}</g>'
    return out


def board(
    w: int, h: int, label: str, side: str | None = None, pad: str | None = None, seed: int = 7
) -> str:
    body = scenery(w, h, seed)
    body += dark_overlay(w, h) if False else ""
    if side:
        body += regions(side)
        body += text(
            230,
            82,
            "Lignum",
            72,
            "#f3c872",
            family=SERIF,
            extra=f' font-style="italic" stroke="{INK}" stroke-width="3" paint-order="stroke"',
        )
        if side == "joinery":
            body += text(
                230,
                128,
                "Joinery & Buildings",
                28,
                "#fff3d6",
                family=SERIF,
                extra=' font-style="italic"',
            )
    if pad:
        body += pad_regions(pad)
        if label:
            hh = 100 if pad == "sawmill" else 70
            if pad == "sawmill":
                body += f'<rect x="{w * 0.36:g}" y="20" width="{w * 0.3:g}" height="{hh - 20}" rx="38" fill="#c18a4a" stroke="{INK}" stroke-width="6"/><ellipse cx="{w * 0.36 + 6:g}" cy="{hh / 2 + 10:g}" rx="22" ry="{(hh - 20) / 2:g}" fill="#e8c98f" stroke="{INK}" stroke-width="5"/>'
                body += text(
                    w * 0.51,
                    52,
                    label,
                    54,
                    "#fff3d6",
                    family=SERIF,
                    extra=f' font-style="italic" stroke="{INK}" stroke-width="2" paint-order="stroke"',
                )
            else:
                body += f'<rect x="{w * 0.1:g}" y="14" width="{w * 0.8:g}" height="60" rx="26" fill="#c18a4a" stroke="{INK}" stroke-width="5"/>'
                body += text(
                    w / 2,
                    46,
                    label,
                    40,
                    "#fff3d6",
                    family=SERIF,
                    extra=f' font-style="italic" stroke="{INK}" stroke-width="2" paint-order="stroke"',
                )
    body += f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="24" fill="none" stroke="{INK}" stroke-width="8"/>'
    body += dark_overlay(w, h)
    return svg(w, h, body, DARK_STYLE)


# ---------------------------------------------------------------- manifest assembly
# (id, category, alt, w, h, svg)
Entry = tuple[str, str, str, int, int, str]


def official_entries() -> list[dict[str, Any]]:
    if not OFFICIAL.exists():
        return []
    assets: list[dict[str, Any]] = json.loads(OFFICIAL.read_text())["assets"]
    return assets


def data_cards() -> dict[str, str]:
    """Sprite id -> card face svg, rendered from the component data."""
    cards = load("cards.yaml")
    out: dict[str, str] = {}
    for c in cards["tasks"]:
        out[c["id"].replace("_", "-")] = task_card(c)
    for c in cards["placement"]:
        out[c["id"].replace("_", "-")] = placement_card(c)
    for c in cards["winter"]:
        out[c["id"].replace("_", "-")] = winter_card(c)
    for c in load("planned_work.yaml")["planned_work"]:
        out[c["id"].replace("_", "-")] = pw_card(c)
    out["loan"] = loan_card(True)
    out["loan-back"] = loan_card(False)
    return out


def render_official(e: dict[str, Any], faces: dict[str, str]) -> Entry:
    i, cat = e["id"], e["category"]
    w, h = e.get("width") or 0, e.get("height") or 0
    alt = e.get("alt") or title(i)
    if i == "board":
        s = board(w, h, "", "base", seed=3)
    elif i == "board-joinery":
        s = board(w, h, "", "joinery", seed=5)
    elif i == "player-extension":
        s = board(w, h, "Joinery & Buildings", pad="extension", seed=11)
    elif i == "sawmill" or i == "sawmill-plain":
        s = board(w, h, "Sawmill", pad="sawmill", seed=17)
    elif i == "woodpile":
        s = woodpile(w, h)
    elif i == "lignum":  # sprite sheet: unused by the generic theme, kept so the id resolves
        w, h = 64, 64
        s = icon(w, h, "joker")
    elif i.startswith("icon-"):
        s = icon(w, h, i[5:])
    elif i.startswith("coin-"):
        s = coin(w, i[5:])
    elif i == "pw-token":
        s = token_disc(w, "#d2a86b", text(w / 2, w / 2 + 2, "PW", w * 0.3, INK, family=SERIF))
    elif i.startswith("cutting-token"):
        s = cutting_token(w, h, i.endswith("front"))
    elif i in faces:
        s = card_svg_for(i, faces)
    elif i.startswith("craftwork-"):
        s = craft_tile(w, h, i[10:])
    elif cat == "buildings":
        s = building_tile(building_data(i[9:]))
    else:
        s = card_svg(card_frame(cat, title(i)))
    return i, cat, alt, w, h, s


def card_svg_for(i: str, faces: dict[str, str]) -> str:
    return faces[i]


def building_data(bid: str) -> dict[str, Any]:
    for b in load("buildings.yaml")["buildings"]:
        if b["id"] == bid:
            return b
    return {"id": bid, "name": title(bid), "params": {}}


def official_size(i: str, default: tuple[int, int]) -> tuple[int, int]:
    for e in official_entries():
        if e["id"] == i and e.get("width"):
            return int(e["width"]), int(e["height"])
    return default


def extra_entries() -> list[Entry]:
    out: list[Entry] = [
        (
            "board-joinery",
            "boards",
            "Joinery board",
            1600,
            1061,
            board(1600, 1061, "", "joinery", seed=5),
        ),
        (
            "player-extension",
            "boards",
            "Player board extension",
            800,
            1476,
            board(800, 1476, "Joinery & Buildings", pad="extension", seed=11),
        ),
        (
            "foreman",
            "tokens",
            "Foreman marker",
            *official_size("foreman", (62, 112)),
            pawn("#5b5b5b", "F", *official_size("foreman", (62, 112))),
        ),
    ]
    for n, c in enumerate(SEATS):
        w, h = official_size(f"pawn-{n}", (62, 112))
        out.append((f"pawn-{n}", "tokens", f"Seat P{n} pawn", w, h, pawn(c, str(n), w, h)))
    for k, c in WORKERS.items():
        w, h = official_size(f"worker-{k}", (96, 84))
        out.append((f"worker-{k}", "tokens", f"{title(k)} meeple", w, h, worker(c, w, h)))
    for n, c in enumerate(SEATS):
        w, h = official_size(f"mill-worker-{n}", (96, 84))
        out.append(
            (f"mill-worker-{n}", "tokens", f"Seat P{n} mill worker", w, h, worker(c, w, h, "M"))
        )
    for k in WOOD:
        w, h = official_size(f"piece-{k}-disk", (76, 46))
        # Disk sprite = unmilled (labelled "Log"); log (beam) sprite = milled (labelled "Milled").
        out.append((f"piece-{k}-disk", "tokens", f"{title(k)} log", w, h, disk_sprite(w, h, k)))
        w, h = official_size(f"piece-{k}-log", (76, 46))
        out.append((f"piece-{k}-log", "tokens", f"{title(k)} milled", w, h, log_sprite(w, h, k)))
    for b in load("buildings.yaml")["buildings"]:
        out.append((f"building-{b['id']}", "buildings", b["name"], 192, 192, building_tile(b)))
    for k in ("back", *CRAFT):
        w, h = official_size(f"craftwork-{k}", (96, 96))
        out.append((f"craftwork-{k}", "craftwork", f"Craftwork {k}", w, h, craft_tile(w, h, k)))
    return out


def build() -> tuple[dict[str, str], dict[str, Any]]:
    """Return ({relative path: svg text}, manifest)."""
    faces = data_cards()
    extras = {e[0]: e for e in extra_entries()}
    boards = {"board-joinery", "player-extension"}
    official = official_entries()
    entries = [
        render_official(e, faces) for e in official if e["id"] not in extras or e["id"] in boards
    ]
    have: set[str] = {e[0] for e in entries}
    if not official:  # no official manifest: cover the icon set we know about
        entries = [
            (f"icon-{k}", "tokens", title(k), *sz, icon(*sz, k)) for k, sz in ICON_SIZE.items()
        ]
        have = set[str]()
    for i, (_, cat, alt, w, h, s) in extras.items():
        if i in have:
            continue
        entries.append((i, cat, alt, w, h, s))
    files: dict[str, str] = {}
    assets: list[dict[str, Any]] = []
    for i, cat, alt, w, h, s in sorted(entries, key=lambda e: (e[1], e[0])):
        rel = f"{cat}/{i}.svg"
        files[rel] = s
        assets.append({"id": i, "category": cat, "alt": alt, "file": rel, "width": w, "height": h})
    manifest: dict[str, Any] = {
        "copyright": "Original flat vector art; no third-party material (PLAN.md D11, D21).",
        "note": "Generated by tools/make_generic_theme.py; do not edit by hand.",
        "assets": assets,
    }
    return files, manifest


def write(out: Path) -> None:
    files, manifest = build()
    for rel, s in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    write(ap.parse_args(argv).out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
