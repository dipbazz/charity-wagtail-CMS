# Charity Wagtail CMS

Read `docs/project-context.md` before exploring the code: it maps the apps, models, settings, tests
and conventions. Don't re-scan the whole repo to learn it. Catch up with
`git log --oneline <last verified commit>..HEAD --stat` and re-read only what changed, and update the
doc in any PR that changes what it describes.

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
