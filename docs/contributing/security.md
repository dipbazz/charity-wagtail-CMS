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
- **A payment's history stores no reply.** A step is a kind from a fixed list, a time, the
  person who did it, and the provider's word only if it's one of that provider's `statuses`. An
  error's text can quote the provider's reply, which can hold the payer's ID or phone number, so it
  goes only to the log. `Payment.ask()` is the one place the site asks a provider and records
  what it said, so this rule lives in one place; tests check an error's text is never stored.
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
  "(test)", the pay page says "Online payments are in test mode here: no money will be taken."
  before anyone pays, and a test payment's thank-you says no money was taken. Anyone can pay in a
  test system with the provider's public test account, so the pay page doesn't show it: the docs
  do.
- **Providers get no personal details** from the site: the amount, our reference and what the gift
  is for.
- **A QR payment is paid only by the team, and the supporter's word never pays it.** "I've paid"
  makes a payment *to confirm*; only a person with `campaigns.confirm_payment` (Moderators) marks it
  paid, from the pledge in the admin, and it's logged with who did it. Those actions refuse every
  provider's payment, and a test posts as an editor to check they're refused. A QR payment is
  always live, so it can never pass for a test and can't be deleted.
- **QR codes are where money goes, so they're a moderator's, and the image is stored on the code,**
  not in the image library an editor can replace a file in.
- **An upload from outside the image library is re-saved, never stored as it came** (a QR card,
  and a supporter's receipt screenshot): `core/images.clean_image()` decodes it, drops location
  and camera data and anything hidden in other bytes, allows JPEG, PNG and WebP of up to 5 MB (no
  SVG; a phone camera's JPEG that Pillow reads as MPO is saved as a plain JPEG), and names the file
  itself.

## A supporter's upload is private and short-lived

The receipt screenshot a supporter can send with "I've paid" is the site's first upload from the
public. The rules for it, and for any later upload from visitors:

- **Re-saved before it's kept** (`clean_image()`, above), in the form, so a file that isn't a
  picture is refused with the form's other mistakes. One file per payment.
- **Small enough to decode safely:** a file of a few KB can decode to a picture that fills the
  server's memory (about 4 MB per million pixels while it's re-saved), so a receipt may be at
  most 13 million pixels (`RECEIPT_MAX_PIXELS`): any phone's screenshot, or a 12.5 megapixel
  photo. `clean_image()` checks that before decoding, and holds one copy of the picture at a
  time. A moderator's QR card may be up to 40 million.
- **Kept where no address serves it:** `STORAGES["receipts"]` is `core.storage.PrivateStorage`,
  in `receipts/` beside `media/`, never inside it. It has no URL (`url()` raises), and only the
  site's own user can read its files. The one way to see a screenshot is the pledge's page in the
  admin, through a view that checks `campaigns.confirm_payment` and is never cached. Editors read
  only that one was sent.
- **Deleted as soon as it's done its job:** when the payment is marked paid or not found, with
  its pledge, and after 30 days at most (`delete_old_receipts`, run by `backup.sh`). It's never
  backed up, so deleted means gone, as the privacy notice says.
- **No request can fill the disk:** Django writes an upload to a temporary file before a form
  checks its size, so Caddy refuses any request over 12 MB, the most the admin's uploads need
  ([Running the live site](../hosting.md)). Any other web server in front of the site needs the
  same limit.
- **Accepted risk:** there's no limit on how many receipts are sent or on the storage as a whole,
  only 5 MB and 13 million pixels per file, both checked before the picture is decoded, and one
  per payment.

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
