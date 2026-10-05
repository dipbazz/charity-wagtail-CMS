# Charity Wagtail CMS

The project's documentation is in `docs/` (Sphinx with MyST Markdown; plain Markdown you can read
directly). Read `docs/project-context.md` before exploring the code: it's a one-page map that
says which docs page answers which question. Open the page you need rather than re-scanning the
repo. Catch up with `git log --oneline <last verified commit>..HEAD --stat` and re-read only what
changed. A PR that changes what a docs page describes updates that page in the same PR, and
the docs must build with `uv run --group docs sphinx-build -W --keep-going docs docs/_build/html`.

## Design mobile first

HTML with no CSS already works on any screen, so that is where every design starts: semantic
markup in reading order, then styles for a 320px phone with no media query, then `min-width`
queries (in `rem`) that add layout only where a wider screen needs it. Never design for desktop
and override down with `max-width` queries. Load the `mobile-first` skill
(`.claude/skills/mobile-first/`) before writing or reviewing any CSS or layout markup.

## QA is part of done

Every pull request gets a QA pass before it is reported as ready. This is mandatory.

1. After opening the PR, run `/qa` on its branch (diff-aware mode) against the dev site with
   `seed_demo` data, at phone and desktop widths.
2. Fix each bug QA finds **test-first**. This overrides `/qa`'s own order (fix, then maybe a
   regression test) and its rule of skipping tests for CSS fixes:
   - write a test in the relevant app's `tests/` package, following its existing style, and run it
     to see it fail for the reason the bug describes;
   - fix the bug, see the test pass, then run the full suite, `ruff check` and `ruff format --check`;
   - commit the test and the fix together, one bug per commit, on the PR's branch.
   If pytest can't catch a bug (purely visual, such as spacing), say so in the QA comment rather
   than skipping it silently.
3. Post the results as a **PR comment**, one per QA run, starting with the commit it checked
   (`QA on abc1234`): pages and widths, bugs found and fixed (with their tests), and anything
   deferred. The PR description keeps the author's own testing; QA is a later event tied to a
   commit, so a comment shows when new pushes make it stale and keeps a history of re-runs.

@docs/project-context.md
