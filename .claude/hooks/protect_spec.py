#!/usr/bin/env python3
"""PreToolUse guard: block changes to docs/RULES_SPEC.md while its Status is APPROVED.

The user unlocks the spec by changing its Status line to AMENDING (and back to APPROVED after).
Covers Edit/Write on the file, Bash commands that write, move or delete it, and git commands that
could revert or replace it wholesale (broad checkout/restore, reset --hard, stash, clean, merge,
pull, rebase, cherry-pick, revert, am).

Bash is judged per segment (split on `&&`, `||`, `;`, `|`, newlines and subshells): a segment is a
write only if its own command is a writer (rm, mv, cp, tee, sed -i, python, ...) and that same
segment names the spec, a glob matching it, or a directory containing it. Read-only commands that
merely mention the spec (`grep R-012 docs/RULES_SPEC.md && rm tests/x.py`) are allowed; this fixes
the kingisdead Phase 1 false positive.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_REL = "docs/RULES_SPEC.md"
SPEC_ABS = ROOT / SPEC_REL
STATUS_APPROVED = re.compile(r"^\*\*Status:\*\*\s*APPROVED\b", re.MULTILINE)
SPEC_REDIRECT = re.compile(r">\s*\S*RULES_SPEC")
# Commands that write their file arguments whenever they run.
WRITERS = {
    "tee", "mv", "cp", "rm", "truncate", "dd", "install", "ln", "rsync", "patch", "unlink",
    "shred", "python", "python3", "bash", "sh", "zsh",
}  # fmt: skip
# Commands that write only with an in-place flag.
IN_PLACE = re.compile(r"^(?:-[A-Za-z]*i\S*|--in-place\S*)$")
WRAPPERS = {"env", "sudo", "time", "command", "nice", "nohup", "exec", "xargs"}
# History-rewriting git commands that can replace the spec with another revision's copy.
GIT_HISTORY = {"merge", "pull", "rebase", "cherry-pick", "revert", "am", "apply"}
SPEC_DIRS = {"docs", "."}
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n()`]|\$\(")
# Interpreter code (`python -c "open(...)"`) contains parentheses, so judge it on a coarser split.
COARSE_SPLIT = re.compile(r"&&|\|\||[;|\n]")
INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "perl", "node"}
GIT_GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree"}
MESSAGE = (
    "docs/RULES_SPEC.md is APPROVED and locked. Don't change it. Propose the amendment to the user "
    "instead: rule ID, current text, proposed text, and why. Only the user unlocks it, by setting "
    "its Status line to AMENDING. (git merge/pull/rebase/cherry-pick/revert/am/apply are blocked "
    "too while the spec is locked, since they can replace it; ask the user to run them.)"
)


def spec_locked() -> bool:
    try:
        head = SPEC_ABS.read_text(encoding="utf-8")[:4000]
    except FileNotFoundError:
        return False
    return STATUS_APPROVED.search(head) is not None


def mentions_spec(command: str) -> bool:
    """True if the command names the spec, directly or through a glob that would match it."""
    if "RULES_SPEC" in command:
        return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if not any(char in token for char in "*?["):
            continue
        normalized = token.removeprefix("./")
        if fnmatch.fnmatch(SPEC_REL, normalized) or fnmatch.fnmatch("RULES_SPEC.md", normalized):
            return True
        if fnmatch.fnmatch(SPEC_REL, normalized.rstrip("/") + "/*"):
            return True
    return False


def broad_pathspec(token: str) -> bool:
    """A pathspec wide enough to cover the spec: `.`, `docs`, `docs/...`, a glob, `:/`."""
    normalized = token.removeprefix("./").rstrip("/")
    return (
        token in {".", "./", "..", ":/", ":/*"}
        or normalized == "docs"
        or normalized.startswith("docs/")
        or any(char in token for char in "*?[")
        or normalized.endswith("RULES_SPEC.md")
    )


def git_command(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Return (subcommand, args) if the segment runs git."""
    index = 0
    while index < len(tokens) and (
        tokens[index] in {"env", "sudo", "time", "command"} or "=" in tokens[index]
    ):
        index += 1
    if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
        return None
    index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GIT_GLOBAL_WITH_VALUE else 1
    if index >= len(tokens):
        return None
    return tokens[index], tokens[index + 1 :]


