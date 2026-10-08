# Contributing

How a change gets from an issue to `main`, and the rules every change follows.

```{toctree}
:maxdepth: 1

testing
performance
security
extending
demo-content
releases
writing-docs
```

## The workflow

1. **Start from an issue** on the [project board](releases.md#the-project-board), and move it to
   *In progress*.
2. **Branch from `main`:** one feature or fix per branch, named `feat/…`, `fix/…`, `docs/…` or
   `chore/…`.
3. **Work test-first** ([Testing](testing.md)): a failing test, then the code that makes it pass.
4. **Update the docs** in the same pull request when it changes something a docs page describes
   ([Writing docs](writing-docs.md)).
5. **Add a changelog file** in `changelog.d/`, written for the person the
   change affects, or label the pull request `no changelog` if nobody would notice it
   ([Releases](releases.md#the-changelog)).
6. **Run the checks for what you touched** before pushing: its tests
   (`uv run pytest path/to/tests`), `uv run ruff check . && uv run ruff format --check .`, and
   `uv run python manage.py makemigrations --check --dry-run` if models changed. CI runs the whole
   suite on every push.
7. **Open a pull request** against `main`, in the version's milestone. Its description is short
   and follows the template: what changed, what to check in the browser before merging, and
   anything the reviewer must act on; the why goes in the commit messages. Pull requests aren't
   stacked on each other.
8. **QA:** CI checks every page layout at six widths; the pull request lists what a person must
   check in the browser ([QA](testing.md#qa)).
9. **The maintainer reviews and merges.**

## Commits

`type(scope): description`: lowercase, imperative, 72 characters or fewer, no trailing period.

- Types: `feat`, `fix`, `perf`, `refactor`, `test`, `chore`, `docs`, `style`, `ci`.
- One logical change per commit; never bundle unrelated changes.
- The body explains *why*; the diff shows what.
- Include `Closes #N` when the commit fixes an issue.
- A breaking change gets a `!`, e.g. `feat(api)!: change response shape`.

The pull request title follows the same format.

## Code style

- ruff, with a line length of 100, enforces formatting and lint rules (`pyproject.toml`).
- Match the surrounding code: its naming, comment density and idiom.
- Comments explain why, especially where the code works around something (a Wagtail
  limitation, a browser quirk, a past bug with its issue number).
- `logging.getLogger(__name__)` in app code.

## Design rules

- **Mobile first** for every page, block and component: [Look and feel](../site/look-and-feel.md).
- **Fast from the start:** query counts, image weight and behaviour at 320–1440px are measured
  for every new feature: [Performance](performance.md).
- **Accessible:** [Look and feel](../site/look-and-feel.md#accessibility).
- **Secure:** read [Security](security.md) before touching listings, documents,
  images, workflows or deployment.
- **Demo data is fictional:** `brightwell.example` for the charity, `example.org` /
  `example.com` for third parties ([Demo content](demo-content.md)).
