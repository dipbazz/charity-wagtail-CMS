"""CI must run exactly the action code we reviewed, and still hear about new releases."""

import re
from pathlib import Path

GITHUB = Path(__file__).resolve().parents[2] / ".github"


def action_lines():
    for workflow in sorted((GITHUB / "workflows").glob("*.yml")):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*(-\s+)?uses:", line):
                yield f"{workflow.name}: {line.strip()}"


def test_every_action_is_pinned_to_a_commit():
    """A tag can be moved to other code; a commit SHA can't (see tj-actions/changed-files, 2025).

    The version stays in a comment so people and Dependabot can still read it.
    """
    lines = list(action_lines())

    assert lines, "expected the workflows to use some actions"
    assert [line for line in lines if not re.search(r"@[0-9a-f]{40} # v\d+(\.\d+)*$", line)] == []


def test_dependabot_checks_the_actions_for_updates_every_week():
    config = (GITHUB / "dependabot.yml").read_text(encoding="utf-8")

    assert 'package-ecosystem: "github-actions"' in config
    assert 'interval: "weekly"' in config
