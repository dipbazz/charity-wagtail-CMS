"""The `new_site` command and the home page it leaves (#175): a new charity's site starts with the
standard pages as drafts, and a home page in each language saying the site is on its way."""

import io
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import transaction
from django.utils import translation
from pytest_django.asserts import assertContains, assertNotContains
from wagtail.models import Locale, Page, Site

from campaigns.models import CampaignIndexPage, DonatePage
from contact.models import FormPage
from core.models import SiteSettings
from core.publishing import (
    ADD_RECIPIENT,
    PUBLISH_PRIVACY_NOTICE,
    PublishRefused,
    has_placeholders,
    reasons_not_to_publish,
)
from home.management.commands.new_site import standard_pages
from home.models import HomePage, StandardPage
from news.models import NewsIndexPage

pytestmark = pytest.mark.django_db

NOT_NEW = (
    "This site already has pages under its home page, so nothing was changed. This command only "
    "sets up a new, empty site."
)

# The standard's pages this command builds, by slug.
BUILT = {
    "about": ("About us", StandardPage),
    "appeals": ("Appeals", CampaignIndexPage),
    "stories": ("Stories", NewsIndexPage),
    "volunteer": ("Volunteer with us", FormPage),
    "donate": ("Donate", DonatePage),
    "privacy": ("Privacy notice", StandardPage),
}
# The standard's pages whose page type isn't built yet: each adds itself to the command.
NOT_BUILT_YET = {
    "reports and accounts": "#170",
    "get involved": "#168",
    "contact": "#167",
    "accessibility statement": "#167",
}


def new_site(**options):
    """Runs the command; what it printed."""
    out = io.StringIO()
    call_command("new_site", name_en="Bright Future", name_ne="उज्यालो भविष्य", stdout=out, **options)
    return out.getvalue()


def nepali_home(home_page):
    return home_page.get_translations().get(locale__language_code="ne").specific


def pages_under(home):
    # Not `home.get_children()`: on an instance from before the command, it still sees a leaf.
    return {page.slug: page.specific for page in Page.objects.child_of(home)}


class TestTheTree:
    def test_builds_the_standard_pages_as_drafts(self, home_page):
        new_site()

        pages = pages_under(home_page)
        assert {slug: (page.title, type(page)) for slug, page in pages.items()} == BUILT
        assert not any(page.live for page in pages.values())

    def test_each_draft_can_be_opened_from_its_latest_revision(self, home_page):
        new_site()

        for page in pages_under(home_page).values():
            assert page.get_latest_revision() is not None

    def test_the_standard_lists_no_page_this_doesnt_account_for(self):
        standard = Path(settings.BASE_DIR, "docs/site/standard.md").read_text(encoding="utf-8")
        section = standard.split("## Pages every site has")[1].split("##")[0].lower()

        left = section.split(", in each of the site's languages")[0]
        built = {title.lower() for title, _ in BUILT.values()} - {"volunteer with us"}
        for name in {"home", "the volunteer form"} | built | NOT_BUILT_YET.keys():
            assert name in left, f"{name} isn't in the standard's list"
            left = left.replace(name, "")

        # What's left is the sentence around the names, so a page added to the list shows here.
        assert re.sub(r"\W|\b(and|the|with|who|runs|charity|under|it)\b", "", left) == ""

    def test_menu_sections_show_once_live(self, home_page):
        new_site()

        pages = pages_under(home_page)
        assert {slug for slug, page in pages.items() if page.show_in_menus} == {
            "about",
            "appeals",
            "stories",
            "volunteer",
        }

    def test_the_second_language_has_only_its_home_page(self, home_page):
        new_site()

        assert nepali_home(home_page).get_children().count() == 0


