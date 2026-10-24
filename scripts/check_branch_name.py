"""Refuse a commit on a branch that isn't named <type>/<issue-number>-<slug>.

A pre-commit hook (.pre-commit-config.yaml). The rule is in docs/contributing/index.md.
"""

import re
import subprocess
import sys

TYPES = ("feat", "fix", "perf", "refactor", "test", "chore", "docs", "style", "ci")
NAMED = re.compile(rf"(?:{'|'.join(TYPES)})/[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*")
# Branches the release steps name another way (docs/contributing/releases.md).
EXEMPT = re.compile(r"main|chore/release-[0-9]+\.[0-9]+\.[0-9]+|patch/[0-9]+\.[0-9]+\.x")


def problem(branch):
    """The message to show for a branch that breaks the rule, or None."""
    if not branch or EXEMPT.fullmatch(branch) or NAMED.fullmatch(branch):
        return None
    return (
        f"Branch '{branch}' isn't named <type>/<issue-number>-<slug>, "
        "such as feat/142-share-gift.\n"
        f"Types: {', '.join(TYPES)}. Rename it with: git branch -m <type>/<issue-number>-<slug>"
    )


def current_branch():
    """The checked-out branch, or '' when HEAD is detached (a rebase, a tag)."""
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main():
    message = problem(current_branch())
    if message:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
