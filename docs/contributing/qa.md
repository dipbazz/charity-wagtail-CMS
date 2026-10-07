# QA

QA is split between what a machine can check on every pull request and what needs a person.

## What CI checks

`charity/tests/test_demo_layout_browser.py` loads one page of each kind from the demo site
(home, an ordinary page, the appeals and an appeal, news, the Donate and volunteer forms, search,
and the Nepali home page and appeal) at **320, 375, 412, 768, 1024 and 1440px** in Chromium, and
fails the pull request when a page:

- **scrolls sideways** (its `scrollWidth` is wider than the window); or
- has a **tap target under 44px**: a button, select, summary, or a link in the footer, the filter
  tags or the pagination. Links inside a paragraph are exempt; they're as tall as their line.

The failure names the page, the width and the element. To check a new kind of page, add its address
to `PATHS`; to cover a new kind of control, add its selector to `TAP_TARGETS`. The demo site is
built once per test module (see [Test fixtures](../reference/test-fixtures.md)).

## What a person checks

Some things only eyes catch: wording, whether a page looks right, whether a flow makes sense.
Each pull request's **Check before merging** section lists the pages, widths and things to look
for, or says nothing needs checking (a backend or admin-only change with no templates or CSS).
Load the demo with `manage.py seed_demo`; the `mobile-first` skill's checks are the checklist:
no sideways scrolling, nothing overlapping or cut off, a visible focus outline, and a page that
still reads in order with CSS off.

For a fuller pass, AI sessions have `/qa` (diff-aware mode against the branch). Run it when you
want one; it isn't required.

## When QA finds a bug

Fix it test-first, one bug per commit:

1. Write a test in the relevant app's `tests/` package, in its existing style, and run it to see
   it fail for the reason the bug describes.
2. Fix the bug and see the test pass.
3. Commit the test and the fix together on the pull request's branch.

If pytest can't catch a bug (something purely visual, such as spacing), say so in the pull request
rather than skipping it silently.
