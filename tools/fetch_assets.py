"""Download the official Lignum card and component images from ludex.dev into third_party/art/.

PLAN.md §5.6 and D11: the images are © Capstone Games; they live only under ``third_party/`` so
one command removes them before the repository goes public. Every image is recorded in
``third_party/art/manifest.json`` with its section, alt text, source URL, size and sha256.

The page groups images under section headings (boards, planned-work cards, task cards, ...); each
becomes a subdirectory. Icon images that point into a sprite sheet (``lignum.webp#icon-saw``) are
recorded as sprite entries with their CSS position, and the sheet is downloaded once.

Polite by design: one request at a time with a pause between them, a descriptive User-Agent, only
https URLs on ludex.dev hosts, and files already present with the recorded hash are skipped.

    uv run python -m tools.fetch_assets             # fetch what's missing
    uv run python -m tools.fetch_assets --dry-run   # list what would be fetched
    uv run python -m tools.fetch_assets --force     # re-download everything
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlsplit

SOURCE_PAGE = "https://www.ludex.dev/lignum/cards/"
ALLOWED_HOSTS = {"www.ludex.dev", "ludex.dev", "img.ludex.dev"}
USER_AGENT = "lignum-asset-fetch/0.1 (+https://github.com/taylordinkins/lignum; private research)"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "third_party" / "art"
PAUSE_SECONDS = 0.5
MAX_BYTES = 20 * 1024 * 1024

# Page section ids -> local directory names.
SECTION_DIRS = {
    "boards": "boards",
    "planned-work-cards": "planned_work",
    "task-cards": "tasks",
    "placement-cards": "placement",
    "winter-cards": "winter",
    "loan-card": "loan",
    "tiles": "tiles",
    "tokens--pieces": "tokens",
    "icons": "icons",
}
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
IMAGE_EXTENSIONS = {"webp", "png", "jpg", "jpeg", "gif", "svg", "avif"}

Fetch = Callable[[str], tuple[bytes, str]]


@dataclass(frozen=True)
class ImageRef:
    """One image on the page: a standalone file, or a position in a sprite sheet."""

    section: str
    alt: str
    url: str
    fragment: str = ""
    width: int | None = None
    height: int | None = None
    style: str = ""


class CardsPageParser(HTMLParser):
    """Collect <img> tags, tagged with the id of the most recent <h2>/<h3> heading."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.section = ""
        self.images: list[ImageRef] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: v or "" for k, v in attrs}
        if tag in ("h2", "h3") and values.get("id"):
            self.section = values["id"]
        elif tag == "img" and values.get("src") and self.section in SECTION_DIRS:
            url, _, fragment = urljoin(self.base_url, values["src"]).partition("#")
            self.images.append(
                ImageRef(
                    section=self.section,
                    alt=values.get("alt", ""),
                    url=url,
                    fragment=fragment,
                    width=_int(values.get("width")),
                    height=_int(values.get("height")),
                    style=values.get("style", ""),
                )
            )


def _int(text: str | None) -> int | None:
    return int(text) if text and text.isdigit() else None


def parse_page(html: str, base_url: str = SOURCE_PAGE) -> list[ImageRef]:
    parser = CardsPageParser(base_url)
    parser.feed(html)
    return parser.images


def allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS


def local_name(url: str) -> tuple[str, str]:
    """(stem, extension) for a URL without Astro's hash: `task-01.EBnV_Zc.webp` -> task-01."""
    filename = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    stem, _, rest = filename.partition(".")
    ext = rest.rsplit(".", 1)[-1] if rest else ""
    if not SAFE_NAME.match(stem) or ext not in IMAGE_EXTENSIONS:
        raise ValueError(f"unexpected image file name in {url!r}")
    return stem, ext


def sprite_css(style: str) -> dict[str, str]:
    """Pull the sprite position and aspect ratio out of an inline style."""
    found: dict[str, str] = {}
    for prop in ("object-position", "aspect-ratio"):
        match = re.search(rf"{prop}\s*:\s*([^;]+)", style)
        if match:
            found[prop.replace("-", "_")] = match.group(1).strip()
    return found


