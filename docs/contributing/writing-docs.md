# Writing docs

These docs are built with [Sphinx](https://www.sphinx-doc.org/),
[MyST Markdown](https://myst-parser.readthedocs.io/) and the
[Wagtail theme](https://sphinx-wagtail-theme.readthedocs.io/), the same tools as
[Wagtail's own docs](https://docs.wagtail.org/).

## The rule

**A pull request that changes what a docs page describes updates that page**, in the same pull
request: a new page type, setting, command, convention, security rule or gotcha goes on the page
that covers it. Once it's merged, bump "Last verified against" in the
[project map](../project-context.md).

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

**One page per feature, answering the whole question.** Someone who wants to understand the Donate
page reads one page, not six. Pages are grouped by who's reading:

| Section | For | Example |
|---|---|---|
| [Getting started](../getting-started/index.md) | Someone new, from clone to first change | Install and run |
| [The site](../site/index.md) | How each part works: what it does, why, its rules, where its code is | Appeals and giving, Languages |
| [Running the live site](../hosting.md) | Whoever hosts it | Environment variables, deploying, backups |
| [Contributing](index.md) | Working on the code | Testing, performance, security, releases |
| [Decisions](../decisions.md) | Why a choice was made | SQLite, one server |
| [Editor guide](../editor-guide.md) | The charity's team | (to come) |

A new page goes in its section's table of contents (the `toctree` in the section's `index.md`, or
the home page's), or the build fails. Prefer a new section on an existing page to a new page.

## What a page says

The test for every page: **could someone rebuild this part of the site from the page alone, in
any codebase, and get the same behaviour?** So a page describes:

1. **what it does**, for visitors and for editors, including the details that matter (what a page
   shows and in what order, limits, defaults, what happens on an error);
2. **why**, especially where another way would seem obvious;
3. **the rules** that keep it working, and the past bugs behind them;
4. **where the code is**, as pointers (`campaigns/models.py`, `DonatePage`), and how it's tested.

It **doesn't repeat the code**: no field-by-field tables, no lists of files or templates, no
copied code. Those go stale silently and the code already says them. Name code only to point to
it. The exceptions are names people use directly: URLs, API fields, environment variables,
settings, management commands and template tags.

## How to write

- Plain Markdown that reads well on GitHub, without a build. Use MyST directives (such as
  `{toctree}` or `{warning}`) only where Markdown has nothing equivalent.
- Link between pages with relative Markdown links (`[Images](../site/images.md)`), and to a
  section with its anchor (`images.md#card-listings`).
- One fact in one place. Link to it rather than repeating it, so pages can't disagree.
- Short sentences, plain words, British spelling.
- Personal notes and guides stay out of the docs, in gitignored `*.local.md` files; the build
  ignores them too.

## Publishing

Where the built site is published depends on whether the repo stays public, which isn't decided
yet. If it stays public, Read the Docs (free for public projects, with a preview build for each
pull request); if it goes private, publishing waits for that decision. Until then the docs are
read in the repo or from the CI artifact.
