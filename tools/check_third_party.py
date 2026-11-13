"""Report tracked binary assets that live outside the allowed directories (PLAN.md D11, D21).

Official art is welcome in this project (D21), so this check is advisory: it lists images, PDFs
and fonts tracked outside ``third_party/`` and ``assets/generic/`` so the pre-public scrub
(``git filter-repo --path third_party --invert-paths``) stays a single command. Exit code is 0
unless ``--strict`` is given.

Usage: ``uv run python -m tools.check_third_party [--strict]``
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable

ASSET_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg", ".pdf",
    ".ttf", ".otf", ".woff", ".woff2",
)  # fmt: skip
ALLOWED_PREFIXES = ("third_party/", "assets/generic/")


def stray_assets(paths: Iterable[str]) -> list[str]:
    """Return the asset paths that are outside the allowed directories."""
    return sorted(
        p
        for p in paths
        if p.lower().endswith(ASSET_SUFFIXES) and not p.startswith(ALLOWED_PREFIXES)
    )


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True, text=True)
    return [p for p in out.stdout.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report tracked assets outside third_party/ and assets/generic/."
    )
    parser.add_argument("--strict", action="store_true", help="exit 1 if any stray asset is found")
    args = parser.parse_args(argv)
    stray = stray_assets(tracked_files())
    if not stray:
        print("third-party check: all tracked assets are under third_party/ or assets/generic/")
        return 0
    for path in stray:
        # GitHub Actions renders this as a warning annotation; plain text elsewhere.
        print(f"::warning file={path}::asset outside third_party/ and assets/generic/ (D11)")
    print(f"third-party check: {len(stray)} asset(s) outside the allowed directories")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
