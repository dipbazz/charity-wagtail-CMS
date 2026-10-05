# Writing docs

These docs are built with [Sphinx](https://www.sphinx-doc.org/),
[MyST Markdown](https://myst-parser.readthedocs.io/) and the
[Wagtail theme](https://sphinx-wagtail-theme.readthedocs.io/), the same tools as
[Wagtail's own docs](https://docs.wagtail.org/).

## The rule

**A pull request that changes what a docs page describes updates that page.** A new model,
setting, command, convention, security rule or gotcha goes on the page that covers it, in the
same pull request. The [Reference](../reference/index.md) pages and the
[page tree](../topics/architecture.md#page-tree) are the ones most often affected.

## Build them

The docs dependencies are in a separate uv group, so install them once with
`uv sync --group docs` (a plain `uv sync` removes them again), or prefix commands with
`uv run --group docs` as below.

```bash
# Rebuild and reload in the browser on every save, at http://127.0.0.1:8000
uv run --group docs sphinx-autobuild docs docs/_build/html

# Build once, as CI does: any warning fails the build
uv run --group docs sphinx-build -W --keep-going docs docs/_build/html
```

Run `sphinx-autobuild` on another port (`--port 8001`) if the site's `runserver` is on 8000.

CI builds the docs on every pull request and uploads the built site as the `docs-html` artifact,
so anyone can download and check a pull request's docs. A broken cross-reference or a page
missing from a table of contents fails the build.

The build also writes `llms.txt` (an index of every page) and `llms-full.txt` (every page in one
file) for AI agents, with [sphinx-llms-txt](https://sphinx-llms-txt.readthedocs.io/).

## Where pages go

Pages are grouped by what the reader is doing, as in Wagtail's docs:

| Section | For | Example |
|---|---|---|
| [Getting started](../getting-started/index.md) | Someone new, from clone to first change | Install and run |
| [Topics](../topics/index.md) | Understanding how a part works | Images, permissions |
| [How-to guides](../how-to/index.md) | Doing one job, step by step | Add a page type |
| [Reference](../reference/index.md) | Looking up a fact | Settings, commands |
| [Decisions](../decisions/index.md) | Why a choice was made | SQLite |
| [Contributing](index.md) | Working on the project | Testing, QA |
| [Editor guide](../editor-guide/index.md) | The charity's editors | (to come) |

A new page goes in its section's table of contents (the `toctree` in the section's `index.md`),
or the build fails.

## How to write

- Plain Markdown that reads well on GitHub, without a build. Use MyST directives (such as
  `{toctree}` or `{warning}`) only where Markdown has nothing equivalent.
- Link between pages with relative Markdown links (`[Images](../topics/images.md)`), and to a
  section with its anchor (`images.md#card-listings`).
- One fact in one place. Link to it rather than repeating it, so pages can't disagree.
- Short sentences, plain words, British spelling. Say why, not only what.
- Personal notes and guides stay out of the docs, in gitignored `*.local.md` files; the build
  ignores them too.

## Publishing

Where the built site is published depends on whether the repo stays public, which isn't decided
yet. If it stays public, Read the Docs (free for public projects, with a preview build for each
pull request); if it goes private, publishing waits for that decision. Until then the docs are
read in the repo or from the CI artifact.
