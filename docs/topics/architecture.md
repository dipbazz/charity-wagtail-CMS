# Architecture

Where the code lives, how the apps depend on each other, and how pages fit together.

## Stack

Django 6.1, Wagtail 8.0, Python 3.13+ (the Docker image uses 3.14), SQLite, uv, ruff, pytest with
pytest-django and wagtail-factories, WhiteNoise, gunicorn. No JavaScript build step: one plain JS
file and one CSS file.

- Django 6.1 configures email with `MAILERS`, not `EMAIL_BACKEND`.
- Wagtail 8 and Django 6.1 are newer than much published advice. Check the installed source in
  `.venv/Lib/site-packages/wagtail/` (Windows) or `.venv/lib/python3.*/site-packages/wagtail/`
  before relying on an API.

## Apps

```
charity/    settings (base, dev, test, production), urls.py, api.py (Wagtail API v2 router),
            base templates (base.html, includes/header, footer, main_menu, streamfield, social_meta,
            pagination, 404/500), static/css/charity.css, static/js/charity.js
core/       shared: StreamField blocks, CustomImage + CustomRendition, SocialMetaMixin,
            SiteSettings, AnnouncementBanner, Partner and Testimonial snippets, template tags,
            admin hooks, views (robots.txt, serve_media), the SMTP mail backend, money
            (currency formatting), phone (mobile number checks),
            update_site_url and backup_site commands
home/       HomePage, StandardPage, seed_demo command + demo_images/
campaigns/  CampaignIndexPage, CampaignPage, DonationAmount, DonatePage, Pledge (+ Frequency
            choices), PledgeForm (a ModelForm, forms.py), PledgeViewSet (views.py,
            the Pledges admin), dashboard panel hook
news/       NewsIndexPage (routable: tag, category, RSS feed), NewsPage, NewsCategory snippet
contact/    FormPage (wagtail.contrib.forms, editor-built forms with email)
search/     search view with search promotions
deploy/aws/ single-server deployment: compose.yaml (gunicorn + Caddy), Caddyfile, env.example,
            backup.sh, systemd timers for backups and publish_scheduled
docs/       these docs (Sphinx with MyST Markdown)
```

## The dependency rule

Feature apps depend on `core`; `core` never imports them. `core/tests/test_dependencies.py`
enforces this. Shared code (blocks, image helpers, settings, snippets) goes in `core`;
anything that knows about appeals or news stays in its own app.

`core` has no page types, so its tests render pages from `home`.

## Page tree

The tree `seed_demo` builds, and the parent and child rules each page type enforces:

```
Root
├─ HomePage "/" (max 1 created in the admin; translations are copies)
│  ├─ StandardPage  /about/ ... (can nest under another StandardPage)
│  ├─ DonatePage /donate/ (one per home page; no children)
│  ├─ CampaignIndexPage /appeals/ (one per home page)
│  │   └─ CampaignPage /appeals/flood-relief/ ... (+ DonationAmount inline)
│  ├─ NewsIndexPage /news/ (one per home page)
│  │   └─ NewsPage /news/<slug>/
│  └─ FormPage /volunteer/ (under HomePage or a StandardPage; no children)
└─ HomePage "/ne/" (the Nepali translation)
   ├─ CampaignIndexPage /ne/appeals/
   │   └─ CampaignPage /ne/appeals/flood-relief/
   └─ NewsIndexPage /ne/news/ ...
```

The [models reference](../reference/models.md) has each page type's fields.

## Languages

The site is in Nepali and English (`LANGUAGES`), with Wagtail's built-in translation
(`WAGTAIL_I18N_ENABLED`):

- **One page tree per language.** Each language has its own home page under Root, and a
  translation is a separate page linked to its original by `translation_key`
  (`page.copy_for_translation(locale)`, then publish). A page can exist in one language only.
- **Missing pages fall back to the main language.** A second-language address with no page there,
  such as `/ne/news/` before the news page is translated, redirects (302) to the same address in
  the main language, `/news/`, if a page is there; otherwise it's a 404.
  `core.middleware.URLLocaleMiddleware` does the redirect. `HomePage.route` refuses a language
  that has no live home page of its own, because Wagtail would otherwise serve the main
  language's pages under the other language's address.
- **The main language is at `/`.** `LANGUAGE_CODE` is the language the site opens in: Nepali
  by default in production (`DJANGO_LANGUAGE_CODE`), English for the Brightwell demo, which
  development and the tests use. The other language
  is under its prefix through `i18n_patterns(prefix_default_language=False)` in
  `charity/urls.py`. Admin, API, documents, media, the sitemap and robots.txt have no prefix.
  So the URL alone sets a response's language, and `core.middleware.URLLocaleMiddleware` (Django's
  `LocaleMiddleware` in `MIDDLEWARE`) leaves out `Vary: Accept-Language`, which would make caches
  keep a copy of each page per browser language.
- **Listings stay in one language.** Listings built with `child_of(self)` already are. Any other
  page query that visitors see filters by `locale_id=self.locale_id`, as the home page's
  featured appeals and the Donate page's appeals do. The menu takes its items from the home
  page at the start of the current page's tree path.
- **English uses British formats** through `FORMAT_MODULE_PATH` (`charity/formats/en/`), because
  `LANGUAGE_CODE` has to be `en`, not `en-gb`, for English pages to have no prefix.
  `core.migrations.0007` renamed existing `en-gb` locales to `en`.

## Settings modules

| Module | Used by | What it does |
|---|---|---|
| `charity.settings.base` | all of the below | Apps, middleware, templates, Wagtail settings |
| `charity.settings.dev` | `manage.py` and `wsgi.py` by default | Debug on, console email, debug toolbar, `SERVE_MEDIA` on |
| `charity.settings.test` | pytest | Fast password hashing, in-memory media, a locmem mailer |
| `charity.settings.production` | the Docker image | Everything from `DJANGO_*` environment variables; refuses to start without the required ones |

The [settings reference](../reference/settings.md) lists every setting and environment variable.

## Logging

Use `logging.getLogger(__name__)` in app code. Production settings send WARNING and above from
Wagtail and this project's apps to stderr, so a new app needs its name added to the list of
loggers in `charity/settings/production.py`; `charity/tests/test_production_settings.py` fails
until it is. See [Deployment](deployment.md#errors-and-logs).
