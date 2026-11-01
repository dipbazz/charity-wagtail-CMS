from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

NEW_SITE_BUILT = "charity.new_site"


@dataclass(frozen=True)
class StandardPageEntry:
    """A page every site has. `setting` names its chooser in Site settings; without one it's found
    by its slug under the home page, until #171 and #167 add theirs."""

    name: str
    slug: str
    setting: str = ""
    why: str = ""


# In the dashboard panel's order. #167, #168, #169, #170 and #171 each add theirs.
STANDARD_PAGES = (
    StandardPageEntry(
        _("Privacy notice"),
        "privacy",
        setting="privacy_page",
        why=_("needed before any form goes live"),
    ),
    StandardPageEntry(
        _("Donate"), "donate", setting="donate_page", why=_("brings back the Donate button")
    ),
    StandardPageEntry(_("About us"), "about"),
    StandardPageEntry(_("Appeals"), "appeals"),
    StandardPageEntry(_("Stories"), "stories"),
    StandardPageEntry(_("Volunteer with us"), "volunteer"),
)
