# Charity Wagtail CMS

The project's documentation is in `docs/` (Sphinx with MyST Markdown; plain Markdown you can read
directly). Read `docs/project-context.md` before exploring the code: it's a one-page map that
says which docs page answers which question. Open the page you need rather than re-scanning the
repo. Catch up with `git log --oneline <last verified commit>..HEAD --stat` and re-read only what
changed. A PR that changes what a docs page describes updates that page in the same PR, and
the docs must build with `uv run --group docs sphinx-build -W --keep-going docs docs/_build/html`.

## Versions and changelog

Every PR adds a file `changelog.d/<slug>.<group>.md` (the entry, written for the person the change
affects), or is labelled `no changelog` (CI checks this). Never edit `CHANGELOG.md` in a PR. Each version is a GitHub milestone: put a
PR in the milestone of the issue it closes. New work found mid-iteration goes into the next
milestone, not the current one, unless it fixes a P1 bug on the live site. Rules and release
steps: `docs/contributing/releases.md`.

## Design mobile first

HTML with no CSS already works on any screen, so that is where every design starts: semantic
markup in reading order, then styles for a 320px phone with no media query, then `min-width`
queries (in `rem`) that add layout only where a wider screen needs it. Never design for desktop
and override down with `max-width` queries. Load the `mobile-first` skill
(`.claude/skills/mobile-first/`) before writing or reviewing any CSS or layout markup.

## QA is part of done

CI runs the mechanical half of QA on every pull request: `charity/tests/test_demo_layout_browser.py`
loads each kind of demo page at 320, 375, 412, 768, 1024 and 1440px and fails on sideways scrolling
or a tap target under 44px. The rest is yours:

1. **Locally,** run only the tests you wrote or changed and the ones for the code you touched
   (`uv run pytest path/to/tests`), plus `ruff check` and `ruff format --check`. Don't run the
   full suite: CI runs it on every push, and the pull request isn't merged until it's green.
2. **Fix each bug test-first:** write a test in the relevant app's `tests/` package, run it to see
   it fail for the reason the bug describes, fix the bug, see it pass. One bug per commit, test and
   fix together. If pytest can't catch it (purely visual), say so in the pull request.
3. **Say what a person must check.** The pull request description is short and follows
   `.github/pull_request_template.md`; its "Check before merging" section names the pages, widths
   and what to look for in the browser, or says nothing needs checking (a change with no templates
   or CSS). Don't run `/qa` unless asked; the owner runs it when they want a full pass.
