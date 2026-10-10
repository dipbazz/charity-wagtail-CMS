# Decisions

Choices already made and why, so nobody has to rediscover the reasons or undo a choice by
accident. Each says what was decided, why, and what it costs.

When a pull request makes a choice someone might later question (a new dependency, a hosting
change, a rule everyone must follow), add a record here in the same pull request. To reverse one,
add a new record and mark the old one "Replaced by …" rather than deleting it.

## SQLite as the database

**Status:** in use

**Context**

The site serves one small charity: a handful of editors, and visitors who mostly read pages.
Every extra service (a database server, its upgrades, its backups, its bill) is something the
charity has to pay for or someone has to look after.

**Decision**

Use SQLite, in one file next to the uploads (`DJANGO_DATA_DIR`), with Wagtail's database search
backend.

**Consequences**

- Nothing to install or run besides the app: development, CI and the live server all use the
  same database engine.
- A backup is one consistent file, made with SQLite's backup API while the site keeps serving
  (`backup_site`).
- The site runs on **one machine** with a persistent disk. It can't be spread across several
  servers or run on platforms whose disks don't persist; see [One EC2 server](#one-ec2-server-with-docker-compose).
- Moving to PostgreSQL later means changing `DATABASES`, teaching `backup_site` another engine
  (it refuses anything but SQLite), and choosing a search backend.

## One EC2 server with Docker Compose