def http_fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (https only)
        body = cast(bytes, response.read(MAX_BYTES + 1))
        content_type = str(response.headers.get("Content-Type", ""))
    if len(body) > MAX_BYTES:
        raise ValueError(f"{url} is larger than {MAX_BYTES} bytes")
    return body, content_type


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Result:
    downloaded: int = 0
    skipped: int = 0
    planned: int = 0


def fetch_assets(
    out_dir: Path,
    fetch: Fetch = http_fetch,
    html: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    pause: float = PAUSE_SECONDS,
    log: Callable[[str], None] = print,
) -> Result:
    """Fetch every image on the cards page into ``out_dir`` and write ``manifest.json``."""
    if html is None:
        body, _ = fetch(SOURCE_PAGE)
        html = body.decode("utf-8")
    refs = parse_page(html)
    manifest_path = out_dir / "manifest.json"
    previous = {a["file"]: a for a in load_manifest(manifest_path).get("assets", [])}

    assets: list[dict[str, Any]] = []
    sprites: list[dict[str, Any]] = []
    seen_files: dict[str, str] = {}
    result = Result()

    for ref in refs:
        if not allowed_url(ref.url):
            log(f"skip (host not allowed): {ref.url}")
            continue
        stem, ext = local_name(ref.url)
        directory = "sprites" if ref.fragment else SECTION_DIRS[ref.section]
        rel = f"{directory}/{stem}.{ext}"
        if ref.fragment:
            sprites.append(
                {
                    "id": ref.fragment,
                    "alt": ref.alt,
                    "sheet": rel,
                    **sprite_css(ref.style),
                }
            )
        if rel in seen_files:
            if seen_files[rel] != ref.url:
                raise ValueError(f"two different URLs map to {rel}")
            continue
        seen_files[rel] = ref.url

        entry: dict[str, Any] = {
            "id": stem,
            "category": directory,
            "alt": "" if ref.fragment else ref.alt,
            "file": rel,
            "url": ref.url,
            "width": ref.width,
            "height": ref.height,
        }
        target = out_dir / rel
        old = previous.get(rel)
        if (
            not force
            and old is not None
            and old.get("url") == ref.url
            and target.is_file()
            and sha256(target.read_bytes()) == old.get("sha256")
        ):
            entry.update(sha256=old["sha256"], bytes=old["bytes"])
            assets.append(entry)
            result.skipped += 1
            continue
        if dry_run:
            log(f"would fetch {ref.url} -> {rel}")
            result.planned += 1
            continue
        if result.downloaded:
            time.sleep(pause)
        data, content_type = fetch(ref.url)
        if not content_type.startswith("image/"):
            raise ValueError(f"{ref.url} returned {content_type!r}, not an image")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry.update(sha256=sha256(data), bytes=len(data))
        assets.append(entry)
        result.downloaded += 1
        log(f"fetched {rel} ({len(data)} bytes)")

    # Entries made by tools/prep_photos.py (a `source` photo instead of a `url`) are kept.
    # (tools/prep_art.py aliases may share a fetched file, so match on id, not file.)
    have = {a["id"] for a in assets}
    local = [a for a in load_manifest(manifest_path).get("assets", []) if "source" in a]
    assets.extend(a for a in local if a["id"] not in have)

    if not dry_run:
        manifest = {
            "source_page": SOURCE_PAGE,
            "copyright": "© Capstone Games. Private development use only (PLAN.md D11).",
            "note": "Written by tools/fetch_assets.py; do not edit by hand.",
            "assets": sorted(assets, key=lambda a: a["file"]),
            "sprites": sprites,
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch official Lignum art from ludex.dev.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="default: third_party/art")
    parser.add_argument("--dry-run", action="store_true", help="list downloads, write nothing")
    parser.add_argument("--force", action="store_true", help="re-download files already present")
    args = parser.parse_args(argv)
    result = fetch_assets(args.out, dry_run=args.dry_run, force=args.force)
    print(
        f"downloaded {result.downloaded}, unchanged {result.skipped}"
        + (f", would fetch {result.planned}" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
