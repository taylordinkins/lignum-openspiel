"""Offline tests for tools/fetch_assets.py (PLAN.md §5.6): parsing, naming, manifest, reruns."""

import json
from pathlib import Path

import pytest

from tools import fetch_assets as fa

FIXTURE = (Path(__file__).parent / "fixtures" / "cards_page.html").read_text(encoding="utf-8")


class FakeFetch:
    def __init__(self, content_type: str = "image/webp") -> None:
        self.calls: list[str] = []
        self.content_type = content_type

    def __call__(self, url: str) -> tuple[bytes, str]:
        self.calls.append(url)
        return url.encode(), self.content_type


def run(out: Path, fetch: FakeFetch, **kwargs: bool) -> fa.Result:
    return fa.fetch_assets(out, fetch=fetch, html=FIXTURE, pause=0, log=lambda _: None, **kwargs)


def test_parse_page_keeps_card_sections_only() -> None:
    refs = fa.parse_page(FIXTURE)
    assert [r.alt for r in refs] == [
        "Game board", "Task card 1", "Task card 3", "Elsewhere", "Saw", "Raft",
    ]  # fmt: skip
    assert refs[4].url == "https://www.ludex.dev/icon-sprites/lignum.webp"
    assert refs[4].fragment == "icon-saw"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://img.ludex.dev/_astro/task-03.VX_wPkSg_5m1D.webp", ("task-03", "webp")),
        ("https://img.ludex.dev/_astro/cutting-token-back._I4H2MUD_Z16s9Wv.webp",
         ("cutting-token-back", "webp")),
        ("https://www.ludex.dev/icon-sprites/lignum.webp", ("lignum", "webp")),
    ],
)  # fmt: skip
def test_local_name_strips_content_hash(url: str, expected: tuple[str, str]) -> None:
    assert fa.local_name(url) == expected


@pytest.mark.parametrize(
    "url", ["https://img.ludex.dev/../../etc/passwd", "https://img.ludex.dev/x/.hidden.webp",
            "https://img.ludex.dev/a/script.js"]
)  # fmt: skip
def test_local_name_rejects_unsafe_names(url: str) -> None:
    with pytest.raises(ValueError):
        fa.local_name(url)


def test_fetch_writes_files_and_manifest(tmp_path: Path) -> None:
    fetch = FakeFetch()
    result = run(tmp_path, fetch)
    assert result.downloaded == 4  # board, two tasks, one sprite sheet; foreign host skipped
    assert not any("evil.example" in c for c in fetch.calls)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    files = [a["file"] for a in manifest["assets"]]
    assert files == ["boards/board.webp", "sprites/lignum.webp", "tasks/task-01.webp",
                     "tasks/task-03.webp"]  # fmt: skip
    task = next(a for a in manifest["assets"] if a["id"] == "task-01")
    assert task["url"].endswith("task-01.EBnVkYb0_ZcAtWw.webp")
    assert task["sha256"] == fa.sha256(task["url"].encode())
    assert (tmp_path / "tasks" / "task-01.webp").read_bytes() == task["url"].encode()
    assert manifest["sprites"] == [
        {"id": "icon-saw", "alt": "Saw", "sheet": "sprites/lignum.webp",
         "object_position": "10% 0", "aspect_ratio": "73/64"},
        {"id": "icon-raft", "alt": "Raft", "sheet": "sprites/lignum.webp",
         "object_position": "20% 0", "aspect_ratio": "70/64"},
    ]  # fmt: skip


def test_second_run_skips_unchanged_and_refetches_tampered(tmp_path: Path) -> None:
    run(tmp_path, FakeFetch())
    before = (tmp_path / "manifest.json").read_text()
    again = FakeFetch()
    assert run(tmp_path, again).downloaded == 0
    assert again.calls == []
    assert (tmp_path / "manifest.json").read_text() == before
    (tmp_path / "tasks" / "task-03.webp").write_bytes(b"corrupt")
    repair = FakeFetch()
    assert run(tmp_path, repair).downloaded == 1
    assert run(tmp_path, FakeFetch(), force=True).downloaded == 4


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    fetch = FakeFetch()
    result = run(tmp_path, fetch, dry_run=True)
    assert result.planned == 4 and fetch.calls == []
    assert not any(tmp_path.iterdir())


def test_non_image_response_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not an image"):
        run(tmp_path, FakeFetch(content_type="text/html"))
