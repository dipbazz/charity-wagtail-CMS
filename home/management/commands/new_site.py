from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import translation
from django.utils.translation import get_language_info
from wagtail.log_actions import log
from wagtail.models import Locale, Site

from core.models import SiteSettings, SiteSettingsText
from home.models import HomePage
from home.standard_site import NEW_SITE_BUILT, STANDARD_PAGES

NOT_NEW = (
    "This site already has pages under its home page, so nothing was changed. This command only "
    "sets up a new, empty site."
)


def standard_pages():
    """The standard pages that have a page type today, in the language being read and in the
    dashboard panel's order."""
    return [standard.build() for standard in STANDARD_PAGES]


def still_to_do():
    """What's left once the command has run: first the pages, in the dashboard panel's order. In
    English, like the rest of what the command prints."""
    with translation.override("en"):
        first = [f"{standard.name}: {standard.why}." for standard in STANDARD_PAGES if standard.why]
        menu = [str(standard.name) for standard in STANDARD_PAGES if not standard.why]
    return [
        *first,
        f"{', '.join(menu[:-1])} and {menu[-1]}: each joins the menu once it's live.",
        "Site settings: address, registration and payment details.",
        "DNS: point the charity's domain at this server.",
        "Email: set up sending, and add each form's address to send messages to.",
    ]


def clean_name(value):
    value = value.strip()
    if not value:
        raise CommandError("The charity's name is needed in every language.")
    return value


def clean_email(value):
    value = value.strip()
    if value:
        try:
            validate_email(value)
        except ValidationError as error:
            raise CommandError(f"{value} isn't an email address.") from error
    return value


def clean_phone(value):
    value = value.strip()
    if value and (
        not any(character.isdigit() for character in value)
        or len(value) > SiteSettings._meta.get_field("phone").max_length
    ):
        raise CommandError(f"{value} isn't a phone number.")
    return value


def questions():
    """What the command asks, in order, as (option, question, clean); each also has its own
    `--option`. A new value is one more line here. Languages are named in English: a console that
    can't print Nepali can still ask."""
    return [
        *(
            (f"name_{code}", f"Charity's name in {get_language_info(code)['name']}", clean_name)
            for code, _language in settings.WAGTAIL_CONTENT_LANGUAGES
        ),
        ("email", "Main email (optional, Enter to skip)", clean_email),
        ("phone", "Main phone (optional, Enter to skip)", clean_phone),
    ]


class Command(BaseCommand):
    help = (
        "Set up a new charity's site, asking for each value in turn: the standard pages as drafts "
        "and a home page in each language. Refuses a site that already has pages."
    )

    def add_arguments(self, parser):
        for option, question, _clean in questions():
            parser.add_argument(f"--{option.replace('_', '-')}", help=f"{question}.")
        parser.add_argument(
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Ask nothing: use only the values given here.",
        )

    def handle(self, *args, **options):
        site, home = self.site_to_set_up()
        answers = {
            option: self.answer(options, option, question, clean)
            for option, question, clean in questions()
        }
        homes, pages = self.set_up(site, home, answers)
        # After the transaction: a setup that worked stays, even if printing it fails.
        self.report(homes, pages)

    def site_to_set_up(self):
        """Checked before asking anything, so nobody answers questions for a site it refuses."""
        site = Site.objects.filter(is_default_site=True).first()
        home = site and site.root_page.specific
        if not isinstance(home, HomePage):
            raise CommandError(
                "The default site's root page isn't a home page, so nothing changed."
            )
        if any(page.get_children().exists() for page in [home, *home.get_translations()]):
            raise CommandError(NOT_NEW)
        return site, home

    def answer(self, options, option, question, clean):
        """A value given to the command is used as it is, and refused if it's wrong; one typed is
        asked for again."""
        if options[option] is not None or not options["interactive"]:
            return clean(options[option] or "")
        while True:
            try:
                return clean(input(f"{question}: "))
            except CommandError as error:
                self.stderr.write(str(error))
            except (KeyboardInterrupt, EOFError) as stopped:
                raise CommandError("Stopped, so nothing was changed.") from stopped

    @transaction.atomic
    def set_up(self, site, home, answers):
        names = {
            code: answers[f"name_{code}"] for code, _language in settings.WAGTAIL_CONTENT_LANGUAGES
        }
        email = answers["email"]
        phone = answers["phone"]

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
        # What lets the dashboard panel say this site's standard pages are done; a hand-built
        # site is never told that.
        log(instance=home, action=NEW_SITE_BUILT)
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
