# Charity Wagtail CMS

A content-managed website for **Brightwell Water Trust**, a fictional water charity, built with
Django 6.1 and Wagtail 8.0. Editors run fundraising appeals, news, forms and site-wide messages
from the Wagtail admin. Every feature was built test-first with pytest.

**Live site:** <https://16-192-118-94.sslip.io>, running the demo content on AWS EC2.

**Documentation:** [`docs/`](docs/index.md): getting started, how it works, how-to guides,
reference, the decisions behind it, and how to contribute. **What changed:**
[`CHANGELOG.md`](CHANGELOG.md).

![Homepage](docs/screenshots/home.jpg)

## Quick start

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo          # fictional charity content, safe to re-run
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Site: <http://localhost:8000> · Admin: <http://localhost:8000/admin/> · API: <http://localhost:8000/api/v2/pages/>

Run the tests with `uv run pytest`. [Getting started](docs/getting-started/index.md) explains
each step and walks through a first change.

## What it does

Pages built from StreamField blocks, fundraising appeals with targets and progress bars, news
with tags, categories and an RSS feed, editor-built forms, partners and testimonials, site-wide
settings and an emergency banner, a consent flag on every photo, search, SEO, a read-only API,
and a moderation workflow. [What the site does](docs/topics/features.md) has the full list and
the Wagtail features behind each part.

## Notes

- Brightwell Water Trust, its people, figures and charity number are fictional. The flood appeal
  describes a real flood and links to the Government of Nepal's relief fund instead of taking
  donations. [Demo content](docs/reference/demo-content.md) has the details and the photo
  credits.
- Built with a feature-branch workflow; see the merged pull requests for the history of each
  feature.
