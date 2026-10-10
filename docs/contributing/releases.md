# Issues, versions and releases

How work is planned and shipped: issues and the project board, then versions, the changelog and
releases. Every change belongs to a numbered version, listed in the [changelog](../changelog.md)
and planned as a milestone on the [project board](#the-project-board).

## Issues

Open issues with the forms in `.github/ISSUE_TEMPLATE/`: bug, feature or docs. Write them from
the point of view of the person using the site or the admin: what they're trying to do and what
gets in their way, not the code change.

Labels:

| Label | |
|---|---|
| `P1`, `P2`, `P3` | Priority: P1 is urgent, P3 can wait |
| `bug`, `enhancement`, `documentation` | Kind of change |
| `accessibility`, `security` | Areas that need extra care in review |
| `epic` | A feature track (below) |

## Epics

Each feature track is an issue labelled `epic` and titled `Epic: …`, with the work as its
sub-issues. It says the goal, why it matters, how the work is split and when it's done.
Attach every new issue to an epic.

Docs for a new feature aren't separate sub-issues: the feature's pull request updates its own
docs page, under that feature's epic.

## The project board

The [project board](https://github.com/users/dipbazz/projects/1) plans the work. New and
updated issues in the repo are added to it automatically.

| Field | |
|---|---|
| Status | Backlog → Ready → In progress → In review → Done |
| Milestone | The version the work ships in, e.g. `v0.4.0` |
| Priority | Mirrors the `P1`–`P3` labels |

The **Current version** view shows the version being built, in a column for each status, and
**Next version** the one planned after it. Each filters on its milestone, such as
`milestone:"v0.4.0"`, so both move on when a version is released ([below](#cutting-a-release)).
The board's Iteration field is no longer used: versions set the pace instead
([Decisions](../decisions.md#release-each-version-when-its-done)).

- Move an issue to *In progress* when you start it, and to *In review* when its pull request is
  open.
- An epic is *In progress* while any of its sub-issues is being worked on or done, and *Done*
  when all of them are closed.
- Merged pull requests and closed issues go to *Done*.

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

Each version is a [milestone](https://github.com/dipbazz/Charity-wagtail-CMS/milestones) for one
kind of feature, such as "brand the site from the admin". Its goal says what the version is for,
and its due date is a rough target, not a deadline. One version is built at a time, and it's
released as soon as it's done, whatever the day: a version is usually a few days' work.

- **The next version is planned when one is released:** choose its issues from the Backlog, and
  give the milestone its goal and a due date.
- **Work started straight away joins the version being built,** such as a fix found while
  testing it.
- **New work filed for later goes into the next milestone,** not the current one: a new
  feature, a redesign, a big refactor, anything that changes the plan. It's discussed when the
  next version is planned. This keeps each version finishable.
- **The exception is a bug on the live site** that stops people using it (`P1`). Its fix can
  join the current version, or ship on its own as a [patch release](#patch-releases).
- Issues nobody has planned yet stay in the Backlog with no milestone. So does planned work
  that turns out not to matter for this version: take it out of the milestone, and it's
  considered again when the next version is planned.

## Cutting a release

Release a version as soon as the last issue in its milestone is closed.

1. **Check the milestone.** Every issue in it is closed, or moved to the next milestone or the
   Backlog with a comment saying why.
2. **Prepare the release** on a `chore/release-X.Y.Z` branch:
   - run `uv run python -m charity.changelog X.Y.Z`. It adds the `changelog.d/` entries to
     `CHANGELOG.md`'s `Unreleased` section, renames that to `## [X.Y.Z] - YYYY-MM-DD` (today),
     starts a new empty `Unreleased`, updates the links at the bottom and deletes the files; read
     the result once, since it's what people will read;
   - set `version = "X.Y.Z"` in `pyproject.toml`, then run `uv lock`.
3. **Open a pull request** titled `chore(release): X.Y.Z`, labelled `no changelog`, in the
   milestone. CI runs as usual.
4. **After it's merged,** tag the merge commit and publish the release:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "X.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title "X.Y.Z" --notes "<this version's changelog section>"
   ```

5. **Close the milestone and plan the next version** ([above](#what-goes-into-which-version)).
   On the board, change the filters of the **Current version** and **Next version** views to the
   new milestones.
6. **Deploy it** ([Deploy a change](../hosting.md#deploy-a-version)). The tag says exactly which
   code is live.

## Patch releases

Only for a bug on the live site that stops people using it (`P1`) and can't wait for the
version being built; any other fix goes into that version. A patch release, such as 0.4.1 while
0.4.0 is live, holds that fix and nothing else, so it's made from the live version's tag, not
from `main`, which already has work for the next version. Give it a milestone (`v0.4.1`) holding
the bug's issue.

1. **Fix it on `main` first,** in a normal pull request with its `fixed` file in `changelog.d/`,
   so the next version has the fix too. If the fix needs a migration, write it to follow the live
   version's last migration, so the same file works on both branches. When `main` already has
   newer migrations, add the merge migration (`makemigrations --merge`) in a commit of its own.
2. **Make the patch branch from the live tag** (or use it, if an earlier patch made it):

   ```bash
   git checkout -b patch/0.4.x v0.4.0
   git push -u origin patch/0.4.x
   ```

3. **Prepare the release in a second folder,** so your local database, which already has the next
   version's migrations, isn't touched (`db.sqlite3` and `media/` belong to the folder). Copy
   `.env` or `charity/settings/local.py` across if you use them.

   ```bash
   git worktree add -b chore/release-0.4.1 ../charity-patch patch/0.4.x
   cd ../charity-patch && uv sync
   git cherry-pick <the fix's commit on main>    # not the merge migration's
   uv run python manage.py migrate && uv run python manage.py seed_demo
   ```

   Check the fix there, then follow step 2 of [Cutting a release](#cutting-a-release) and open
   the pull request against `patch/0.4.x`, labelled `no changelog`. CI runs on it as usual.
4. **After it's merged,** tag the merge commit and publish the release as in step 4 above, with
   `patch/0.4.x` in place of `main`, then [deploy](../hosting.md#deploy-a-version) `v0.4.1`.
5. **Bring the release onto `main`** in a pull request labelled `no changelog`, so the next
   version's notes don't list the fix again: take `CHANGELOG.md` from the patch branch
   (`git checkout patch/0.4.x -- CHANGELOG.md`; `main`'s copy only changes at a release, so this
   adds just the new section), delete the fix's file from `changelog.d/`, set `version` in
   `pyproject.toml` to `0.4.1` and run `uv lock`.
6. **Close the milestone** and remove the second folder (`git worktree remove ../charity-patch`).
   Keep the patch branch for any later patch to the same version.

## Seeing versions on the board

The board's **Milestone** field shows each issue's version. For a roadmap of every version, add
a view in the browser: on the [project board](https://github.com/users/dipbazz/projects/1),
**New view → Board** (or Table), then **Group by → Milestone**. Each version becomes a column,
with the Backlog as "No milestone".
