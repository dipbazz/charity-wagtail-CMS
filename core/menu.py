"""The menu's standard sections (#171): which page each one is, and which the menu leaves out.

The sections, their order and their names come from the standard (`docs/site/standard.md`, "The
menu"), never from page titles: a moderator only chooses which page each one links to, in Site
settings → Menu. The menu tag and the Menu tab both read `menu_sections`, so what the tab says is
left out is what the menu leaves out.
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _
from wagtail.models import PageViewRestriction

SHOWN = "shown"
NOT_SET = "not set"
NOT_PUBLISHED = "not published"
NOT_PUBLIC = "not public"


@dataclass(frozen=True)
class Section:
    """`setting` is its chooser on SiteSettings and `name` the menu's, translated. `page_type` is
    the one kind of page it takes, as an "app_label.model" label so `core` imports nothing from the
    feature apps, or "" for any; `wrong_type` is the admin's error for another kind, in English as
    the rest of the admin's own messages are."""

    setting: str
    name: str
    page_type: str = ""
    wrong_type: str = ""


SECTIONS = (
    Section("about_page", _("About us")),
    Section(
        "appeals_page",
        _("Appeals"),
        "campaigns.campaignindexpage",
        "Choose the appeals page: Appeals lists its appeals.",
    ),
    Section(
        "stories_page",
        _("Stories"),
        "news.newsindexpage",
        "Choose the stories page: Stories lists its stories.",
    ),
    Section("get_involved_page", _("Get involved")),
    Section("contact_page", _("Contact")),
)

# The other chooser that takes one kind of page: the header's Donate button.
DONATE = Section(
    "donate_page",
    _("Donate"),
    "campaigns.donatepage",
    "Choose the Donate page: it holds the pledge form.",
)


@dataclass(frozen=True)
class MenuSection:
    """A section, the page it links to in the language being read, and whether it's shown."""

    section: Section
    page: object
    status: str

    @property
    def name(self):
        return self.section.name


def private_paths():
    """The tree paths of the pages behind a password, a login or a group: each page under one is
    private too."""
    return list(PageViewRestriction.objects.values_list("page__path", flat=True))


def menu_sections(site_settings, found, private):
    """Each section, in the standard's order, with the page it links to and its status.

    `found` maps a section's setting to its chosen page in the language being read (its published
    translation, else the chosen page), or None. `private` is `private_paths()`, read only when a
    section has a page. A section is shown only when its page is live and public, as public
    listings are (`.live().public()`).
    """
    sections = []
    for section in SECTIONS:
        page = found.get(section.setting)
        if getattr(site_settings, f"{section.setting}_id") is None:
            status = NOT_SET
        elif page is None or not page.live:
            status = NOT_PUBLISHED
        elif any(page.path.startswith(path) for path in private):
            status = NOT_PUBLIC
        else:
            status = SHOWN
        sections.append(MenuSection(section, page if status == SHOWN else None, status))
    return sections


# A home page's depth in the tree, under the root: a section's page is below one, since the
# site's name links to the home page and a home page holds every page of its site.
HOME_DEPTH = 2


def wrong_choices(site_settings):
    """Errors for SiteSettings.clean(), by field: a page chosen for two sections, on the later
    one, a home page, and a page of the wrong kind for a chooser that takes one kind."""
    errors = {}
    earlier = {}
    for section in (*SECTIONS, DONATE):
        page = getattr(site_settings, section.setting)
        if page is None:
            continue
        model = page.specific_class
        if section.page_type and (model is None or model._meta.label_lower != section.page_type):
            errors[section.setting] = section.wrong_type
        elif section is not DONATE and page.depth <= HOME_DEPTH:
            errors[section.setting] = (
                "Choose a page under the home page: the site's name links to it already."
            )
        elif section is not DONATE and page.pk in earlier:
            name = earlier[page.pk].name
            errors[section.setting] = f"This page is already {name}. Choose another one."
        if section is not DONATE:
            earlier.setdefault(page.pk, section)
    return errors
