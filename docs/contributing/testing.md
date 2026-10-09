# Testing and QA

Every feature here was built test-first with pytest: write a test, watch it fail for the reason
you expect, then write the code that makes it pass. Locally, run only the tests you wrote or
changed and those for the code you touched; CI runs the whole suite on every push.

## Running the tests

```bash
uv run pytest path/to/tests      # locally: the tests you wrote and those for code you touched
uv run pytest                    # the whole suite: CI runs it; run it yourself only when you want to
uv run pytest news               # one app
uv run pytest --cov              # with coverage
uv run pytest -m "not browser"   # without the browser tests (quicker)
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
```

pytest uses `charity.settings.test` (set in `pyproject.toml`).

## Where tests live

Each app has a `tests/` package. A module's own logic is tested in its own test file
(`core/tests/test_mail.py` tests `core/mail.py`); code that uses it tests that use in its own
files.

Some tests guard the whole project rather than one feature:

| Test | Guards |
|---|---|
| `core/tests/test_dependencies.py` | `core` never imports a feature app |
| `core/tests/test_stylesheet.py` | Width queries in `charity.css` are `min-width` in `rem`; every colour outside `:root` is a `var(--…)` token that `:root` defines |
| `charity/tests/test_translations.py` | No visible template text is unmarked for translation; no Nepali entry is empty or fuzzy; the `.mo` matches the `.po` |
| `core/tests/test_permissions.py` | What editors and moderators can do |
| `charity/tests/test_query_budgets.py` | The most queries each kind of page may run |
| `charity/tests/test_workflows.py` | Every workflow action is pinned to a commit |
| `charity/tests/test_deploy.py` | `.env` stays out of git and the image; images pinned; logs capped |
| `charity/tests/test_production_settings.py` | Production refuses to start half-configured; every app's warnings are logged |
| `home/tests/test_seed_demo.py` | Every demo page renders |
| `charity/tests/test_demo_layout_browser.py` | Each kind of demo page at six widths: no sideways scrolling, no tap target under 44px ([QA](#qa)) |
| `charity/tests/test_lighthouse_budgets.py` | Each page's total weight budget is its image budget plus the fixed allowance ([Performance](performance.md)) |
| `charity/tests/test_changelog.py`, `test_changelog_fragments.py` | The changelog is well-formed, its newest version matches `pyproject.toml`, and `changelog.d/` files are named `<slug>.<group>.md` |
| `charity/tests/test_docs.py` | The docs sidebar menu isn't hidden |

## How to write them

- **Admin editing** is tested through the real admin with Wagtail's form-data helpers
  (`wagtail.test.utils.form_data`; see `campaigns/tests/test_campaigns.py` and
  `home/tests/test_pages.py`), not just by saving models. The moderation workflow is tested in
  `campaigns/tests/test_editorial.py` and `core/tests/test_moderation.py`.
- **Test what editors can do as `editor`,** not with `admin_client`: a superuser can do
  everything, which hides a missing permission.
- **Files on disk:** tests use `InMemoryStorage`, which has no file paths. Tests of anything that
  reads files from disk must set `MEDIA_ROOT` to `tmp_path` and the default storage to
  `FileSystemStorage` (see `core/tests/test_media.py`).
- **Query counts:** a listing test should check that its query count doesn't grow per item,
  with `cold_cache_queries`.
- If pytest can't catch a bug (something purely visual, such as spacing), say so in the pull
  request rather than skipping it silently.

### Languages in tests

Tests always run with **English as the main language**, as the Brightwell demo is English-first,
though production defaults to Nepali: English pages are at `/about/` and Nepali ones under
`/ne/about/`, and `DJANGO_LANGUAGE_CODE` never affects tests. Ask a page for its address
(`page.url`) rather than typing one, and build Nepali pages under `nepali_home_page` with
`page.copy_for_translation(nepali_locale)` and a publish. To test a Nepali-first site, set
`settings.LANGUAGE_CODE = "ne"` and clear Django's URL caches and the cache before and after, as
`TestNepaliAsTheMainLanguage` in `charity/tests/test_languages.py` does: reversed URLs and
Wagtail's site root paths are cached per language.

A request under `/ne/` leaves Nepali active in the test's thread, and translated text is looked
up when it's shown, so `conftest.py` puts English back after every test. Inside a test, read lazy
text (a form's label) within `translation.override("ne")`. Tests of the site's own Nepali words
are `charity/tests/test_nepali_interface.py` (header, footer, search, 404) and
`campaigns/tests/test_nepali.py` (appeals and the pledge form).

## Fixtures and factories

The root `conftest.py` has the shared fixtures; each has a docstring, so read it there. The ones
most tests use:

- **`site`**, **`home_page`**: the default Site and its home page, the parent for test pages.
  **`nepali_locale`**, **`nepali_home_page`**: the published Nepali home page at `/ne/`.
- **`demo_site`**: the whole `seed_demo` charity, built **once per test module** and rolled back
  at its end, so a module of demo tests costs one build. Use `site` for a test that needs an
  empty database.
- **`editor`**, **`moderator`**: users in those groups, never superusers.
- **`privacy_notice`**: a published privacy notice chosen in Site settings.
- **`cold_cache_queries(path)`**: how many queries a page runs on a just-started server.
- **`site_page`**: a Playwright page for browser tests (below). The cache is cleared after every
  test automatically.

Factories, built on [wagtail-factories](https://github.com/wagtail/wagtail-factories), are in
each app's `tests/factories.py` (appeals, the Donate page, news); create pages under a parent:
`CampaignPageFactory(parent=index, title="Winter appeal")`.

Media in tests is kept in memory (`InMemoryStorage`), which has no file paths: a test of anything
that reads files from disk must set `MEDIA_ROOT` to `tmp_path` and use `FileSystemStorage` (see
`core/tests/test_media.py`). Sent email is in `django.core.mail.outbox`.

## Browser tests

Some behaviour only exists in a browser: where the cursor goes, what scrolling does to a field,
and fields that CSS or `charity.js` show and hide. pytest's HTML checks can't see it, so write a
**browser test** for it with [Playwright](https://playwright.dev/python/) (`pytest-playwright`),
next to the app's other tests, e.g. `campaigns/tests/test_donate_browser.py`:

- mark the module `pytestmark = [pytest.mark.browser, pytest.mark.django_db]`;
- open pages with the root `conftest.py`'s `site_page` fixture: `site_page.goto(SITE +
  page.url)`. It answers the browser's requests with Django's test client, in the test's own
  thread and database transaction, so there's no live server and the test sees the data it
  creates. Static files come from the static finders. A redirect is answered with an
  immediate refresh to its target, because Chromium sends a redirected request to the network
  instead of back to `site_page`; like a redirect, the refresh replaces the history entry.
- assert with `playwright.sync_api.expect`, which waits for the page to settle.

Install Chromium once with `uv run playwright install chromium`. Without it, browser tests are
skipped locally with that hint; in CI they always run. Each takes about a second.

Once Playwright has started, its event loop stays in the main thread for the rest of the run, so
the root `conftest.py` sets `DJANGO_ALLOW_ASYNC_UNSAFE` whenever browser tests are collected.

## QA

QA is split between what a machine checks on every pull request and what needs a person.

**CI checks layout on every pull request.** `charity/tests/test_demo_layout_browser.py` loads one
page of each kind from the demo site (home, an ordinary page, the appeals and an appeal, news, the
Donate and volunteer forms, search, and the Nepali home page and appeal) at 320, 375, 412, 768,
1024 and 1440px, and fails when a page scrolls sideways or has a tap target under 44px (a button,
select, text field, summary, or a link in the footer, filters or pagination; links inside a
paragraph are exempt). The failure names the page, the width and the element. Add a new kind of
page to `PATHS`, and a new kind of control to `TAP_TARGETS`.

**A person checks what only eyes catch**: wording, whether a page looks right, whether a flow
makes sense. Each pull request's **Check before merging** section names the pages, widths and
what to look for, or says nothing needs checking (a backend or admin-only change). The
`mobile-first` skill's checks are the checklist: no sideways scrolling, nothing overlapping or cut
off, a visible focus outline, and a page that still reads in order with CSS off. For a fuller pass,
AI sessions have `/qa`; run it when you want one.

**A bug QA finds is fixed test-first**, one bug per commit: a test in the relevant app's `tests/`
package that fails for the reason the bug describes, then the fix. If pytest can't catch it
(something purely visual, such as spacing), say so in the pull request.

## What CI runs

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and every push to `main`:

| Job | What it checks |
|---|---|
| `test` | ruff, `makemigrations --check`, Django's `check --deploy --fail-level WARNING` against production settings, the test suite with coverage, including the browser tests in Chromium and the layout check at six widths |
| `lighthouse` | Page weight and layout shift on a phone ([Performance](performance.md)) |
| `docker` | The image builds and passes `check --deploy` inside it; the AWS Compose file and Caddyfile parse |
| `docs` | These docs build with warnings as errors; the built site is uploaded as the `docs-html` artifact |
| `changelog` (its own workflow) | The pull request adds a `changelog.d/` file, unless it's labelled `no changelog` |
