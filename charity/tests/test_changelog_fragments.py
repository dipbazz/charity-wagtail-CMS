"""Each pull request adds a small file to changelog.d/; a release merges them into CHANGELOG.md."""

import re
from datetime import date
from pathlib import Path

import pytest

from charity.changelog import GROUPS, Fragment, load_fragments, release

ROOT = Path(__file__).resolve().parents[2]

CHANGELOG = """# Changelog

Intro.

## [Unreleased]

### Added

- Existing feature
  ([#1](https://example.org/1)).

### Fixed

- Existing fix.

## [0.2.0] - 2026-10-06

### Added

- Old.

[Unreleased]: https://github.com/o/r/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/o/r/compare/v0.1.0...v0.2.0
"""


def fragments():
    return [
        Fragment("a-new-fix", "fixed", "A fix that\nspans lines."),
        Fragment("a-feature", "added", "Another feature."),
        Fragment("heads-up", "upgrade", "Set a variable."),
    ]


def test_release_turns_unreleased_into_the_version_and_adds_an_empty_unreleased():
    text = release(CHANGELOG, fragments(), "0.3.0", date(2026, 10, 13))

    assert text.index("## [Unreleased]") < text.index("## [0.3.0] - 2026-10-13")
    assert text.index("## [0.3.0] - 2026-10-13") < text.index("## [0.2.0]")
    between = text.split("## [Unreleased]")[1].split("## [0.3.0]")[0]
    assert between.strip() == ""


def test_release_merges_fragments_into_their_groups_in_a_fixed_order():
    text = release(CHANGELOG, fragments(), "0.3.0", date(2026, 10, 13))
    section = text.split("## [0.3.0] - 2026-10-13")[1].split("## [0.2.0]")[0]

    assert re.findall(r"^### (.+)$", section, re.MULTILINE) == ["Upgrade notes", "Added", "Fixed"]
    assert "- Existing feature\n  ([#1](https://example.org/1)).\n- Another feature." in section
    assert "- Existing fix.\n- A fix that\n  spans lines.\n" in section
    assert "- Set a variable." in section


def test_release_updates_the_comparison_links():
    text = release(CHANGELOG, fragments(), "0.3.0", date(2026, 10, 13))

    assert "[Unreleased]: https://github.com/o/r/compare/v0.3.0...HEAD" in text
    assert "[0.3.0]: https://github.com/o/r/compare/v0.2.0...v0.3.0" in text
    assert "[0.2.0]: https://github.com/o/r/compare/v0.1.0...v0.2.0" in text


def test_release_without_fragments_still_dates_the_unreleased_section():
    text = release(CHANGELOG, [], "0.3.0", date(2026, 10, 13))

    assert "## [0.3.0] - 2026-10-13\n\n### Added\n\n- Existing feature" in text


def test_every_fragment_in_the_repo_is_named_slug_dot_group():
    names = [path.name for path in (ROOT / "changelog.d").glob("*.md")]
    pattern = re.compile(rf"^[a-z0-9-]+\.({'|'.join(GROUPS)})\.md$")

    assert [name for name in names if not pattern.match(name)] == []


def test_load_fragments_reads_the_group_from_the_file_name(tmp_path):
    (tmp_path / "x-y.fixed.md").write_text("Fixed it.\n", encoding="utf-8")

    assert load_fragments(tmp_path) == [Fragment("x-y", "fixed", "Fixed it.")]


def test_load_fragments_refuses_an_unknown_group(tmp_path):
    (tmp_path / "x.broken.md").write_text("Text.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="broken"):
        load_fragments(tmp_path)
