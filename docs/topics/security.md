# Security

Rules this project has learned, most of them from a bug that was found and fixed. Each one has a
test, so breaking it fails CI.

## Public listings filter `.live().public()`

Public listings must filter `.live().public()`, not just `.live()`. Otherwise pages with a
password, login or group restriction leak into listings, feeds and the homepage (#47).

Search, the sitemap, the API, the news listings and feed, the appeals page and the homepage all
do. `.public()` costs one query (it reads the restrictions), which the query budgets allow for.

The main menu is the exception: it shows whatever editors tick "Show in menus" for, which may be
a members-only page. See [the decision record](../decisions/live-public-listings.md).

## Documents are only served through Wagtail's document view

Only Wagtail's document view (`/documents/<id>/<filename>`) checks a private collection's
password or login. Never serve `MEDIA_ROOT/documents/` directly (#46, fixed in `serve_media` by
#49).

- `core.views.serve_media` returns 404 for anything under `documents/`, however the path is
  written (`./documents/x`, `images/../documents/x`, `Documents.\x` on Windows).
- If a web server serves `/media/` in front of the app, it must return 404 for
  `/media/documents/` too, or anyone who knows a private document's filename can skip the
  password.
- With object storage such as S3, keep the documents in a private bucket or prefix and set
  `WAGTAILDOCS_SERVE_METHOD = "serve_view"`.

## Unconsented images stay out of the API

The images API hides images whose safeguarding consent isn't confirmed. Keep any new image
endpoint consistent with that. See [Images](images.md).

## Workflow actions are pinned to a commit

Workflows pin every action to a full commit SHA, with the version in a comment
(`uses: owner/action@<sha> # v1.2.3`), because a tag can be moved to other code (#48).
`charity/tests/test_workflows.py` fails on an unpinned `uses:`. Dependabot
(`.github/dependabot.yml`) opens one grouped pull request a week when an action has a new
release. The Caddy image in `deploy/aws/compose.yaml` is pinned to a digest for the same reason.
See [the decision record](../decisions/pinned-actions.md).

## Server secrets stay out of git and the image

Server secrets live in `deploy/aws/.env`, which is gitignored and dockerignored.
`charity/tests/test_deploy.py` checks both. Without the `.dockerignore` entry, the Dockerfile's
`COPY . .` would bake the secret key into the image.

## Production refuses to start half-configured

Production settings raise at startup without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` or
`DJANGO_SITE_URL`, rather than run with a missing secret or reject every request with a bare
400. CI runs `check --deploy --fail-level WARNING` against them, and again inside the Docker
image. See the [settings reference](../reference/settings.md).

## Permissions are tested as an editor

Test what editors can do as `editor`, not as a superuser, or a missing permission goes unnoticed.
See [Permissions](permissions.md).

## Pledges and form submissions hold personal data

Donate page pledges (the `Pledge` model) hold names, email addresses, optional home addresses
and, for monthly pledges only, mobile numbers. Editors and moderators can read and export them
under **Pledges**; only a superuser can delete one, so a donation's record can't be lost by
accident. Volunteer sign-ups are form submissions: anyone who can edit a form page can read and
export them (`wagtail.contrib.forms` grants it with the page's edit permission). Give admin
access only to people who may see supporters' details, and don't leave exported files in shared
folders.

The mobile number's help text is the supporter's consent to a monthly reminder on WhatsApp or
by text. Don't use the numbers for anything else.
