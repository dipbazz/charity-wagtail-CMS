from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _
from wagtail.models import Locale, Site

from campaigns.forms import PledgeForm
from campaigns.models import CampaignIndexPage, DonatePage
from contact.models import FormField, FormPage
from core.models import SiteSettings, SiteSettingsText
from home.models import HomePage, StandardPage
from news.models import NewsIndexPage

NOT_NEW = (
    "This site already has pages under its home page, so nothing was changed. This command only "
    "sets up a new, empty site."
)


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


def standard_pages():
    """The standard pages that have a page type today, in the language being read and in the
    standard's order. #167, #168, #169, #170 and #171 each add theirs."""
    return [
        StandardPage(
            title=_("About us"),
            slug="about",
            show_in_menus=True,
            introduction=_("[Write: who you are, where you work and who you help.]"),
        ),
        CampaignIndexPage(
            title=_("Appeals"),
            slug="appeals",
            show_in_menus=True,
            introduction=_("[Write: one sentence on what your appeals pay for.]"),
        ),
        NewsIndexPage(
            title=_("Stories"),
            slug="stories",
            show_in_menus=True,
            introduction=_("[Write: one sentence on the stories you share here.]"),
        ),
        volunteer_form(),
        DonatePage(
            title=_("Donate"),
            slug="donate",
            introduction=_("[Write: one sentence on what a gift does.]"),
            thank_you_text=_("<p>[Write: what happens next, and when you'll be in touch.]</p>"),
        ),
        StandardPage(
            title=_("Privacy notice"),
            slug="privacy",
            introduction=_("How we use the details you give us."),
            body=privacy_notice_body(),
        ),
    ]


def still_to_do():
    """What's left once the command has run: first the pages, in the dashboard panel's order."""
    return [
        "Privacy notice: needed before any form goes live.",
        "Donate: brings back the Donate button.",
        "About us, Appeals, Stories and Volunteer with us: each joins the menu once it's live.",
        "Site settings: address, registration and payment details.",
        "DNS: point the charity's domain at this server.",
        "Email: set up sending, and add each form's address to send messages to.",
    ]


class Command(BaseCommand):
    help = (
        "Set up a new charity's site: the standard pages as drafts and a home page in each "
        "language. Refuses a site that already has pages."
    )

    def add_arguments(self, parser):
        for code, language in settings.WAGTAIL_CONTENT_LANGUAGES:
            parser.add_argument(
                f"--name-{code}", required=True, help=f"The charity's name in {language}."
            )
        parser.add_argument("--email", default="", help="The charity's main email, if it sent one.")
        parser.add_argument("--phone", default="", help="The charity's main phone, if it sent one.")

    def handle(self, *args, **options):
        homes, pages = self.set_up(options)
        # After the transaction: a setup that worked stays, even if printing it fails.
        self.report(homes, pages)

    @transaction.atomic
    def set_up(self, options):
        names = {
            code: options[f"name_{code}"].strip() for code, _ in settings.WAGTAIL_CONTENT_LANGUAGES
        }
        email = options["email"].strip()
        phone = options["phone"].strip()
        if not all(names.values()):
            raise CommandError("The charity's name is needed in every language.")
        if email:
            try:
                validate_email(email)
            except ValidationError as error:
                raise CommandError(f"{email} isn't an email address.") from error
        if phone and (
            not any(character.isdigit() for character in phone)
            or len(phone) > SiteSettings._meta.get_field("phone").max_length
        ):
            raise CommandError(f"{phone} isn't a phone number.")

        site = Site.objects.filter(is_default_site=True).first()
        home = site and site.root_page.specific
        if not isinstance(home, HomePage):
            raise CommandError(
                "The default site's root page isn't a home page, so nothing changed."
            )
        if any(page.get_children().exists() for page in [home, *home.get_translations()]):
            raise CommandError(NOT_NEW)

        main = home.locale.language_code
        with translation.override(main):
            pages = standard_pages()
        by_slug = {page.slug: page for page in pages}
        for page in pages:
            page.live = False
            home.add_child(instance=page)
            page.save_revision()

        homes = [self.name_home(home, names[main])]
        for code in names.keys() - {main}:
            homes.append(self.second_home(home, code, names[code]))

        site.site_name = names[main]
        site.save()
        self.write_settings(site, names, by_slug, email, phone)
        return homes, pages

    def name_home(self, home, name):
        home.title = name
        home.save_revision().publish()
        return home

    def second_home(self, home, code, name):
        """The site's home page in another language: its own if it has one, so the language switch
        works from day one. Translate skips `HomePage.max_count`."""
        locale = Locale.objects.get(language_code=code)
        page = home.get_translation_or_none(locale)
        page = page.specific if page else home.copy_for_translation(locale)
        return self.name_home(page, name)

    def write_settings(self, site, names, by_slug, email, phone):
        settings_ = SiteSettings.for_site(site)
        settings_.contact_email = email
        settings_.phone = phone
        settings_.donate_page = by_slug["donate"]
        settings_.privacy_page = by_slug["privacy"]
        settings_.save()
        for code, name in names.items():
            SiteSettingsText.objects.update_or_create(
                settings=settings_,
                locale=Locale.objects.get(language_code=code),
                defaults={"name": name},
            )

    def report(self, homes, pages):
        languages = dict(settings.WAGTAIL_CONTENT_LANGUAGES)
        for page in homes:
            self.stdout.write(f"Live   {self.language(languages, page)}   {page.title}")
        for page in pages:
            self.stdout.write(f"Draft  {self.language(languages, page)}   {page.title}")
        # The running site keeps its list of home pages in its own memory, which this can't clear.
        self.stdout.write(
            "\nRestart the site now, or for up to an hour its second language's home page"
            " redirects to the main one and the language switcher stays hidden."
        )
        self.stdout.write("\nStill to do:")
        for number, step in enumerate(still_to_do(), start=1):
            self.stdout.write(f"{number}. {step}")

    def language(self, languages, page):
        return languages[page.locale.language_code]
