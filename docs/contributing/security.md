# Security

Rules this project has learned, most of them from a bug that was found and fixed. Each one has a
test, so breaking it fails CI.

## Public listings filter `.live().public()`

Public listings must filter `.live().public()`, not just `.live()`. Otherwise pages with a
password, login or group restriction leak into listings, feeds and the homepage (#47).

Search, the sitemap, the API, the news listings and feed, the appeals page and the homepage all
do. `.public()` costs one query (it reads the restrictions), which the query budgets allow for.

The main menu is the exception: it shows whatever editors tick "Show in menus" for, which may be
a members-only page. See [the decision record](../decisions.md#public-listings-filter-livepublic).

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
endpoint consistent with that. See [Images](../site/images.md).

## Workflow actions are pinned to a commit

Workflows pin every action to a full commit SHA, with the version in a comment
(`uses: owner/action@<sha> # v1.2.3`), because a tag can be moved to other code (#48).
`charity/tests/test_workflows.py` fails on an unpinned `uses:`. Dependabot
(`.github/dependabot.yml`) opens one grouped pull request a week when an action has a new
release. The Caddy image in `deploy/aws/compose.yaml` is pinned to a digest for the same reason.
See [the decision record](../decisions.md#workflow-actions-pinned-to-commits).

## Server secrets stay out of git and the image

Server secrets live in `deploy/aws/.env`, which is gitignored and dockerignored.
`charity/tests/test_deploy.py` checks both. Without the `.dockerignore` entry, the Dockerfile's
`COPY . .` would bake the secret key into the image.

## A payment is paid only when its provider says so

Whether a pledge is paid comes only from the provider's own API, asked by the server with the
site's own reference and amount (`check()` in `nepal_payments`). What the supporter's browser brings
back to the return address (eSewa's `?data=`, Khalti's `?status=Completed`) is never read, because
anyone can type it; a test sends a forged return and checks that nothing changes. Only
`Payment.record()` changes a status, and paid never goes back.

- **A pledge is paid only by a payment of its own amount.** Once someone starts paying a pledge,
  sending its form again starts a new pledge rather than changing it, and a payment for another
  amount or currency (a pledge changed in the admin meanwhile) leaves the pledge unpaid. Otherwise
  paying Rs 10 could mark a Rs 1,00,000 pledge as received.
- **Merchant keys live in the environment** (`DJANGO_PAYMENT_*`), never in git, the admin or the
  database. Providers keep them out of their `repr()` and logs.
- **A provider's answer comes only from the provider.** `nepal_payments.http` never follows a
  redirect: it would carry the merchant's key, and the say on whether a payment is paid, to
  whatever address the redirect names (CVE-2018-18074 was this flaw in `requests`).
- **The payer is sent only to the provider's own page.** A Khalti answer naming any other address
  is refused, and the contract test (`nepal_payments/tests/test_contract.py`) fails any provider
  that sends a payer anywhere but `https`.
- **A form posted to a provider carries no CSRF token** of ours, so it can't leak to them.
- **Test mode can't pass for real money:** the Pledges list and its export mark a test payment
  "(test)", and its thank-you says no money was taken. Anyone can pay in a test system with the
  provider's public test account, so the pay page doesn't show it: the docs do.
- **Providers get no personal details** from the site: the amount, our reference and what the gift
  is for.

## Production refuses to start half-configured

Production settings raise at startup without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` or
`DJANGO_SITE_URL`, rather than run with a missing secret or reject every request with a bare
400. CI runs `check --deploy --fail-level WARNING` against them, and again inside the Docker
image. A payment provider with only some of its keys fails Django's checks, which `migrate` runs
as the container starts, so it stops the site too. See
[Running the live site](../hosting.md#environment-variables).

## Permissions are tested as an editor

Test what editors can do as `editor`, not as a superuser, or a missing permission goes unnoticed.
See [Editors and permissions](../site/editors-and-permissions.md#testing-permissions).

## Exports show what visitors typed as text

A spreadsheet runs a cell that starts with `=` as a formula (in a CSV file, `+`, `-` and `@` too),
so a pledge "from" `=HYPERLINK(…)` could send other donors' details away when the team opens the
export (CWE-1236). Wagtail writes text as it is, so every export of what visitors typed (Pledges,
form submissions) goes through `core.exports.VisitorTextExportMixin`: an Excel file keeps such text
in a text cell, shown as typed, and a CSV file puts `'` in front of it. A new export of visitors'
text puts the mixin first among its view's bases.

## Supporters' personal data stays with the team

Pledges and form submissions hold names, contact details and consents. Who can see them, what each
consent allows, and why a pledge's message is never shown: [Appeals and giving](../site/appeals-and-giving.md#personal-data-and-consent).
