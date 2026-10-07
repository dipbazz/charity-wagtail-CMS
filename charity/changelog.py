"""Merge the pull requests' changelog.d/ files into CHANGELOG.md when cutting a release.

Every pull request adds one small file, `changelog.d/<slug>.<group>.md`, holding its entry without
the leading dash. Two open pull requests then never edit the same lines of CHANGELOG.md. At
release time: `uv run python -m charity.changelog X.Y.Z` adds those entries to the `Unreleased`
section, renames it to the version, starts a fresh `Unreleased` and deletes the files.
"""

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A file's group, as it's written in its name, and the heading it's listed under. The order is the
# order the headings appear in a release.
GROUPS = {
    "upgrade": "Upgrade notes",
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
}


@dataclass(frozen=True)
class Fragment:
    slug: str
    group: str
    text: str


def load_fragments(directory: Path) -> list[Fragment]:
    found = []
    for path in sorted(directory.glob("*.md")):
        slug, _, group = path.name.removesuffix(".md").rpartition(".")
        if group not in GROUPS:
            raise ValueError(
                f"{path.name}: the group must be one of {', '.join(GROUPS)}, not {group!r}"
            )
        found.append(Fragment(slug, group, path.read_text(encoding="utf-8").strip()))
    return found


def bullet(text: str) -> str:
    first, *rest = text.splitlines()
    return "\n".join([f"- {first}", *(f"  {line.strip()}" for line in rest)])


def release(changelog: str, fragments: list[Fragment], version: str, released: date) -> str:
    """The changelog with its Unreleased section (plus the fragments) released as `version`."""
    head, _, rest = changelog.partition("## [Unreleased]\n")
    unreleased, _, older = rest.partition("\n## [")
    older = "## [" + older

    entries = {name: [] for name in GROUPS.values()}
    for name, body in re.findall(r"^### ([^\n]+)\n\n(.*?)(?=\n### |\Z)", unreleased, re.S | re.M):
        entries[name].append(body.strip())
    for fragment in fragments:
        entries[GROUPS[fragment.group]].append(bullet(fragment.text))

    sections = [
        f"### {name}\n\n" + "\n".join(items) + "\n" for name, items in entries.items() if items
    ]
    body = "\n".join(sections)
    text = f"{head}## [Unreleased]\n\n## [{version}] - {released.isoformat()}\n\n{body}\n{older}"

    link = re.search(r"^\[Unreleased\]: (\S+)/compare/(v[\w.]+)\.\.\.HEAD$", text, re.M)
    if link:
        repo, previous = link.groups()
        text = text.replace(
            link.group(0),
            f"[Unreleased]: {repo}/compare/v{version}...HEAD\n"
            f"[{version}]: {repo}/compare/{previous}...v{version}",
        )
    return text


def main(version: str) -> None:
    fragments = load_fragments(ROOT / "changelog.d")
    path = ROOT / "CHANGELOG.md"
    path.write_text(
        release(path.read_text(encoding="utf-8"), fragments, version, date.today()),
        encoding="utf-8",
    )
    for path in (ROOT / "changelog.d").glob("*.md"):
        path.unlink()
    print(f"Released {version} with {len(fragments)} entries from changelog.d/.")


if __name__ == "__main__":
    main(sys.argv[1])
