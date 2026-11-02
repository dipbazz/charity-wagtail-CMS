from collections.abc import Callable
from dataclasses import dataclass

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from campaigns.forms import PledgeForm
from campaigns.models import CampaignIndexPage, DonatePage
from contact.models import FormField, FormPage
from home.models import StandardPage
from news.models import NewsIndexPage

NEW_SITE_BUILT = "charity.new_site"


@dataclass(frozen=True)
class StandardPageEntry:
    """A page every site has. `build` makes `new_site`'s draft of it, in the language being read.
    `setting` names its chooser in Site settings; without one it's found by its slug under the
    home page, until #171 and #167 add theirs."""

    name: str
    slug: str
    build: Callable[[], object]
    setting: str = ""
    why: str = ""


def privacy_notice_body():
    """The notice is written for the charity, in the shape of the demo's: only how long it keeps
    details and who to contact are for it to fill in. It names the tick boxes as the pledge form
    labels them."""
    tick_boxes = PledgeForm.Meta.labels

    def section(heading, paragraph):
        return [
            ("heading", {"heading_text": heading, "size": "h2"}),
            ("paragraph", paragraph),
        ]

    return [
        *section(
            _("What we collect"),
            _(
                "<p>When you pledge a gift, we keep your name, email address and the message you "
                "write, and your home address and postcode if you give them. For a monthly gift "
                "you can also give a mobile number. If you pay by scanning our QR code, you can "
                "send us a screenshot of your app's receipt. When you sign up to volunteer, we "
                "keep the answers you give on the form.</p>"
            ),
        ),
        *section(
            _("What we use it for"),
            _(
                "<ul><li>To arrange your gift or your volunteering, and to thank you.</li><li>Your "
                "mobile number only to remind you each month to give, on WhatsApp or by text."
                "</li><li>Your email address for stories and appeals only if you ticked "
                "<b>%(email_updates)s</b>.</li><li>Your name, the appeal and the date on a page "
                "you can share and in our list of recent supporters only if you ticked "
                "<b>%(show_on_website)s</b>, once you've told us you've paid, and the amount once "
                "your gift has arrived.</li></ul><p>Your message is for our team only and never "
                "appears on the website.</p>"
            )
            % {
                "email_updates": tick_boxes["email_updates"],
                "show_on_website": tick_boxes["show_on_website"],
            },
        ),
        *section(
            _("Who can see it"),
            _(
                "<p>Only the members of our team who manage gifts and volunteers. We don't sell "
                "your details or share them with anyone else.</p>"
            ),
        ),
        *section(
            _("How long we keep it"),
            _("<p>[Write: how long you keep pledges and volunteer sign-ups, and why.]</p>")
            + _(
                "<p>A screenshot of a receipt is seen only by the team members who check payments. "
                "We keep it until we've checked your payment, and 30 days at most, then delete it; "
                "it isn't kept in our backups.</p>"
            ),
        ),
        *section(
            _("Seeing or deleting your details"),
            _(
                "<p>[Write: which role to contact, and how, to see, correct or delete the details "
                "you hold about someone.]</p>"
            ),
        ),
    ]


def privacy_notice():
    return StandardPage(
        title=_("Privacy notice"),
        slug="privacy",
        introduction=_("How we use the details you give us."),
        body=privacy_notice_body(),
    )


def donate():
    return DonatePage(
        title=_("Donate"),
        slug="donate",
        introduction=_("[Write: one sentence on what a gift does.]"),
        thank_you_text=_("<p>[Write: what happens next, and when you'll be in touch.]</p>"),
    )


def about():
    return StandardPage(
        title=_("About us"),
        slug="about",
        show_in_menus=True,
        introduction=_("[Write: who you are, where you work and who you help.]"),
    )


def appeals():
    return CampaignIndexPage(
        title=_("Appeals"),
        slug="appeals",
        show_in_menus=True,
        introduction=_("[Write: one sentence on what your appeals pay for.]"),
    )


def stories():
    return NewsIndexPage(
        title=_("Stories"),
        slug="stories",
        show_in_menus=True,
        introduction=_("[Write: one sentence on the stories you share here.]"),
    )


def volunteer_form():
    form = FormPage(
        title=_("Volunteer with us"),
        slug="volunteer",
        show_in_menus=True,
        intro=_("<p>[Write: what volunteers do with you, and how much time it takes.]</p>"),
        thank_you_text=_("<p>[Write: what happens next, and when you'll be in touch.]</p>"),
        subject=_("New volunteer sign-up"),
    )
    form.form_fields = [
        FormField(label=_("Your name"), field_type="singleline", required=True),
        FormField(label=_("Phone number"), field_type="singleline", required=False),
        FormField(label=_("Email address"), field_type="email", required=False),
        FormField(label=_("When are you free?"), field_type="singleline", required=False),
        FormField(label=_("How would you like to help?"), field_type="multiline", required=False),
    ]
    return form


# The one list of them, in the dashboard panel's order: the pages with a `why` first, then the menu
# sections in the standard's order. #167, #168, #169, #170 and #171 each add theirs.
STANDARD_PAGES = (
    StandardPageEntry(
        gettext_lazy("Privacy notice"),
        "privacy",
        privacy_notice,
        setting="privacy_page",
        why=gettext_lazy("needed before any form goes live"),
    ),
    StandardPageEntry(
        gettext_lazy("Donate"),
        "donate",
        donate,
        setting="donate_page",
        why=gettext_lazy("brings back the Donate button"),
    ),
    StandardPageEntry(gettext_lazy("About us"), "about", about),
    StandardPageEntry(gettext_lazy("Appeals"), "appeals", appeals),
    StandardPageEntry(gettext_lazy("Stories"), "stories", stories),
    StandardPageEntry(gettext_lazy("Volunteer with us"), "volunteer", volunteer_form),
)
