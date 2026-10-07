# Versions and releases

Every change to the site belongs to a numbered version, listed in the
[changelog](../changelog.md) and planned as a milestone on the
[project board](issues-and-board.md). This page says what the numbers mean, how to write a
changelog entry, what goes into which version, and how to cut a release.

## Version numbers

Versions follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`. The site isn't a
library that other code calls, so the parts are defined by who has to act when they upgrade:

| Part | When it changes | Examples |
|---|---|---|
| **MAJOR** | Whoever hosts or edits the site has to do something | A manual upgrade step, a new required environment variable, a removed feature, a page type editors must move content out of |
| **MINOR** | New features that work without anyone acting | A new block, a pledge form, a new setting with a sensible default |
| **PATCH** | Fixes only | A layout bug, a wrong permission, a faster query |

While the version is `0.x`, the site is still taking shape: a change that would be MAJOR bumps
MINOR instead, and its release notes get an **Upgrade notes** section saying what to do. Version
`1.0.0` marks the first time a real charity runs the site.

The version lives in one place, `version` in `pyproject.toml`, and
`charity/tests/test_changelog.py` fails if it doesn't match the newest release in the changelog.

## The changelog

[`CHANGELOG.md`](https://github.com/dipbazz/Charity-wagtail-CMS/blob/main/CHANGELOG.md) uses the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

**Every pull request adds one small file to `changelog.d/`,** named `<slug>.<group>.md` (for
example `privacy-notice.added.md`) and holding the entry without a leading dash. Entries live in
their own files so two open pull requests never edit the same lines of `CHANGELOG.md`. The group
in the name is one of:

| Group | For |
|---|---|
| `added` | New features |
| `changed` | Changes to existing behaviour |
| `deprecated` | Features that will be removed in a later version |
| `removed` | Features removed now |
| `fixed` | Bug fixes |
| `security` | Fixes for vulnerabilities or leaks |
| `upgrade` | What someone hosting the site must do when they take this version |

`CHANGELOG.md` itself only changes when a release merges the files into it (below).

Write each entry for the person affected (a supporter, an editor or whoever hosts the site), not
for the code: "Editors can submit pages when the mail server is down", not "Catch OSError in
SMTPBackend.open". End it with a link to the pull request or issue; when the pull request
isn't open yet, add the link after you've opened it.

The `Changelog` workflow (`.github/workflows/changelog.yml`) fails a pull request that doesn't
add a file to `changelog.d/` (or touch `CHANGELOG.md`). A pull request that changes nothing anyone would notice (a CI tweak, a typo
in a comment, a release pull request) gets the **`no changelog`** label instead, which skips the
check. Dependabot's pull requests are skipped automatically.

## What goes into which version

Each version is a [milestone](https://github.com/dipbazz/Charity-wagtail-CMS/milestones) with a
goal and a due date. Usually one minor version is released at the end of each one-week
iteration.

- **An issue joins a milestone at planning,** when the iteration starts. The milestone's goal
  says what the version is for.
- **New work found during an iteration goes into the next milestone,** not the current one: a
  new feature, a redesign, a big refactor, anything that changes the plan. It's discussed when
  the next version is planned. This keeps each version finishable.
- **The exception is a bug on the live site** that stops people using it (`P1`). Its fix can
  join the current version, or ship on its own as a PATCH release.
- Issues nobody has planned yet stay in the Backlog with no milestone. So does planned work
  that turns out not to matter for this version: take it out of the milestone and clear its
  iteration, and it's considered again when the next iteration is planned.

## Cutting a release

1. **Check the milestone.** Every issue in it is closed, or moved to the next milestone or the
   Backlog with a comment saying why.
2. **Prepare the release** on a `chore/release-X.Y.Z` branch:
   - run `uv run python -m charity.changelog X.Y.Z`. It adds the `changelog.d/` entries to
     `CHANGELOG.md`'s `Unreleased` section, renames that to `## [X.Y.Z] - YYYY-MM-DD` (today),
     starts a new empty `Unreleased`, updates the links at the bottom and deletes the files; read
     the result once, since it's what people will read;
   - set `version = "X.Y.Z"` in `pyproject.toml`, then run `uv lock`.
3. **Open a pull request** titled `chore(release): X.Y.Z`, labelled `no changelog`, in the
   milestone. CI and the QA pass run as usual.
4. **After it's merged,** tag the merge commit and publish the release:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "X.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title "X.Y.Z" --notes "<this version's changelog section>"
   ```

5. **Close the milestone** and make sure the next one exists, with its goal and due date.
6. **Deploy it** ([Deploy a change](../how-to/deploy-a-change.md)). The tag says exactly which
   code is live.

## Seeing versions on the board

The board's **Milestone** field shows each issue's version. For a roadmap, add a view in the
browser: on the [project board](https://github.com/users/dipbazz/projects/1), **New view →
Board** (or Table), then **Group by → Milestone**. Each version becomes a column, with the
Backlog as "No milestone".
