# Versions, a changelog and milestones

**Status:** in use (since #87)

## Context

After 48 merged pull requests the site had no tags, releases, milestones or changelog. "What
changed since the last deploy?" could only be answered from the git log, nobody could say which
version was live, and new ideas kept being squeezed into whichever iteration was running. All of
that gets harder with more than one contributor, or with AI sessions that start without the
history.

## Decision

- **Semantic Versioning,** with the parts defined by who has to act on an upgrade (MAJOR: whoever
  hosts or edits the site; MINOR: new features; PATCH: fixes). Calendar versions were the other
  option; they're simple but say nothing about whether an upgrade needs care.
- **0.1.0 is the first release,** collecting everything built before versioning started. 1.0.0
  is kept for the first time a real charity runs the site.
- **A hand-written `CHANGELOG.md`** in the Keep a Changelog format, with a line added by each
  pull request and a CI check that fails without one (unless labelled `no changelog`). Writing
  the entry with the change, rather than from pull request titles at release time, means it's
  written by the person who knows what changed and for whom.
- **GitHub milestones for versions,** because issues and pull requests carry them everywhere,
  the board has a Milestone field to group by, and each milestone shows how much is done.
  Iterations stay as time boxes: two weeks at first, one week since 6 October 2026, because
  the work planned for two weeks was finishing in one.
- **New work goes into the next milestone,** apart from fixes for bugs that stop people using the
  live site.

## Consequences

- Each pull request carries one more line to write, and a label when it truly needs none.
- `charity/tests/test_changelog.py` keeps the changelog well-formed and its newest version equal
  to `pyproject.toml`'s.
- The changelog is in the docs and in `llms.txt`, so AI agents read what changed without the git
  log.
- [Versions and releases](../contributing/releases.md) has the rules and the release steps.