def git_reverts_spec(sub: str, args: list[str]) -> bool:
    if sub == "clean" or (sub == "reset" and "--hard" in args) or sub in GIT_HISTORY:
        return True
    if sub in {"rm", "mv"}:
        return any(broad_pathspec(a) for a in args if not a.startswith("-"))
    if sub == "stash":
        return not args or args[0] not in {"list", "show"}
    if sub not in {"checkout", "restore", "switch"}:
        return False
    if any(a in {"-f", "--force", "--discard-changes"} for a in args):
        return True
    if sub == "switch":
        return False
    paths = [a for a in args if not a.startswith("-")]
    if any(broad_pathspec(a) for a in paths):
        return True
    if sub == "restore":
        # `git restore --source=<rev> <path>`: pulling files from another revision.
        return bool(paths) and any(a.startswith("--source") or a == "-s" for a in args)
    # `git checkout <rev> -- <path>`: branch-to-path form.
    if "--" in args:
        before, after = args[: args.index("--")], args[args.index("--") + 1 :]
        return bool(after) and any(not a.startswith("-") for a in before)
    return False


def leading_command(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Return (command basename, args) for a segment, skipping wrappers and VAR=value prefixes."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in WRAPPERS or ("=" in token and not token.startswith("-")):
            index += 1
        elif token == "uv" and index + 1 < len(tokens) and tokens[index + 1] == "run":
            index += 2
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
        else:
            break
    if index >= len(tokens):
        return None
    return os.path.basename(tokens[index]), tokens[index + 1 :]


def names_spec_dir(args: list[str]) -> bool:
    """True if an argument is a directory that contains the spec (`docs`, `.`, the repo root)."""
    for arg in args:
        normalized = arg.removeprefix("./").rstrip("/") or "."
        if normalized in SPEC_DIRS or arg in {str(ROOT), str(ROOT) + "/", str(ROOT / "docs")}:
            return True
    return False


def segment_writes_spec(tokens: list[str], segment: str) -> bool:
    found = leading_command(tokens)
    if found is None:
        return False
    command, args = found
    if command in {"sed", "perl"}:
        writer = any(IN_PLACE.match(a) for a in args)
    elif command == "find":
        writer = any(a in {"-delete", "-exec", "-execdir", "-ok"} for a in args)
    else:
        writer = command in WRITERS
    if not writer:
        return False
    if mentions_spec(segment):
        return True
    # A recursive delete/move/sync of a directory holding the spec also removes it.
    return command in {"rm", "mv", "rsync", "find", "shred"} and names_spec_dir(args)


def bash_writes_spec(command: str) -> bool:
    if SPEC_REDIRECT.search(command):
        return True
    for segment in SEGMENT_SPLIT.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        git = git_command(tokens)
        if git is not None:
            if git_reverts_spec(*git):
                return True
            continue
        if segment_writes_spec(tokens, segment):
            return True
    for segment in COARSE_SPLIT.split(command):
        found = leading_command(segment.split())
        if found is not None and found[0] in INTERPRETERS and mentions_spec(segment):
            return True
    return False


def targets_spec(tool_name: str, tool_input: dict[str, object]) -> bool:
    if tool_name in ("Edit", "Write"):
        path = str(tool_input.get("file_path", ""))
        if not path:
            return False
        return (ROOT / path).resolve() == SPEC_ABS.resolve()
    if tool_name == "Bash":
        return bash_writes_spec(str(tool_input.get("command", "")))
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    if targets_spec(payload.get("tool_name", ""), tool_input) and spec_locked():
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