class TestTheHomePages:
    def test_each_language_is_live_under_the_charitys_name(self, home_page):
        new_site()

        home_page.refresh_from_db()
        nepali = nepali_home(home_page)
        assert (home_page.title, home_page.live) == ("Bright Future", True)
        assert (nepali.title, nepali.live) == ("उज्यालो भविष्य", True)

    def test_they_carry_no_placeholder(self, home_page):
        new_site()

        home_page.refresh_from_db()
        assert not has_placeholders(home_page.specific)
        assert not has_placeholders(nepali_home(home_page))

    def test_an_empty_second_home_page_is_reused(self, home_page, nepali_home_page):
        new_site()

        assert nepali_home(home_page).pk == nepali_home_page.pk
        assert nepali_home(home_page).title == "उज्यालो भविष्य"

    def test_the_main_language_comes_from_the_site(self, home_page):
        nepali = Locale.objects.get_or_create(language_code="ne")[0]
        Page.objects.filter(pk=home_page.pk).update(locale=nepali)

        new_site()

        about = StandardPage.objects.get(slug="about")
        english_home = HomePage.objects.get(locale__language_code="en")
        assert about.title == "हाम्रो बारेमा"
        assert about.introduction.startswith("[लेख्नुहोस्:")
        assert english_home.title == "Bright Future"
        assert english_home.get_children().count() == 0


class TestThePlaceholders:
    def test_what_only_the_charity_can_write_holds_one(self, home_page):
        new_site()

        for slug, page in pages_under(home_page).items():
            assert has_placeholders(page), slug

    def test_nothing_with_one_can_go_live(self, home_page):
        new_site()

        with pytest.raises(PublishRefused):
            pages_under(home_page)["about"].get_latest_revision().publish()

    def test_the_privacy_notice_only_needs_its_two(self, home_page):
        new_site()

        notice = pages_under(home_page)["privacy"]
        blocks = notice.body.get_prep_value()
        holding = [block for block in blocks if "[Write:" in str(block["value"])]
        assert len(holding) == 2
        assert all(block["type"] == "paragraph" for block in holding)

    def test_the_volunteer_form_has_no_recipient(self, home_page):
        new_site()

        form = pages_under(home_page)["volunteer"]
        assert form.to_address == ""
        fields = form.form_fields.all()
        assert [(field.label, field.field_type, field.required) for field in fields] == [
            ("Your name", "singleline", True),
            ("Phone number", "singleline", False),
            ("Email address", "email", False),
            ("When are you free?", "singleline", False),
            ("How would you like to help?", "multiline", False),
        ]
        reasons = reasons_not_to_publish(form)
        assert ADD_RECIPIENT in reasons
        assert PUBLISH_PRIVACY_NOTICE in reasons


class TestSiteSettings:
    def test_gets_the_names_and_the_contact_details_given(self, site):
        new_site(email="hello@brightfuture.example", phone="+977 1 400 0000")

        site = Site.objects.get(pk=site.pk)
        settings_ = SiteSettings.for_site(site)
        assert site.site_name == "Bright Future"
        assert {text.locale.language_code: text.name for text in settings_.texts.all()} == {
            "en": "Bright Future",
            "ne": "उज्यालो भविष्य",
        }
        assert settings_.contact_email == "hello@brightfuture.example"
        assert settings_.phone == "+977 1 400 0000"

    def test_chooses_the_commands_own_pages(self, home_page, site):
        new_site()

        settings_ = SiteSettings.for_site(site)
        pages = pages_under(home_page)
        assert settings_.donate_page_id == pages["donate"].pk
        assert settings_.privacy_page_id == pages["privacy"].pk

    def test_writes_nothing_made_up(self, site):
        new_site()

        settings_ = SiteSettings.for_site(site)
        assert settings_.contact_email == ""
        assert settings_.phone == ""
        assert not any(text.address or text.refund_policy for text in settings_.texts.all())

    def test_refuses_an_email_that_isnt_one(self, home_page):
        with pytest.raises(CommandError, match="email"):
            new_site(email="not an address")

        assert not Page.objects.child_of(home_page).exists()


