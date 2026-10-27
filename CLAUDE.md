# Charity Wagtail CMS

The project's documentation is in `docs/` (Sphinx with MyST Markdown; plain Markdown you can read
directly). Read `docs/project-context.md` before exploring the code: it's a one-page map that
says which docs page answers which question. Open the page you need rather than re-scanning the
repo. Catch up with `git log --oneline <version>..HEAD --stat`, where `<version>` is that page's
"Last verified against", and re-read only what changed. A PR that changes what a docs page
describes updates that page in the same PR, and the docs must build with
`uv run --group docs sphinx-build -W --keep-going docs docs/_build/html`.

## Every charity, standard first

Many charities run this one product, each on its own installation on a shared server; never build
several into one (`docs/decisions.md`), and never offer a template, CSS, code or branch for one
charity only. Before proposing a fix, feature or design, answer the questions in the Principles
section of `docs/contributing/index.md` in the proposal. Follow the standards (WCAG 2.2 AA, web
conventions, `docs/site/standard.md`, the law) before modern styling, and add modern styling only
through the design tokens and shared components. A change to what a charity must send or decide
updates the onboarding pack in `onboarding/` in the same PR (`docs/contributing/onboarding.md`);
a charity only ever gets links to its guide and form, never a file.

## Reviews before code and before merge

A `needs: …` label marks a review an issue or pull request still owes
(`docs/contributing/reviews.md`); CI fails a pull request while one is left. Load the `workflow`
skill to file an issue, start one (its `needs:` reviews come before branching), open a pull
request or finish a review. Before each commit, check the change belongs to this branch's issue;
if not, branch from `main` for it.

## Where rules live

Rules say what, when and where; memory says who, which and how. A rule for every contributor goes
in `docs/`, with a short pointer in a skill (`.claude/skills/`, loaded by task) or a rule file
(`.claude/rules/<topic>.md` with `paths:` frontmatter, loaded when a matching file is opened). A
rule a machine can check is a check instead: CI, pre-commit, or a hook in `.claude/settings.json`.
A rule for this maintainer alone goes in `CLAUDE.local.md`. Memory holds only current state and
how-to for this machine. When a workflow or decision comes up that none of these covers, first
propose where it goes, get the user's yes, and write it there before relying on it.

## Versions and changelog

Every PR adds a file `changelog.d/<slug>.<group>.md` (the entry, written for the person the change
affects), or is labelled `no changelog` (CI checks this). Only a release edits `CHANGELOG.md`. Put
a PR in the milestone of the issue it closes; which milestone new work joins, and the release
steps, are in `docs/contributing/releases.md`; it also says which release is 1.0.0.

## Design mobile first

Start from semantic HTML, style a 320px phone with no media query, then add `min-width` queries
in `rem`; never override down with `max-width`. Load the `mobile-first` skill before writing or
reviewing any CSS or layout markup.

## QA is part of done

Run only the tests you wrote or changed and those for the code you touched
(`docs/contributing/testing.md`, "Running the tests"); CI runs the whole suite, including the
layout checks at six widths. Fix each bug test-first, one bug per commit; if pytest can't catch
it, say so in the pull request. The pull request's "Check before merging" section names the
pages, widths and what to look for in the browser, or says nothing needs checking.
