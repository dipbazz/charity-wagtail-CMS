# Testing

Every feature here was built test-first with pytest: write a test, watch it fail for the reason
you expect, then write the code that makes it pass.

## Running the tests

```bash
uv run pytest                    # the whole suite
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
| `core/tests/test_stylesheet.py` | Width queries in `charity.css` are `min-width` in `rem` |
| `core/tests/test_permissions.py` | What editors and moderators can do |
| `charity/tests/test_query_budgets.py` | The most queries each kind of page may run |
| `charity/tests/test_workflows.py` | Every workflow action is pinned to a commit |
| `charity/tests/test_deploy.py` | `.env` stays out of git and the image; images pinned; logs capped |
| `charity/tests/test_production_settings.py` | Production refuses to start half-configured; every app's warnings are logged |
| `home/tests/test_seed_demo.py` | Every demo page renders |
| `charity/tests/test_changelog.py` | The changelog is well-formed and its newest version matches `pyproject.toml` |
| `charity/tests/test_docs.py` | The docs sidebar menu isn't hidden |

## How to write them

- **Fixtures and factories:** the root `conftest.py` and each app's `tests/factories.py`; see
  [Test fixtures](../reference/test-fixtures.md).
- **Admin editing** is tested through the real admin with Wagtail's form-data helpers
  (`wagtail.test.utils.form_data`; see `campaigns/tests/test_campaigns.py` and
  `home/tests/test_pages.py`), not just by saving models. The moderation workflow is tested in
  `campaigns/tests/test_editorial.py` and `core/tests/test_moderation.py`.
- **Test what editors can do as `editor`,** not with `admin_client`: a superuser can do
  everything, which hides a missing permission.
- **Files on disk:** tests use `InMemoryStorage`, which has no file paths. Tests of anything that
  reads files from disk must set `MEDIA_ROOT` to `tmp_path` and the default storage to
  `FileSystemStorage` (see `core/tests/test_media.py`).
- **Languages:** tests run with **English as the main language**, as the Brightwell demo is
  English-first, though production defaults to Nepali. So English pages are at `/about/` and
  Nepali ones under `/ne/about/`; `DJANGO_LANGUAGE_CODE` never affects tests. Ask a page
  for its address (`page.url`) rather than typing one, and build Nepali pages under
  `nepali_home_page` with `page.copy_for_translation(nepali_locale)` and a publish. To test a
  Nepali-first site, set `settings.LANGUAGE_CODE = "ne"` and clear Django's URL caches and the
  cache before and after, as `TestNepaliAsTheMainLanguage` in `charity/tests/test_languages.py`
  does: reversed URLs and Wagtail's site root paths are cached per language.
- **Query counts:** a listing test should check that its query count doesn't grow per item,
  with `cold_cache_queries`.
- If pytest can't catch a bug (something purely visual, such as spacing), say so in the pull
  request rather than skipping it silently.

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

## What CI runs

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and every push to `main`:

| Job | What it checks |
|---|---|
| `test` | ruff, `makemigrations --check`, Django's `check --deploy --fail-level WARNING` against production settings, the test suite with coverage, including the browser tests in Chromium |
| `lighthouse` | Page weight and layout shift on a phone ([Performance](../topics/performance.md)) |
| `docker` | The image builds and passes `check --deploy` inside it; the AWS Compose file and Caddyfile parse |
| `docs` | These docs build with warnings as errors; the built site is uploaded as the `docs-html` artifact |
| `changelog` (its own workflow) | The pull request updates `CHANGELOG.md`, unless it's labelled `no changelog` |