**Status:** in use (since #70)

**Context**

The site needed a public address with HTTPS, persistent storage for the SQLite database and
uploads, scheduled publishing and off-site backups (#30). The first idea was a platform such as
Fly.io, Railway or Render.

**Decision**

Run the existing Docker image on a single Linux server (an AWS EC2 instance), with Docker
Compose and Caddy in front, as set up in `deploy/aws/`:

- Caddy gets and renews the HTTPS certificate itself, so there's no load balancer or certificate
  service to set up.
- The database and uploads live on the server's disk (`/srv/charity/data`), which outlives the
  container.
- systemd timers run `publish_scheduled` every five minutes and a nightly backup to S3.
- The server's IAM role can write backups but not delete them, so a compromised server can't
  wipe them.

**Consequences**

- One server fits [SQLite](#sqlite-as-the-database): one machine, one disk.
- The setup is portable: the site is one Docker image plus a data folder, so it can move to any
  host with Docker.
- Deploying is a manual step on the server ([Deploy a change](hosting.md#deploy-a-version))
  until #76 deploys from GitHub.
- A deploy restarts the web container, with a few seconds of downtime.
- The server's operating system, Docker and disk space are ours to look after.

## Public listings filter `.live().public()`

**Status:** in use (since #47, fixed by #66)

**Context**

Wagtail lets editors put a page behind a password, a login or a group restriction. `.live()`
only drops drafts, so a restricted page still showed up in listings that used it: its title,
summary and image appeared on the homepage, the appeals and news listings and the RSS feed, to
anyone.

**Decision**

Every public listing filters `.live().public()`: search, the sitemap, the API, the news listings
and feed, the appeals page and the homepage. Tests check each one.

The main menu is the exception. It shows whatever editors tick "Show in menus" for, because an
editor may want a members-only page in the menu, and the page itself still asks for its password
or login.

**Consequences**

- `.public()` costs one query per listing (it reads the restrictions), which the query budgets
  allow for.
- Any new listing must do the same; [Security](contributing/security.md) and the
  [page type guide](contributing/extending.md#add-a-page-type) say so.

## Workflow actions pinned to commits

**Status:** in use (since #48, done in #69)

**Context**

A GitHub Actions workflow that uses `owner/action@v1` runs whatever code that tag points to on
the day. Tags can be moved, and in 2025 a compromised action (tj-actions/changed-files) did
exactly that, running attackers' code in every workflow that used it.

**Decision**

Pin every action to a full commit SHA, with the version in a comment:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

`charity/tests/test_workflows.py` fails on any `uses:` that isn't pinned this way. Dependabot
(`.github/dependabot.yml`) opens one grouped pull request a week when an action has a new
release, updating the SHA and the comment together. The Caddy image in
`deploy/aws/compose.yaml` is pinned to a digest for the same reason, and Dependabot watches it
too.

**Consequences**

- CI runs exactly the action code that was reviewed.
- Updates arrive as pull requests to review, rather than silently.
- Adding an action means looking up its commit SHA.

## Group permissions granted in data migrations

**Status:** in use (since #72, done in #73)

**Context**

The charity's team are in Wagtail's Editors and Moderators groups, not superusers. Those groups
only come with permissions for Wagtail's own models, so editors couldn't see the announcement
banner, partners, testimonials or news categories at all. Granting permissions by hand in the
admin would have to be repeated on every new database, and nothing would notice if it were
forgotten.

**Decision**

Grant this site's permissions to the groups in data migrations
(`core/migrations/0004_editor_and_moderator_permissions.py`,
`news/migrations/0004_editor_and_moderator_permissions.py`), and test them as an `editor` and a
`moderator` user, never as a superuser (`core/tests/test_permissions.py`).

Editors draft and moderators publish, as with pages. The banner is direct for editors because an
emergency message can't wait for approval; testimonials quote real people, so a moderator signs
them off; site settings are moderators' only.

**Consequences**

- Every new database, including the test database, gets the same permissions.
- Django and Wagtail create permission rows in `post_migrate`, after all migrations have run, so
  these migrations must `get_or_create` the rows they grant.
- **A new snippet or setting needs a migration like these**, or editors can't see it;
  [Add a snippet or setting](contributing/extending.md#add-a-snippet-or-setting) shows how.
- A site that renamed or deleted a group skips it rather than failing.

## Versions, a changelog and milestones

**Status:** in use (since #87); changelog entries moved to `changelog.d/` files in #130 (below)

**Context**

After 48 merged pull requests the site had no tags, releases, milestones or changelog. "What
changed since the last deploy?" could only be answered from the git log, nobody could say which
version was live, and new ideas kept being squeezed into whichever iteration was running. All of
that gets harder with more than one contributor, or with AI sessions that start without the
history.

**Decision**

- **Semantic Versioning,** with the parts defined by who has to act on an upgrade (MAJOR: whoever
  hosts or edits the site; MINOR: new features; PATCH: fixes). Calendar versions were the other
  option; they're simple but say nothing about whether an upgrade needs care.
- **0.1.0 is the first release,** collecting everything built before versioning started. 1.0.0
  is kept for the first time a real charity runs the site.
- **A hand-written `CHANGELOG.md`** in the Keep a Changelog format, with a line added by each
  pull request and a CI check that fails without one (unless labelled `no changelog`). Writing
  the entry with the change, rather than from pull request titles at release time, means it's
  written by the person who knows what changed and for whom.
  Since #130 each pull request adds its entry as one small file in `changelog.d/`, merged into
  `CHANGELOG.md` at release time, because every pull request editing the same lines made any two
  open pull requests conflict.
- **GitHub milestones for versions,** because issues and pull requests carry them everywhere,
  the board has a Milestone field to group by, and each milestone shows how much is done.
  Iterations stayed as time boxes: two weeks at first, then one week from 6 October 2026, until
  they were dropped on 10 October ([below](#release-each-version-when-its-done)).
- **New work goes into the next milestone,** apart from fixes for bugs that stop people using the
  live site.

**Consequences**

- Each pull request carries one more line to write, and a label when it truly needs none.
- `charity/tests/test_changelog.py` keeps the changelog well-formed and its newest version equal
  to `pyproject.toml`'s.
- The changelog is in the docs and in `llms.txt`, so AI agents read what changed without the git
  log.
- [Versions and releases](contributing/releases.md) has the rules and the release steps.

## Release each version when it's done

**Status:** in use (since 10 October 2026)

**Context**

Each version was meant to be one week's work, released at the end of a one-week iteration. It
took far less: 0.2.0 and 0.3.0 were both released within days of 0.1.0, and 0.4.0 was half done
while the board still said it belonged to the following week. The board's "current iteration"
showed finished versions and work planned for later, not the version being built, and
iterations had already been halved once (from two weeks) for the same reason.

**Decision**

- **A version is one kind of feature,** and it's released, and the live site deployed, as soon
  as its milestone is done, whatever the day. Only tagged versions go live, as before.
- **Iterations are dropped.** The next version is planned when one is released, from the
  Backlog. A milestone's due date is a rough target.
- **The board follows versions:** its Current version and Next version views filter on
  milestones, and move on at each release.
- Shorter iterations were the other option. They would still split a version across two time
  boxes whenever its size didn't match, and they'd keep needing to shrink.

**Consequences**

- More releases: a release pull request, a tag and a deploy each time a version is done, often
  more than once a week. Each version is small, with its own changelog section, so the live
  site changes in small steps.
- A release has one more step: pointing the board's two views at the new milestones.
- The board's Iteration field is no longer used. It stays, so old items keep their history.

## Phone numbers with `phonenumbers`

**Status:** in use (since #31)

**Context**

The Donate page asks monthly supporters for an optional mobile number, so the charity can later
send them a monthly reminder on WhatsApp, or by text message in Nepal. Sending to a number needs
it in one consistent international form (`+9779841234567`), and a number that can't receive a
message is worse than none. Supporters type numbers in many ways (`984-1234567`,
`+977 9841234567`, `07400 123456`), and each country has its own lengths and mobile ranges.

**Decision**

- **Add [`phonenumbers`](https://pypi.org/project/phonenumbers/),** the Python port of Google's
  libphonenumber. It's pure Python with no dependencies of its own and knows every country's
  number lengths and which ranges are mobiles.
- **Forms ask for a country and a number.** The country select starts on the one chosen in Site
  settings (Nepal by default); a number typed with its own `+code` keeps it.
- **Store E.164** (`+<country code><number>`), and accept only numbers that can receive a
  message: mobiles, plus the countries (such as the US and India) whose numbers can't be told
  apart from landlines.
- The countries offered are a short list in `core/phone.py`: Nepal and the countries where most
  Nepali supporters live or work. Add to it when a charity needs another.

A hand-written check (a country code plus 6–12 digits) was the alternative. It needs no
dependency, but it would accept numbers that can't exist.

**Consequences**

- A third runtime dependency (after Wagtail and WhiteNoise), with country data that changes
  several times a year. Keep it up to date with the other dependencies.
- `core.phone.normalise_mobile()` is the one place numbers are checked; anything that stores a
  phone number uses it.

## Browser tests with Playwright

**Status:** in use (since #89)

**Context**

On the Donate page, two bugs got past both pytest and the QA passes:
- scrolling over "Your own amount" changed the amount, because it was a number input;
- choosing "Other amount" didn't move the cursor into the field it reveals.

pytest renders HTML through Django's test client, so it can't see focus, scrolling, or fields
that CSS (`:has()`) and `charity.js` show and hide. Manual QA checks those once and then they
can quietly break.

**Decision**

- **Browser tests with Playwright,** through its pytest plugin (`pytest-playwright`, dev
  dependency only), in headless Chromium, marked `browser`. They run inside `uv run pytest`.
- **No live server.** The `site_page` fixture (root `conftest.py`) answers the browser's
  requests with Django's test client, in the test's thread and transaction. pytest-django's
  `live_server` needs a transactional database that is flushed after each test, and restoring
  the Site and home page that migrations create proved unreliable once other database tests had
  run first.
- Write one only for behaviour that exists only in a browser. Everything else stays a plain
  pytest test, which is faster and clearer.
- CI installs Chromium and always runs them. Locally they're skipped, with an install hint,
  until Chromium is installed.

Selenium was the alternative. Playwright needs no separate driver, waits for the page by itself,
and fits pytest through an official plugin.

**Consequences**

- About 115 MB of Chromium on each machine that runs them, and about a minute more in CI to
  install it.
- `DJANGO_ALLOW_ASYNC_UNSAFE` is set for any run that includes browser tests, because
  Playwright's event loop stays in the main thread once it starts. The project has no async
  code, so this hides nothing today; revisit it if async views arrive.
- [Testing](contributing/testing.md#browser-tests) says how to write them.

## Settings text in a row per language

**Status:** in use (since #117)

**Context**

The announcement banner's message and the footer's address are set in Wagtail settings, and readers
of the second language need them in that language. Wagtail can translate pages and snippets, but
not settings: a setting is exactly one record per Site, with no Translate action. How this project
will serve several charities is not decided yet: one installation per charity, or one installation
with a Wagtail Site per charity. Either has to keep working.

Options considered:

- **A translatable snippet holding the text,** translated like partners. Snippets belong to the
  whole installation rather than a Site, so with several charities in one installation each would
  see the others' text in the admin. Nothing would stop a second banner in the same language or the
  deletion of the main one, and the text would be edited away from the setting it belongs to.
- **One field per language** (`message_ne`, `address_ne`). Each language would need a migration, a
  third language (Welsh for a UK charity, Maithili or Newar in Nepal) included, and a field named
  after a language reads backwards on a site whose main language is Nepali.

**Decision**

Each setting keeps the values that are the same in every language. Its text goes in a row model
attached to it, one row per language (`SiteSettingsText`, `AnnouncementBannerText`, built on
`TextInEachLanguage`), edited as **Text in each language** in the setting's own form. A unique
constraint allows one row per language. Templates read the text through properties that return
the row in the language being read, else the main language's. The announcement banner moved from
a generic setting (one per installation) to a site setting (one per Site) at the same time.

**Consequences**

- The text belongs to its Site, so each charity has its own if several share an installation, and
  a new language is another row, not a migration.
- Rows are not Wagtail translations: they have no Translate action, and tools such as
  wagtail-localize won't see them. For two short texts that costs little.
- Every page runs one more query for the footer's address, and one for the banner's message while
  the banner is on. The links chosen in settings (Donate page, the banner's page, the privacy
  notice) are found together in one query, which saves as many queries as the text costs.
- Partners, testimonials and news categories are translatable snippets and so still belong to the
  whole installation. If several charities ever share one, they need a link to their Site.
- Text a new setting shows readers goes in a row model like these
  ([Extending the site](contributing/extending.md#add-a-snippet-or-setting)).

## Brand previews in Site settings

**Status:** in use (since #136)

**Context**

A charity's brand (its colours and a light or dark name bar and footer, and next its logo, #123,
and a font style, #135) is in Site settings, and Wagtail can't keep settings as drafts: a saved
change is on every page at once. A moderator trying a brand needs to see it on real pages (a long
page, the Donate form, a page in the other language) before supporters do, and to back out of a
mistake without visitors seeing it.

Options considered:

- **A: keep the brand in Site settings and preview it.** Wagtail 8's settings views support
  `PreviewableMixin`: the form gets the preview panel pages have, and the preview's request
  carries the unsaved setting, which templates then read in place of the saved one.
- **B: move the brand into a snippet with drafts** (`DraftStateMixin`, `RevisionMixin`,
  `PreviewableMixin`), saved, sent for approval and published like a page.

**Decision**

A. `SiteSettings` is a `PreviewableMixin`, and its preview draws the home page, the Donate page or
the home page in another language with the unsaved form
([Look and feel](site/look-and-feel.md#seeing-a-brand-change-before-it-goes-live)).

B adds drafts, approval, scheduling and a history to go back to. A small charity's moderator sets
the brand once and changes it rarely, so those are worth less than what B costs:

- **A snippet is a list, and a brand is one per Site.** Nothing in Wagtail stops a second brand
  or the deletion of the only one, and snippets belong to the whole installation, not a Site
  (the same problem as [settings text](#settings-text-in-a-row-per-language)).
- **The brand would move out of Site settings,** and the logo and font style after it, away from
  the charity's other details.
- **Every page would look up the published brand,** one more query on every page, where Site
  settings are already loaded.
- **The saved colours would move** in a data migration, with a permissions migration for the new
  snippet.

A is a mixin and two methods, with no migration and no change to what visitors download.

**Consequences**

- A brand change can't be kept as a draft, sent for approval or scheduled: a moderator previews
  it and saves it in one sitting.
- There's no history of earlier brands. Once saved, the old colours are gone unless someone noted
  them; a way back to the default look is #137. If charities ask for drafts or a history, B can
  still be built, and its preview would be this one.
- The preview covers the whole Site settings form, so a new address or Donate page can be
  previewed too, and Wagtail's accessibility checks panel comes with it.

## The logo is a raster image, not an SVG

**Status:** in use (since #123)

**Context**

The issue for the charity's logo asked for "SVG or a small PNG". Wagtail 8 only accepts an SVG
upload once `svg` is added to `WAGTAILIMAGES_EXTENSIONS`, and that setting is for the whole image
library, not for one field.

Options considered:

- **A: accept PNG, JPEG and WebP, as the library does now,** and serve the logo as a small copy
  at the height the name bar draws it.
- **B: add `svg` to `WAGTAILIMAGES_EXTENSIONS`.**

**Decision**

A. The logo is any image the library holds, served as a `max-320x80` rendition, which is twice
the size it's drawn at ([The logo](site/look-and-feel.md#the-logo)).

B would let an SVG into every image field, and the photo templates can't render one:
`{% picture %}` asks for `format-avif`, `format-webp` and `format-jpeg`, and Wagtail raises
`InvalidFilterSpecError` for those on an SVG, so an editor who picked one as an appeal's photo
would break that appeal's page and the listings it appears in. An SVG can also carry scripts, and
the library is open to editors, not only to the moderators who choose the logo.

**Consequences**

- A logo is a raster image. At 80px high, a PNG drawn at that size or larger is sharp on every
  phone, and the copy is a few kilobytes.
- A charity whose logo only exists as an SVG exports a PNG of it first.
- If SVG is wanted later, it needs `preserve-svg` in every photo filter, a sanitiser on upload,
  and a test that picks an SVG for each image field: a decision of its own, replacing this one.
