"""Refuse a commit that leaves CLAUDE.md over its word limit.

A pre-commit hook (.pre-commit-config.yaml). CLAUDE.md is read at every session start, so detail
belongs in docs/ or a skill (docs/decisions.md, "Checks before each commit with pre-commit").
"""

import sys
from pathlib import Path

LIMIT = 600


def problem(text):
    """The message to show for a CLAUDE.md over the limit, or None."""
    words = len(text.split())
    if words <= LIMIT:
        return None
    return (
        f"CLAUDE.md is {words} words, over its {LIMIT}-word limit.\n"
        "Move detail to docs/ or a skill (.claude/skills/), leaving a short pointer."
    )


def main(paths):
    for path in paths:
        message = problem(Path(path).read_text(encoding="utf-8"))
        if message:
            print(message, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
