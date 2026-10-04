# Project context

A map of the codebase for anyone (or any AI session) starting work here, so they don't have to
re-read the whole repo first. The README covers features, setup and deployment; this file covers
where things live, how they fit together and the conventions to follow.

**Last verified against:** `8136012` (main, 2026-09-29)

## Keeping this file current

- **Starting a session:** trust this file. Run `git log --oneline 8136012..HEAD --stat` (use the
  commit above) and re-read only the areas those commits touched. Re-scan the whole repo only if
  most areas changed, or if this file contradicts the code.
- **Before reading a file to answer a question,** check whether this file already answers it.
  Always read the actual code before *changing* it.
- **When a PR changes something described here** (a new app, model, setting, convention or
  gotcha), update this file in the same PR and bump "Last verified against" once it's merged.

## Stack

Django 6.1, Wagtail 8.0, Python 3.13+ (the Docker image uses 3.14), SQLite, uv, ruff, pytest with
pytest-django and wagtail-factories, WhiteNoise, gunicorn. No JavaScript build step: one plain JS
file and one CSS file.

- Django 6.1 configures email with `MAILERS`, not `EMAIL_BACKEND`. Production uses
  `core.mail.SMTPBackend`, which turns any failure to connect into a `ConnectionError`: Wagtail
  skips moderation emails only on that or `TimeoutError`, and any other error stopped editors
  submitting pages (#77).
- Wagtail 8 and Django 6.1 are newer than much published advice. Check the installed source in
  `.venv/Lib/site-packages/wagtail/` (Windows) or `.venv/lib/python3.*/site-packages/wagtail/`
  before relying on an API.

## Layout and dependency rule

```
charity/    settings (base, dev, test, production), urls.py, api.py (Wagtail API v2 router),
            base templates (base.html, includes/header, footer, main_menu, streamfield, social_meta,
            pagination, 404/500), static/css/charity.css, static/js/charity.js
core/       shared: StreamField blocks, CustomImage + CustomRendition, SocialMetaMixin,
            SiteSettings, AnnouncementBanner, Partner and Testimonial snippets, template tags,
            admin hooks, views (robots.txt, serve_media), SMTPBackend (mail.py),
            update_site_url and backup_site commands
home/       HomePage, StandardPage, seed_demo command + demo_images/
campaigns/  CampaignIndexPage, CampaignPage, DonationAmount, dashboard panel hook
news/       NewsIndexPage (routable: tag, category, RSS feed), NewsPage, NewsCategory snippet
contact/    FormPage (wagtail.contrib.forms, editor-built forms with email)
search/     search view with search promotions
deploy/aws/ single-server deployment: compose.yaml (gunicorn + Caddy), Caddyfile, env.example,
            backup.sh, systemd timers for backups and publish_scheduled
```

Feature apps depend on `core`; `core` never imports them (`core/tests/test_dependencies.py`
enforces this). `core` has no page types, so its tests render pages from `home`.

## Page tree (from `seed_demo`)

```
Root
└─ HomePage "/" (max 1)
   ├─ StandardPage  /about/, /donate/ ... (can nest under another StandardPage)
   ├─ CampaignIndexPage /appeals/ (max 1)
   │   └─ CampaignPage /appeals/flood-relief/ ... (+ DonationAmount inline)
   ├─ NewsIndexPage /news/ (max 1)
   │   └─ NewsPage /news/<slug>/
   └─ FormPage /volunteer/ (under HomePage or a StandardPage; no children)
```

## Models worth knowing

- **`core.CustomImage`** (`WAGTAILIMAGES_IMAGE_MODEL`): adds `credit` (shown as a caption) and
  `consent_confirmed` (safeguarding). The images API only lists consented images
  (`charity/api.py`, `ConsentedImagesAPIViewSet`). Alt text comes from the image's `description`.
- **`SocialMetaMixin`**: `social_image` + promote-panel fields used by `includes/social_meta.html`.
- **`SiteSettings`** (per site): charity number, contact details, `donate_page`, social URLs.
  **`AnnouncementBanner`** (generic setting): the site-wide emergency banner. Templates read them as
  `settings.core.SiteSettings` / `settings.core.AnnouncementBanner`.
- **Snippets:** `Partner` (Orderable), `Testimonial` (draft/revision/lock/preview mixins), grouped
  under "Supporters" in `core/wagtail_hooks.py`; `NewsCategory` in `news/wagtail_hooks.py`.
- **Editor permissions:** editors draft and moderators publish. Wagtail's Editors and Moderators
  groups only get permissions for Wagtail's own models; data migrations give them this site's
  (`core/migrations/0004_…`, `news/migrations/0004_…`; the table is in #72). Editors change the
  banner directly but only draft testimonials; Site settings are moderators' only. **A new
  snippet or setting needs a migration like these**, or editors can't see it. Django and Wagtail
  create permission rows in `post_migrate`, after all migrations, so such a migration must
  `get_or_create` them.
- **`CampaignPage`**: target, raised, dates, `progress_percent`, `is_active`, `TabbedInterface`,
  preview modes `""` (full page) and `"card"`. `CampaignPageQuerySet` has `.active()` / `.closed()`.
- **`BaseStreamBlock`** (`core/blocks.py`): heading, paragraph (`RICH_TEXT_FEATURES` incl. the
  custom `mark` highlight), captioned image, quote, call to action, impact stats, embed, table,
  document, testimonial, partners. Block templates are in `core/templates/core/blocks/`.
- **`FormPage.send_mail`**: Reply-To set to the sender's email field; mail errors are logged, not
  shown to the visitor.

## Front end

- **Mobile first:** base styles are the phone layout, and wider screens add to them with
  `min-width` queries in `rem` (`core/tests/test_stylesheet.py` fails on any other width
  query). The `mobile-first` skill in `.claude/skills/` has the rules and the widths to check.
- `charity.css` uses design tokens in `:root`. `charity.js` adds
  progressive enhancements, such as the copy-feed-link button. Controls that need JS start
  `hidden` in the HTML and the JS shows them, so the page works without JavaScript. The one
  exception is anything that changes layout above the fold, such as the mobile Menu button: an
  inline script in `base.html`'s `<head>` adds a `js` class to `<html>` before the first paint,
  and the CSS keys off that, so the page doesn't jump when `charity.js` runs at the end of the
  body. If `charity.js` fails to download, its `onerror` removes the class again.
- Accessibility is a requirement: skip link, `aria-current` in the menu, visible focus, tap
  targets of at least 44px, and alt text on every image.
- **Images:** photos use Wagtail's `{% picture %}` with `format-{avif,webp,jpeg}`, several
  widths and a `sizes` that matches the CSS layout. List the **largest** size first: the `<img>`
  takes its `width`/`height` from the first filter, and a smaller one stops it filling its
  column. Lazy-load everything below the first screen. The homepage banner uses
  `{% hero_picture %}` (`core/templatetags/picture_tags.py`), which serves phones a square crop
  at a lower quality (it sits under a 75% dark overlay there, so the loss doesn't show) and is
  marked `fetchpriority="high"`. Partner logos stay PNG through `{% image %}`.
- Page weight is measured by the Lighthouse job at phone emulation (412px, pixel density 1.75).
  Measure image savings that way, not in a browser at density 1, which picks smaller files.
- Listings that show cards wrap their queryset in `core.images.with_card_images()`, which
  prefetches the card renditions in one query. Its filters must match the card templates, or
  each card runs a query of its own (the listing tests catch this).
- `picture { display: contents }` in `charity.css` makes grid and flex rules apply to the `<img>`
  as before; `<source>` elements are hidden explicitly, or they become empty grid rows.

## Settings and environments

- `manage.py` and `wsgi.py` default to `charity.settings.dev`; the Docker image sets
  `charity.settings.production`, which reads everything from `DJANGO_*` environment variables
  (listed in the README) and refuses to start without the required ones.
- `charity.settings.test` sets `DEBUG = False`, uses MD5 hashing, `InMemoryStorage` for media and
  a locmem mailer.
- Uploads are served by `core.views.serve_media` when `SERVE_MEDIA` is on (the Docker image turns
  it on by default).
- `SITE_URL` is copied into the Wagtail `Site` record by `update_site_url`, which runs on every
  container start. All absolute URLs (API, feed, sitemap, canonical tags) come from that record.
- **Live server:** `deploy/aws/compose.yaml` builds the Dockerfile's image and puts Caddy in
  front for HTTPS. Data lives in `/srv/charity/data` on the server. Nightly `backup_site` copies
  go to S3 under `backups/`, which the server's IAM role can write but not delete. Server
  secrets live in `deploy/aws/.env`, which is gitignored and dockerignored
  (`charity/tests/test_deploy.py` checks both). Email isn't configured yet.

## Testing

- Test-first, with pytest. Each app has a `tests/` package; factories are in
  `campaigns/tests/factories.py` and `news/tests/factories.py`.
- Root `conftest.py` provides `site`, `home_page` and `cold_cache_queries` (counts a page's queries
  as on a just-started server, with image renditions looked up in the database), and clears the
  cache after every test. Its `editor` and `moderator` fixtures are users in those groups.
- Admin editing is tested through the real admin with Wagtail's form-data helpers
  (`campaigns/tests/test_editorial.py`). Test what editors can do as `editor`, not with
  `admin_client`: a superuser can do everything, which hides a missing permission
  (`core/tests/test_permissions.py`).
- **Gotcha:** tests use `InMemoryStorage`, which has no file paths. Tests of anything that
  reads files from disk (for example Wagtail's document serve view) must set `MEDIA_ROOT` to
  `tmp_path` and the default storage to `FileSystemStorage` (see `core/tests/test_media.py`).
- Commands: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run python manage.py makemigrations --check --dry-run`. CI also runs
  `check --deploy --fail-level WARNING` with production settings, and the same check inside the
  Docker image.

## Security rules already learned

- Public listings must filter `.live().public()`, not just `.live()`, or pages with a password or
  login restriction leak into listings, feeds and the homepage. Search, the sitemap, the API, the
  news listings and feed, the appeals page and the homepage all do (#47). `.public()` costs one
  query (it reads the restrictions), which the query budgets allow for. The main menu is the
  exception: it shows whatever editors tick "Show in menus" for, which may be a members-only page.
- Only Wagtail's document view (`/documents/<id>/<filename>`) checks collection privacy. Never
  serve `MEDIA_ROOT/documents/` directly (#46, fixed in `serve_media` by PR #49).
- The images API hides unconsented images. Keep any new image endpoint consistent with that.
- Workflows pin every action to a full commit SHA with the version in a comment
  (`uses: owner/action@<sha> # v1.2.3`), because a tag can be moved to other code (#48).
  `charity/tests/test_workflows.py` fails on an unpinned `uses:`. Dependabot
  (`.github/dependabot.yml`) opens one grouped PR a week when an action has a new release.

## Conventions

- **Branches and PRs:** one feature or fix per branch and PR, opened against `main`. Branch names
  are `feat/…`, `fix/…`, `docs/…` or `chore/…`. The maintainer reviews and merges.
- **Commits:** `type(scope): description`, lowercase, imperative, 72 characters or fewer. The body
  explains *why*. Include `Closes #N` when the commit fixes an issue.
- **Issues:** use the forms in `.github/ISSUE_TEMPLATE/` (bug, feature, docs), written from the
  point of view of the person using the site or admin. Labels: `P1`–`P3`, `bug`, `enhancement`,
  `documentation`, `accessibility`, `security`, `epic`.
- **Tracking:** each feature track is an issue labelled `epic` (titled `Epic: …`), with the work as
  its sub-issues; attach every new issue to an epic. The project board
  (<https://github.com/users/dipbazz/projects/1>) plans the work: Status (Backlog → Ready →
  In progress → In review → Done), a weekly Iteration field for sprints, and Priority. New and
  updated repo issues are added to the board automatically.
- **Demo data:** the charity and its people are fictional. Use `brightwell.example` for the
  charity's own addresses and `example.org` / `example.com` for third parties. The Nepal flood
  appeal is real, so it links to the Government of Nepal's fund and takes no donations.
- **Performance:** new features should be measured and fast from the start: query counts, image
  weight, and behaviour at phone widths (320–1440px).
