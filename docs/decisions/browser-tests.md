# Browser tests with Playwright

**Status:** in use (since #89)

## Context

On the Donate page, two bugs got past both pytest and the QA passes:
- scrolling over "Your own amount" changed the amount, because it was a number input;
- choosing "Other amount" didn't move the cursor into the field it reveals.

pytest renders HTML through Django's test client, so it can't see focus, scrolling, or fields
that CSS (`:has()`) and `charity.js` show and hide. Manual QA checks those once and then they
can quietly break.

## Decision

- **Browser tests with Playwright,** through its pytest plugin (`pytest-playwright`, dev
  dependency only), in headless Chromium, marked `browser`. They run inside `uv run pytest`.
- **No live server.** The `site_page` fixture (root `conftest.py`) answers the browser's
  requests with Django's test client, in the test's thread and transaction. pytest-django's
  `live_server` needs a transactional database that is flushed after each test, and restoring
  the Site and home page that migrations create proved unreliable once other database tests had
  run first.
- Write one only for behaviour that exists only in a browser. Everything else stays a plain
  pytest test, which is faster and clearer.
- CI installs Chromium and always runs them. Locally they're skipped, with an install hint,
  until Chromium is installed.

Selenium was the alternative. Playwright needs no separate driver, waits for the page by itself,
and fits pytest through an official plugin.

## Consequences

- About 115 MB of Chromium on each machine that runs them, and about a minute more in CI to
  install it.
- `DJANGO_ALLOW_ASYNC_UNSAFE` is set for any run that includes browser tests, because
  Playwright's event loop stays in the main thread once it starts. The project has no async
  code, so this hides nothing today; revisit it if async views arrive.
- [Testing](../contributing/testing.md#browser-tests) says how to write them.
