# Project map

A one-page map into these docs for anyone (or any AI session) starting work here: each question
points to the one page that answers it, so there's no need to read everything or scan the code.

**Last verified against:** `v0.4.0` (every page and screenshot checked on 2026-10-12)

## Keeping the docs current

- **Starting a session:** trust the docs. Run `git log --oneline v0.4.0..HEAD --stat` (the version
  above) and re-read only the pages for the areas those commits touched. Re-scan the repo only if
  most areas changed, or if the docs contradict the code.
- **Before reading code to answer a question,** read the page below that answers it. Always read
  the actual code before *changing* it.
- **A pull request that changes what a page describes updates that page**
  ([Writing docs](contributing/writing-docs.md)).
- **Each release checks every page against the code** and fixes what has drifted, in the release
  pull request, then sets "Last verified against" to the new version
  ([Cutting a release](contributing/releases.md#cutting-a-release)). So the version above is always
  one whose docs were checked in full.

## In one paragraph

A Wagtail 8 / Django 6.1 site that small charities in Nepal and the UK get free, demoed with a
fictional water charity. Supporters read appeals and news, pledge and pay (eSewa or Khalti, in
the providers' test systems until a charity goes live, or in person) and volunteer, in Nepali or
English; the team edits in the Wagtail admin, editors drafting and
moderators publishing. SQLite, no JavaScript build step. Feature apps (`home`, `campaigns`, `news`,
`contact`, `search`) depend on `core`, which never imports them; the payment providers are
`nepal_payments`, which imports nothing from the site. Production runs the Docker image on
one EC2 server behind Caddy, configured by `DJANGO_*` environment variables; each charity gets its
own installation there, built to one standard structure. Built test-first with
pytest, styled mobile first, and budgeted for queries and page weight in CI.

## Where to find things

| Question | Page |
|---|---|
| How do I run it, locally or as production runs it? | [Getting started](getting-started/index.md) |
| What's the stack? Which app owns what? What's the page tree? Which Wagtail features are used? | [Overview](site/overview.md) |
| What must every charity's site have: header, menu, footer, pages? What may a charity change? | [The charity site standard](site/standard.md) |
| How do several charities share the platform? | [Decisions: one installation per charity](decisions.md#one-installation-per-charity-on-a-shared-server) |
| What does the home page, a standard page, a block, news, search, a form, the footer or the API do? Which URLs exist? | [Pages and content](site/pages-and-content.md) |
| Appeals, the Donate page, the pledge form, paying a pledge, pledges in the admin, money, consent, the privacy notice? | [Appeals and giving](site/appeals-and-giving.md) |
| Nepali and English: addresses, translating pages, snippets and settings text, the switch, `hreflang`, Nepali text? | [Languages](site/languages.md) |
| How are photos stored, protected and served? What's `with_card_images`? | [Images](site/images.md) |
| Colours, a charity's brand colours and previewing them, fonts, header, breakpoints, JavaScript, accessibility? How do I style something? | [Look and feel](site/look-and-feel.md) and the `mobile-first` skill |
| Who can change what? Why can't editors see my new snippet? | [Editors and permissions](site/editors-and-permissions.md) |
| How does the live server work? Environment variables, commands, backups, logs, deploying, restoring? | [Running the live site](hosting.md) |
| How is a fix, feature or design judged? Quick fix or lasting one? Standard or modern? | [Contributing: Principles](contributing/index.md#principles) |
| Branches, commits, pull requests, code style? | [Contributing](contributing/index.md) |
| How do I write tests? Fixtures? What does CI run? What must I check by hand? | [Testing and QA](contributing/testing.md) |
| Why did CI fail on query counts or page weight? | [Performance](contributing/performance.md) |
| What mistakes must I not repeat? | [Security](contributing/security.md) |
| How do I add a page type, a snippet or setting, a block, or a payment provider? | [Extending the site](contributing/extending.md) |
| What's in the demo data? Photo credits? | [Demo content](contributing/demo-content.md) |
| Issues, epics, the board, versions, the changelog, releasing? | [Issues, versions and releases](contributing/releases.md) |
| How do I write or build these docs? | [Writing docs](contributing/writing-docs.md) |
| Why SQLite, one server, `.live().public()`, pinned actions, permission migrations, Playwright? | [Decisions](decisions.md) |
| What changed in each version? What's planned? | [Changelog](changelog.md), [milestones](https://github.com/dipbazz/Charity-wagtail-CMS/milestones) |

## Rules that catch people out

Each is explained on the linked page; they're here because breaking one has caused a bug before.

- A change works for every charity and fixes the shared cause; standards come before modern
  styling ([Principles](contributing/index.md#principles)).
- Public listings filter `.live().public()`, never just `.live()`
  ([Security](contributing/security.md)).
- Page queries visitors see, other than `child_of(self)`, filter by `locale_id`, or Nepali and
  English pages mix ([Languages](site/languages.md#keeping-each-language-to-itself)).
- Snippets visitors see are listed with `in_reading_language`, and text a setting shows visitors
  goes in its rows for each language ([Languages](site/languages.md#snippets-and-settings-text)).
- Never serve `MEDIA_ROOT/documents/` directly ([Security](contributing/security.md)).
- A payment is paid only when its provider says so, asked by the server; never from what the
  browser brings back ([Security](contributing/security.md#a-payment-is-paid-only-when-its-provider-says-so)).
- `nepal_payments` imports nothing from Django or the site, so it can be published
  ([Decisions](decisions.md#payment-providers-are-a-drop-in-package)).
- A new snippet or setting needs a permissions data migration that uses `get_or_create`
  ([Extending the site](contributing/extending.md#add-a-snippet-or-setting)).
- Test permissions as `editor`, not `admin_client`
  ([Editors and permissions](site/editors-and-permissions.md#testing-permissions)).
- `min-width` queries in `rem` only; never `max-width` ([Look and feel](site/look-and-feel.md)).
- Every word a visitor reads is marked for translation, and the Nepali goes in `locale/ne/` with its
  compiled `.mo` committed ([Languages](site/languages.md#menus-buttons-and-messages)).
- `{% picture %}` lists the largest size first; card filters must match `CARD_IMAGE_FILTERS`
  ([Images](site/images.md)).
- Workflow actions are pinned to a commit SHA ([Security](contributing/security.md)).
- Every pull request adds a file to `changelog.d/` or is labelled `no changelog`
  ([Releases](contributing/releases.md#the-changelog)).
- Tests use in-memory media; tests that read files from disk switch storage
  ([Testing](contributing/testing.md#fixtures-and-factories)).
- A new app needs its name in production's loggers ([Overview](site/overview.md#logging)).
- Django 6.1 uses `MAILERS`, not `EMAIL_BACKEND`; check Wagtail 8's installed source before
  trusting older advice ([Overview](site/overview.md#stack)).
