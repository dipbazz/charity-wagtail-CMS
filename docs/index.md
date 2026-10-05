# Charity Wagtail CMS

A content-managed website for **Brightwell Water Trust**, a fictional water charity, built with
Django 6.1 and Wagtail 8.0. Editors run fundraising appeals, news, forms and site-wide messages
from the Wagtail admin. Every feature was built test-first with pytest.

These docs are for anyone who works on the site, and for AI agents doing the same. They're
plain Markdown in the repo's `docs/` folder, so they read the same on GitHub as on the built
site, and the build publishes `llms.txt` and `llms-full.txt` alongside the pages for AI
agents.

![The homepage](screenshots/home.jpg)

## Where to start

- **New here?** [Getting started](getting-started/index.md) gets the site running on your
  computer with demo content, and walks through a first change.
- **How does it work?** [Topics](topics/index.md) explain each part of the site: the apps,
  images, the front end, permissions, security, performance and the live server.
- **Doing a specific job?** [How-to guides](how-to/index.md) cover adding a page type, a snippet
  or setting, or a StreamField block, deploying a change and restoring a backup.
- **Looking something up?** [Reference](reference/index.md) lists the models, settings,
  management commands, template tags, URLs, the API and the test fixtures.
- **Wondering why?** [Decisions](decisions/index.md) record choices already made, and why.
- **Opening a pull request?** [Contributing](contributing/index.md) has the workflow, the tests
  and the QA pass every pull request gets.
- **Editing the charity's content?** The [editor guide](editor-guide/index.md) is for the
  charity's own team.

```{toctree}
:maxdepth: 2
:titlesonly:
:hidden:

getting-started/index
topics/index
how-to/index
reference/index
decisions/index
contributing/index
editor-guide/index
project-context
```
