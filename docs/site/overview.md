# Overview

What the site is, how it's built, and where each part lives. The other pages in this section
each cover one part in full.

## What it is

A website and content management system for small charities in Nepal and the UK, given to them
free. Supporters read appeals and news, pledge a gift and sign up to volunteer, in Nepali or
English; the charity's team runs everything from the Wagtail admin, without a developer. The
demo charity, **Brightwell Water Trust**, is fictional ([Demo content](../contributing/demo-content.md)).

Three things shape every decision:

- **Most visitors are on a phone, often on a slow connection.** Pages are designed for a 320px
  screen first ([Look and feel](look-and-feel.md)) and their weight and database queries are
  budgeted in CI ([Performance](../contributing/performance.md)).
- **A charity has no IT staff.** One server, one database file, no services to run
  ([Decisions](../decisions.md)), and editors can't break the site from the admin.
- **Supporters' details and consent are taken seriously** ([Appeals and giving](appeals-and-giving.md#personal-data-and-consent),
  [Security](../contributing/security.md)).

## Stack

Django 6.1 and Wagtail 8.0 on Python 3.13 or newer (the Docker image uses 3.14), with SQLite and
Wagtail's database search. uv manages dependencies, ruff formats and lints, pytest tests (with
pytest-django, wagtail-factories and Playwright for browser tests). In production, gunicorn serves
the app and WhiteNoise its static files.

There's no JavaScript build step: one stylesheet, one script for every page and one for the
Donate page. Runtime dependencies beyond Wagtail are deliberately few: WhiteNoise and
[phonenumbers](../decisions.md#phone-numbers-with-phonenumbers).

Two traps with versions this new:

- Django 6.1 configures email with `MAILERS`, not `EMAIL_BACKEND`.
- Much published advice predates Wagtail 8 and Django 6.1. Check the installed source
  (`.venv/Lib/site-packages/wagtail/` on Windows, `.venv/lib/python3.*/site-packages/wagtail/`
  elsewhere) before relying on an API.

## Apps and what they own

| App | Owns |
|---|---|
| `charity` | The project: settings, URLs, the API, the base templates, the stylesheet and scripts |
| `core` | Everything shared: content blocks, the image model, site settings and the banner, partners and testimonials, languages, money and phone formatting, the mail backend, the sitemap, template tags, and the `update_site_url` and `backup_site` commands |
| `home` | The home page, standard pages and the demo content (`seed_demo`) |
| `campaigns` | Appeals, the Donate page, pledges and the admin's fundraising panel |
| `news` | News stories, categories, tag and category pages and the RSS feed |
| `contact` | Forms editors build themselves, such as volunteer sign-up |
| `search` | Site search |
| `deploy/aws/` | The live server's Docker Compose setup, Caddy, timers and backup script ([Running the live site](../hosting.md)) |

**The dependency rule:** feature apps depend on `core`, and `core` never imports them
(`core/tests/test_dependencies.py` enforces it). Shared code goes in `core`; anything that knows
about appeals or news stays in its own app. `core` has no page types, so its tests render pages
from `home`.

## The page tree

Each language has its own tree of pages under Wagtail's root ([Languages](languages.md)). Every
page type says where it may go, so editors can only build this shape:

```
Root
├─ Home page  /           (one per language)
│  ├─ Standard page  /about/        (can also go under another standard page)
│  │   └─ Form page  /about/…       (forms can go under a standard page too)
│  ├─ Donate page  /donate/         (one per home page; no children)
│  ├─ Appeals  /appeals/            (one per home page)
│  │   └─ Appeal  /appeals/flood-relief/
│  ├─ News  /news/                  (one per home page)
│  │   └─ Story  /news/<slug>/
│  └─ Form page  /volunteer/        (no children)
└─ Home page  /ne/  (the Nepali tree, with the same rules)
```

[Pages and content](pages-and-content.md) and [Appeals and giving](appeals-and-giving.md) say what
each page type shows.

## Built with Wagtail's own features

Each part uses what Wagtail already provides before adding code of its own:

| Part | Wagtail and Django features |
|---|---|
| Page bodies | `StreamField` with `StructBlock`s, custom validation and block templates |
| Appeals | Page models, `InlinePanel` with `Orderable` (suggested amounts), `TabbedInterface`, a custom `PageQuerySet` (`.active()`, `.closed()`), preview modes |
| Donate page and pledges | `RoutablePageMixin` (the thank-you route), a `ModelForm`, a `ModelViewSet` (listing, filters, inspect, export) |
| News | `RoutablePageMixin` (tag, category and feed routes), `ClusterTaggableManager`, `ParentalManyToManyField`, Django's syndication feed |
| Forms | `wagtail.contrib.forms` (`AbstractEmailForm`) |
| Partners and testimonials | Snippets with `SnippetViewSet(Group)`; `TranslatableMixin`, `DraftStateMixin`, `RevisionMixin`, `LockableMixin`, `PreviewableMixin` |
| Site settings and banner | `wagtail.contrib.settings` (per-site settings), with `ClusterableModel` and `InlinePanel` for their text in each language |
| Images | A custom image model with its own renditions, `{% picture %}`, focal points, a custom API viewset |
| Languages | `WAGTAIL_I18N_ENABLED`, `Locale`, `wagtail.contrib.simple_translation`, Django's `i18n_patterns` |
| Search | The database search backend, `search_fields`, `wagtail.contrib.search_promotions` |
| SEO | `wagtail.contrib.sitemaps`, `wagtail.contrib.redirects`, promote panels |
| API | `wagtail.api.v2` |
| Admin | Hooks (a dashboard panel, a Draftail feature), moderation workflows, scheduled publishing |

## Settings modules

| Module | Used by | What it changes |
|---|---|---|
| `charity.settings.base` | the others | Apps, middleware, templates, Wagtail settings, SQLite in the project folder |
| `charity.settings.dev` | `manage.py` and `wsgi.py` by default | Debug on, any host, emails printed to the console, django-debug-toolbar, uploads served by Django. Reads this computer's own settings from a gitignored `.env.local` (copy `.env.local.example`), such as `DJANGO_LANGUAGE_CODE=ne` |
| `charity.settings.test` | pytest | Fast password hashing, uploads kept in memory, emails kept in memory, English as the main language |
| `charity.settings.production` | the Docker image | Everything from `DJANGO_*` environment variables; refuses to start without the required ones ([Running the live site](../hosting.md#environment-variables)) |

## Logging

App code logs with `logging.getLogger(__name__)`. Production sends warnings and errors from
Wagtail and this project's apps to the container's output, so **a new app needs its name added to
the loggers in `charity/settings/production.py`**; `charity/tests/test_production_settings.py`
fails until it is ([Running the live site](../hosting.md#errors-and-logs)).
