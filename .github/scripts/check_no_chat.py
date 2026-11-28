"""No chat in the repository: tracked text never quotes a conversation or cites who decided.

Code, config, comments, tests, scripts and docs say what the code does and why in technical
terms. They never hold a quote of a chat (in any language), an approval or decision attributed
to a person with its date ("owner 2026-11-20", "the owner asked"), a thread or message id, or a
reviewer's letter or name (claude-NNN, codex-NNN, Codex, Fable). A decision log records the
decision itself in neutral words. Run from the repository root; prints file:line: rule and exits
1 on any hit.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RULES = {
    "owner-dated": re.compile(r"\bowner\b[^.\n]{0,25}\b20\d\d-\d\d-\d\d\b", re.IGNORECASE),
    "dated-owner": re.compile(r"\b20\d\d-\d\d-\d\d\b[^.\n|]{0,8}\bowner\b", re.IGNORECASE),
    "owner-said": re.compile(
        r"\bowner(?:'s|\u2019s)? (?:asked|chose|said|says|wrote|approved|decided|confirmed|"
        r"answered|ruling|reports?|recording|screenshots?|live check|idea|wish|goal|wants|"
        r"pick|choice)\b", re.IGNORECASE),
    "owner-approved": re.compile(r"\bowner-(?:approved|requested)\b", re.IGNORECASE),
    "thread-id": re.compile(r"\bcmsg_[0-9A-Za-z]"),
    "letter": re.compile(r"\b(?:claude|codex)-\d{2,}\b", re.IGNORECASE),
    "reviewer": re.compile(r"\b(?:Codex|Fable)\b"),
    "cyrillic": re.compile(r"[\u0400-\u04ff]"),
}
# Agent rules name the review process itself; this file names the rules it checks.
EXEMPT = {"CLAUDE.md", "AGENTS.md", ".github/scripts/check_no_chat.py"}
# Vendored design skills, kept as their authors wrote them.
SKIP = re.compile(r"^(?:\.claude/skills/)")
# Files that need one rule off, each with its reason.
ALLOWED: dict[str, tuple[set[str], str]] = {}

# Rules also checked across a line break, with the next line's comment marker removed.
WRAPPED = ("owner-dated", "dated-owner")
CONTINUATION = re.compile(r"^\s*(?:#+|/{2,}|--|\*|;+)?\s*")


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    return [name for name in out.stdout.decode().split("\0") if name]


def problems(root: Path) -> list[str]:
    found = []
    for name in tracked(root):
        if name in EXEMPT or SKIP.search(name):
            continue
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
        off = ALLOWED.get(name, (set(), ""))[0]
        lines = text.splitlines()
        for number, line in enumerate(lines, 1):
            hit = [rule for rule, rx in RULES.items() if rule not in off and rx.search(line)]
            found += [f"{name}:{number}: {rule}" for rule in hit]
            if hit or number == len(lines):
                continue
            # An attribution wrapped onto the next comment line ("(owner,\n# 2026-11-28)").
            joined = line + " " + CONTINUATION.sub("", lines[number])
            for rule in WRAPPED:
                if rule not in off and RULES[rule].search(joined):
                    found.append(f"{name}:{number}: {rule} (wrapped)")
    return found


if __name__ == "__main__":
    hits = problems(Path.cwd())
    print("\n".join(hits) or "no chat quotes")
    sys.exit(1 if hits else 0)
