"""The changelog records every release, in a shape people and tools can both read."""

import re
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE = re.compile(r"^## \[(\d+)\.(\d+)\.(\d+)\] - (\d{4}-\d{2}-\d{2})$")


def changelog():
    return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def headings():
    return [line for line in changelog().splitlines() if line.startswith("## ")]


def releases():
    """(version tuple, date) for each released version, newest first as written."""
    found = []
    for heading in headings()[1:]:
        match = RELEASE.match(heading)
        assert match, f"expected '## [X.Y.Z] - YYYY-MM-DD', got {heading!r}"
        *version, released = match.groups()
        found.append((tuple(int(part) for part in version), date.fromisoformat(released)))
    return found


def test_changes_not_yet_released_have_a_place_at_the_top():
    assert headings()[0] == "## [Unreleased]"


def test_releases_are_listed_newest_first():
    found = releases()

    assert found, "expected at least one released version"
    assert found == sorted(found, reverse=True)


def test_the_newest_release_is_the_version_in_pyproject():
    """Bumping one without the other at release time fails here."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    newest = ".".join(str(part) for part in releases()[0][0])

    assert pyproject["project"]["version"] == newest


def test_every_version_heading_links_to_its_changes():
    """Keep a Changelog's reference links turn each heading into a link to the diff or tag."""
    links = set(re.findall(r"^\[([^\]]+)\]: https://\S+$", changelog(), flags=re.MULTILINE))
    names = {re.match(r"## \[([^\]]+)\]", heading).group(1) for heading in headings()}

    assert names - links == set()
