"""Check a stylesheet as soon as Claude Code changes it.

A PostToolUse hook on Edit and Write (.claude/settings.json). After a change to a file in
charity/static/css/, it runs core/tests/test_stylesheet.py, which fails on a `max-width` or `px`
media query and on a colour that isn't a design token (the `mobile-first` skill). A failure is
fed back to Claude.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "charity" / "static" / "css"
# No cache, so the run doesn't change what a later `pytest --lf` picks.
TEST = "uv run --no-sync pytest core/tests/test_stylesheet.py -q -p no:cacheprovider".split()


def main():
    tool_input = json.load(sys.stdin).get("tool_input", {})
    path = Path(tool_input.get("file_path", ""))
    if path.suffix != ".css" or not path.resolve().is_relative_to(CSS):
        return 0
    result = subprocess.run(TEST, cwd=ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        return 0
    print(f"{TEST[4]} fails after this change:\n{result.stdout[-3000:]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
