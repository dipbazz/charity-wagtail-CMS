# Project map

A one-page map into these docs for anyone (or any AI session) starting work here, so they can go
straight to the page that answers their question instead of reading everything.

**Last verified against:** `985bc31` (main, 2026-10-05)

## Keeping the docs current

- **Starting a session:** trust the docs. Run `git log --oneline 985bc31..HEAD --stat` (use the
  commit above) and re-read only the areas those commits touched. Re-scan the whole repo only if
  most areas changed, or if the docs contradict the code.
- **Before reading code to answer a question,** check whether a docs page already answers it.
  Always read the actual code before *changing* it.
- **A pull request that changes what a docs page describes updates that page,** and bumps "Last
  verified against" above once it's merged ([Writing docs](contributing/writing-docs.md)).

## In one paragraph

A Wagtail 8 / Django 6.1 site for a fictional water charity, on SQLite, with no JavaScript build
step. Feature apps (`home`, `campaigns`, `news`, `contact`, `search`) depend on `core`, which
never imports them. Production runs the Docker image on one EC2 server behind Caddy, configured
by `DJANGO_*` environment variables. Everything is built test-first with pytest, styled mobile
first, and budgeted for queries and page weight in CI.

## Where to find things

| Question | Page |
|---|---|
| How do I run it? | [Getting started](getting-started/index.md) |
| What can editors do? | [What the site does](topics/features.md) |
| Where does code live? Which app depends on which? What's the page tree? | [Architecture](topics/architecture.md) |
| How do I style something? | [Front end](topics/front-end.md) and the `mobile-first` skill |
| How are photos served? What's `with_card_images`? | [Images](topics/images.md) |
| Who can change what? Why can't editors see my new snippet? | [Permissions](topics/permissions.md) |
| What mistakes must I not repeat? | [Security](topics/security.md) |
| Why did CI fail on query counts or page weight? | [Performance](topics/performance.md) |
| How does the live server work? Where are the logs? | [Deployment](topics/deployment.md) |
| Which fields does a model have? | [Models](reference/models.md) |
| Which setting or environment variable? | [Settings](reference/settings.md) |
| What does a management command do? | [Management commands](reference/management-commands.md) |
| Which template tag or shared template? | [Template tags](reference/template-tags.md) |
| Which URL or API endpoint? | [URLs and the API](reference/urls-and-api.md) |
| Which test fixture or factory? | [Test fixtures](reference/test-fixtures.md) |
| What's in the demo data? Photo credits? | [Demo content](reference/demo-content.md) |
| Why SQLite, one server, `.live().public()`, pinned actions, permission migrations? | [Decisions](decisions/index.md) |
| Branches, commits, pull requests? | [Contributing](contributing/index.md) |
| How do I write tests? What does CI run? | [Testing](contributing/testing.md) |
| What's the QA pass? | [QA](contributing/qa.md) |
| Issues, epics and the board? | [Issues and the board](contributing/issues-and-board.md) |
| How do I build these docs? | [Writing docs](contributing/writing-docs.md) |

## Rules that catch people out

Each is explained on the linked page; they're listed here because breaking one has caused a bug
before.

- Public listings filter `.live().public()`, never just `.live()`
  ([Security](topics/security.md)).
- Never serve `MEDIA_ROOT/documents/` directly ([Security](topics/security.md)).
- A new snippet or setting needs a permissions data migration that uses `get_or_create`
  ([Add a snippet or setting](how-to/add-snippet-or-setting.md)).
- Test permissions as `editor`, not `admin_client` ([Permissions](topics/permissions.md)).
- `min-width` queries in `rem` only; never `max-width` ([Front end](topics/front-end.md)).
- `{% picture %}` lists the largest size first; card filters must match `CARD_IMAGE_FILTERS`
  ([Images](topics/images.md)).
- Workflow actions are pinned to a commit SHA ([Security](topics/security.md)).
- Tests use `InMemoryStorage`; tests that read files from disk switch storage
  ([Test fixtures](reference/test-fixtures.md)).
- Django 6.1 uses `MAILERS`, not `EMAIL_BACKEND`; check Wagtail 8's installed source before
  trusting older advice ([Architecture](topics/architecture.md)).
