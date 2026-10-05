# The QA pass

Every pull request gets a QA pass before it's reported as ready. This is mandatory.

1. **After opening the pull request,** check its branch against the dev site loaded with
   `seed_demo`, at phone and desktop widths, focusing on what the diff changed. (AI sessions use
   `/qa` in diff-aware mode.)
2. **Fix each bug test-first.**
   - Write a test in the relevant app's `tests/` package, following its existing style, and run
     it to see it fail for the reason the bug describes.
   - Fix the bug, see the test pass, then run the full suite, `ruff check` and
     `ruff format --check`.
   - Commit the test and the fix together, one bug per commit, on the pull request's branch.

   If pytest can't catch a bug (purely visual, such as spacing), say so in the QA comment
   rather than skipping it silently.
3. **Post the results as a pull request comment,** one per QA run, starting with the commit it
   checked (`QA on abc1234`): the pages and widths checked, bugs found and fixed (with their
   tests), and anything deferred.

The pull request description keeps the author's own testing. QA is a later event tied to a
commit, so a comment shows when new pushes make it stale and keeps a history of re-runs.

## Widths to check

The `mobile-first` skill lists them: **320, 375, 412, 768, 1024 and 1440px**. At each, look for
horizontal scrolling, text or buttons overlapping or cut off, tap targets under 44px, and a
missing focus outline. Then turn the CSS off and check the page still reads in order and its
links and forms still work.