class TestWhatItRefuses:
    def test_a_site_with_pages_under_its_home_page(self, home_page):
        home_page.add_child(instance=StandardPage(title="Ours", slug="ours"))

        with pytest.raises(CommandError) as refused:
            new_site()

        assert str(refused.value) == NOT_NEW
        assert list(Page.objects.child_of(home_page).values_list("slug", flat=True)) == ["ours"]
        home_page.refresh_from_db()
        assert home_page.title == "Home"

    def test_a_site_with_pages_under_its_second_home_page(self, home_page, nepali_home_page):
        nepali_home_page.add_child(instance=StandardPage(title="हाम्रो", slug="ours"))

        with pytest.raises(CommandError) as refused:
            new_site()

        assert str(refused.value) == NOT_NEW
        assert not Page.objects.child_of(home_page).exists()

    def test_running_it_twice(self, home_page):
        new_site()

        with pytest.raises(CommandError) as refused:
            new_site()

        assert str(refused.value) == NOT_NEW

    def test_a_site_whose_root_isnt_a_home_page(self, site, home_page):
        root = Page.get_first_root_node()
        other = root.add_child(instance=Page(title="Welcome", slug="welcome"))
        Site.objects.filter(pk=site.pk).update(root_page=other)

        with pytest.raises(CommandError, match="home page"):
            new_site()

    def test_a_failure_changes_nothing_and_it_can_run_again(self, home_page, monkeypatch):
        def fail(*args, **kwargs):
            raise RuntimeError("the disk is full")

        with monkeypatch.context() as patch:
            patch.setattr(SiteSettings, "save", fail)
            with pytest.raises(RuntimeError), transaction.atomic():
                new_site()

        assert not Page.objects.child_of(home_page).exists()
        home_page.refresh_from_db()
        assert home_page.title == "Home"

        new_site()
        assert pages_under(home_page).keys() == BUILT.keys()


class TestWhatItPrints:
    def test_each_page_and_what_is_left(self):
        printed = new_site()

        assert "Live   English   Bright Future" in printed
        assert "Live   नेपाली   उज्यालो भविष्य" in printed
        assert "Draft  English   About us" in printed
        order = [printed.index(name) for name in ("Still to do", "1. Privacy notice", "2. Donate")]
        assert order == sorted(order)
        for still_to_do in ("Site settings", "DNS", "Email"):
            assert still_to_do in printed


class TestTheDayOneHomePage:
    @pytest.fixture
    def built(self, home_page):
        new_site(email="hello@brightfuture.example", phone="+977 1 400 0000")
        return HomePage.objects.get(pk=home_page.pk)

    def test_says_the_site_is_on_its_way(self, client, built):
        response = client.get("/")

        assertContains(response, "<h1", count=1)
        assertContains(response, "Bright Future</h1>")
        assertContains(response, '<p class="lead">Our new website is on its way.</p>', html=True)
        assertContains(response, 'href="mailto:hello@brightfuture.example"')
        assertContains(response, 'href="tel:+97714000000"')

    def test_in_the_second_language_too(self, client, built):
        response = client.get("/ne/")

        assertContains(response, "उज्यालो भविष्य</h1>")
        assertContains(response, "हाम्रो नयाँ वेबसाइट बन्दै छ।")

    def test_its_title_says_the_name_once(self, client, built):
        html = client.get("/").content.decode()

        assert html.split("</title>")[0].split("<title>")[1].count("Bright Future") == 1

    def test_stays_out_of_search_results(self, client, built):
        assertContains(client.get("/"), '<meta name="robots" content="noindex">')

    def test_leaves_out_the_contact_list_without_details(self, client, home_page):
        new_site()

        assertNotContains(client.get("/"), "day-one-contact")

    def test_shows_no_menu_or_donate_button_yet(self, client, built):
        response = client.get("/")

        assertNotContains(response, 'href="/donate/"')
        assertNotContains(response, 'href="/about/"')

    @pytest.mark.parametrize(
        "written",
        [{"hero_heading": "Clean water"}, {"hero_text": "For everyone."}],
        ids=["heading", "text"],
    )
    def test_ends_once_the_hero_is_written(self, client, built, written):
        for name, value in written.items():
            setattr(built, name, value)
        built.save_revision().publish()

        response = client.get("/")

        assertNotContains(response, "Our new website is on its way.")
        assertNotContains(response, 'content="noindex"')

    def test_ends_once_the_body_is_written(self, client, built):
        built.body = [("paragraph", "<p>Who we are.</p>")]
        built.save_revision().publish()

        assertNotContains(client.get("/"), "Our new website is on its way.")

    def test_a_hero_image_alone_doesnt_end_it(self, built):
        built.hero_image_id = 1

        assert built.on_day_one

    def test_nepali_placeholders_start_the_way_the_guard_looks_for(self):
        with translation.override("ne"):
            pages = standard_pages()

        assert all(has_placeholders(page) for page in pages)
