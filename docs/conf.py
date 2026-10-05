"""Sphinx configuration for the project's documentation.

Build once with `uv run --group docs sphinx-build -W --keep-going docs docs/_build/html`, or
while writing with `uv run --group docs sphinx-autobuild docs docs/_build/html`.
"""

project = "Charity Wagtail CMS"
author = "Charity Wagtail CMS contributors"
copyright = "2026, Charity Wagtail CMS contributors"

extensions = [
    "myst_parser",
    "sphinx_wagtail_theme",
    "sphinx_llms_txt",
]

# Pages are plain Markdown, readable on GitHub and by AI agents without a build.
source_suffix = {".md": "markdown"}
myst_enable_extensions = ["colon_fence", "deflist"]
# Every heading down to h3 gets an anchor, so a page can link to a section of another.
myst_heading_anchors = 3

exclude_patterns = [
    "_build",
    # Personal notes and guides stay out of git and out of the docs.
    "**/*.local.md",
    "*.local.md",
]

html_theme = "sphinx_wagtail_theme"
html_title = "Charity Wagtail CMS"
html_static_path = ["_static"]
html_show_sphinx = False
html_theme_options = {
    "project_name": "Charity Wagtail CMS",
    "logo": "img/logo.svg",
    "logo_alt": "Charity Wagtail CMS",
    "logo_height": 48,
    "logo_width": 48,
    "github_url": "https://github.com/dipbazz/Charity-wagtail-CMS/blob/main/docs/",
    "header_links": "GitHub|https://github.com/dipbazz/Charity-wagtail-CMS",
    "footer_links": (
        "Issues|https://github.com/dipbazz/Charity-wagtail-CMS/issues,"
        "Project board|https://github.com/users/dipbazz/projects/1,"
        "Wagtail docs|https://docs.wagtail.org/"
    ),
}

# llms.txt (an index of every page) and llms-full.txt (every page in one file) for AI agents.
llms_txt_summary = (
    "Documentation for a Wagtail 8 / Django 6.1 charity website: how to run it, how it's "
    "built, how to change it safely, and the decisions behind it."
)
