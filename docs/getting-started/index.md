# Getting started

From a fresh clone to the site running on your computer with demo content, then a first change.

## What you need

- Python 3.13 or newer (the Docker image uses 3.14)
- [uv](https://docs.astral.sh/uv/), which installs everything else
- git

There's no JavaScript build step and no database server to install: the site uses SQLite, one
CSS file and one JavaScript file.

## Run the site

```bash
git clone https://github.com/dipbazz/Charity-wagtail-CMS.git
cd Charity-wagtail-CMS
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo          # fictional charity content, safe to re-run
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

| | |
|---|---|
| Site | <http://localhost:8000> |
| Admin | <http://localhost:8000/admin/> (log in as the superuser you created) |
| API | <http://localhost:8000/api/v2/pages/> |

`manage.py` uses the development settings (`charity.settings.dev`): debug on, emails printed to
the console, and [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) on every
page, showing the SQL queries, templates and timings behind it.

`seed_demo` builds the demo site: the homepage, About and Donate pages, four appeals, three news
stories, a volunteer form, partners, a testimonial, the site settings and the announcement
banner. It also copies the `SITE_URL` setting (`http://localhost:8000` in development) into
Wagtail's Site record, which every full URL is built from: the API, the news feed, the sitemap
and canonical tags. On a database created before that, run
`uv run python manage.py update_site_url` once. See [Demo content](../reference/demo-content.md).

### See the site Nepali-first

Development uses English as the main language, like the demo content and the tests; the live
site opens in Nepali. To see your local site the way a Nepali charity's visitors will, set
`DJANGO_LANGUAGE_CODE=ne` in a file called `.env.local`: copy `.env.local.example` to `.env.local` and
remove the `#` from that line. The file is gitignored and only development reads it.

`/` is then the Nepali home page, and pages that exist only in English are under `/en/`. Put the
`#` back to go back (a variable set in your shell wins over the file). The tests ignore it.

### Run it as the live site runs it

`runserver` is for changing code. To see the site as it's served live (production settings,
gunicorn, compressed static files, the Docker image) install
[Docker](https://docs.docker.com/get-started/get-docker/), then run this from the project folder:

```bash
docker compose up --build
```

The first build takes a few minutes. When the logs show gunicorn listening, open
<http://localhost:8090> (the admin is at `/admin/`). It loads the demo content itself, so there is no
superuser: create one with `docker compose exec web python manage.py createsuperuser`.

It runs on port 8090, so it can run next to `runserver`, and keeps its data in a Docker volume,
never in your `db.sqlite3`. To start again from empty demo content:

```bash
docker compose down --volumes
```

Use it to check what only breaks under production settings (static files, security headers,
the language the site opens in) and to
[measure page weight with Lighthouse](../how-to/run-lighthouse.md) before pushing. The secret
key and other values in `compose.yaml` are for your computer only; the live server has its own in
[`deploy/aws/`](../topics/deployment.md). Safari won't keep the admin login on plain `http`;
use Chrome, Edge or Firefox.

## Check that everything passes

```bash
uv run playwright install chromium   # once: the browser the browser tests drive
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

[Testing](../contributing/testing.md) explains the test layout, the fixtures and what CI runs.

## Make a first change

A small change that touches a model, a template and a test, the way every change here is made.
Say the charity wants a short "registered in England and Wales" line under its charity number
in the footer.

1. **Find where it lives.** Site-wide organisation details are in `SiteSettings`
   (`core/models.py`), and the footer template is `charity/templates/includes/footer.html`.
   [Architecture](../topics/architecture.md) maps the rest of the code.
2. **Write a failing test first.** Settings tests live in `core/tests/test_settings.py`. Add one
   that saves a value in the new field and checks the homepage shows it. Run
   `uv run pytest core/tests/test_settings.py` and watch it fail.
3. **Add the field** to `SiteSettings` and its `panels`, then make a migration:
   `uv run python manage.py makemigrations core`.
4. **Show it** in `footer.html`, reading `settings.core.SiteSettings`.
5. **Run the test again**, then the whole suite and ruff.
6. **Look at it** at <http://localhost:8000> at phone width first, then wider (see
   [Front end](../topics/front-end.md)).

Then follow [Contributing](../contributing/index.md) to open a pull request.

## Next steps

- [Topics](../topics/index.md) explain how each part of the site works.
- [How-to guides](../how-to/index.md) walk through the common bigger changes.
- [Security rules](../topics/security.md) list mistakes this project has already made once.
