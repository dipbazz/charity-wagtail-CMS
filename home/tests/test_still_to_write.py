"""The dashboard panel listing a site's standard pages that are still to write (#175)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page, PageLogEntry, Site

from core.models import SiteSettings
from home.management.commands.new_site import standard_pages
from home.models import StandardPage
from home.standard_site import NEW_SITE_BUILT, STANDARD_PAGES
from home.wagtail_hooks import still_to_write as panel

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(django_user_model):
    return django_user_model.objects.create_superuser("admin", password="pw")


def built_site(home_page):
    call_command("new_site", "--no-input", "--name-en=Hope", "--name-ne=आशा", stdout=StringIO())
    return Site.objects.get(is_default_site=True)


def statuses(group):
    return [(row.title, row.status) for row in group.rows]


def write_and_publish(page):
    """A standard page as an editor leaves it: written and live."""
    page = page.specific
    written = {
        "introduction": "Written.",
        "intro": "<p>Written.</p>",
        "thank_you_text": "<p>Written.</p>",
        "to_address": "team@example.org",
    }
    for name, value in written.items():
        if hasattr(page, name):
            setattr(page, name, value)
    if page.slug == "privacy":
        page.body = [("paragraph", "<p>Written.</p>")]
    page.save_revision().publish()
    return Page.objects.get(pk=page.pk).specific


def finish_every_page(site):
    main_pages = [Page.objects.get(slug=standard.slug) for standard in STANDARD_PAGES]
    for page in main_pages:
        write_and_publish(page)
    for locale in [home.locale for home in site.root_page.get_translations()]:
        for page in main_pages:
            write_and_publish(page.specific.copy_for_translation(locale, alias=False))


def test_the_panel_lists_the_pages_new_site_builds():
    assert {standard.slug for standard in STANDARD_PAGES} == {
        page.slug for page in standard_pages()
    }


class TestTheCommandsDrafts:
    def test_rows_come_in_the_decided_order_main_language_first(self, home_page, admin):
        site = built_site(home_page)
        main, second = panel(admin, site).groups

        assert main.language == "English"
        assert [row.title for row in main.rows] == [
            "Privacy notice",
            "Donate",
            "About us",
            "Appeals",
            "Stories",
            "Volunteer with us",
        ]
        assert second.language == "नेपाली"
        assert {row.status for row in second.rows} == {"Translate after publishing"}

    def test_a_draft_with_placeholders_says_so_and_links_to_its_edit_page(self, home_page, admin):
        site = built_site(home_page)
        about = Page.objects.get(slug="about")

        row = next(r for r in panel(admin, site).groups[0].rows if r.title == "About us")

        assert row.status == "Has [Write: …] text"
        assert row.edit_url == reverse("wagtailadmin_pages:edit", args=[about.pk])

    def test_the_count_covers_every_standard_page_in_each_language(self, home_page, admin):
        site = built_site(home_page)

        result = panel(admin, site)

        assert (result.left, result.total) == (12, 12)

    def test_the_privacy_notice_and_donate_say_why_they_come_first(self, home_page, admin):
        rows = panel(admin, built_site(home_page)).groups[0].rows

        assert rows[0].why == "needed before any form goes live"
        assert rows[1].why == "brings back the Donate button"
        assert rows[2].why == ""


class TestStatuses:
    def test_a_written_draft_says_draft(self, home_page, admin):
        site = built_site(home_page)
        about = StandardPage.objects.get(slug="about")
        about.introduction = "Written."
        about.save_revision()

        assert ("About us", "Draft") in statuses(panel(admin, site).groups[0])

    def test_a_live_page_leaves_its_own_row_and_can_be_translated(self, home_page, admin):
        site = built_site(home_page)
        about = write_and_publish(Page.objects.get(slug="about"))

        main, second = panel(admin, site).groups

        assert "About us" not in [row.title for row in main.rows]
        row = next(r for r in second.rows if r.title == "About us")
        assert row.status == "Not translated yet"
        assert row.translate_url == reverse(
            "simple_translation:submit_page_translation", args=[about.pk]
        )

    def test_an_unpublished_page_comes_back(self, home_page, admin):
        site = built_site(home_page)
        about = write_and_publish(Page.objects.get(slug="about"))
        about.unpublish()

        assert ("About us", "Draft") in statuses(panel(admin, site).groups[0])

    def test_a_setting_left_empty_is_not_set_and_links_to_site_settings(self, home_page, admin):
        site = built_site(home_page)
        settings = SiteSettings.for_site(site)
        settings.privacy_page = None
        settings.save()

        row = panel(admin, site).groups[0].rows[0]

        assert (row.title, row.status) == ("Privacy notice", "Not set")
        assert row.edit_url is None
        assert row.settings_url == reverse(
            "wagtailsettings:edit", args=["core", "sitesettings", site.pk]
        )


class TestWhoCanFollowTheLinks:
    def test_an_editor_gets_edit_links(self, home_page, editor):
        rows = panel(editor, built_site(home_page)).groups[0].rows

        assert all(row.edit_url for row in rows)

    def test_no_edit_link_for_someone_who_cant_edit_the_page(self, home_page, editor):
        site = built_site(home_page)
        editor.groups.clear()

        rows = panel(editor, site).groups[0].rows

        assert all(row.edit_url is None for row in rows)

    def test_no_translate_link_without_the_permission(self, home_page, editor):
        site = built_site(home_page)
        write_and_publish(Page.objects.get(slug="about"))
        editor.groups.clear()

        rows = panel(editor, site).groups[1].rows

        assert all(row.translate_url is None for row in rows)


class TestAHandBuiltSite:
    def test_finds_its_pages_by_slug_under_the_home_page(self, home_page, admin):
        about = StandardPage(title="Who we are", slug="about", introduction="Written.")
        home_page.add_child(instance=about)

        result = panel(admin, Site.objects.get(is_default_site=True))

        titles = [row.title for row in result.groups[0].rows]
        assert "Who we are" not in titles
        assert "About us" not in titles
        assert ("Appeals", "Not set") in statuses(result.groups[0])

    def test_a_missing_section_has_no_link_as_no_setting_chooses_it(self, home_page, admin, site):
        row = next(r for r in panel(admin, site).groups[0].rows if r.title == "Appeals")

        assert row.settings_url is None

    def test_nothing_left_never_claims_the_site_is_done(self, home_page, admin):
        site = built_site(home_page)
        PageLogEntry.objects.filter(action=NEW_SITE_BUILT).delete()
        finish_every_page(site)
        settings = SiteSettings.for_site(site)
        settings.charity_number = "123"
        settings.save()

        result = panel(admin, site)

        assert not result.groups
        assert not result.all_done


class TestWhenEveryPageIsDone:
    def finished(self, home_page):
        site = built_site(home_page)
        finish_every_page(site)
        settings = SiteSettings.for_site(site)
        settings.charity_number = "123"
        settings.save()
        return site

    def test_a_site_the_command_built_says_so(self, home_page, admin):
        result = panel(admin, self.finished(home_page))

        assert result.all_done
        assert not result.groups

    def test_the_line_goes_seven_days_after_the_last_page_went_live(self, home_page, admin):
        site = self.finished(home_page)
        Page.objects.exclude(pk=site.root_page.pk).update(
            last_published_at=timezone.now() - timedelta(days=8)
        )

        assert not panel(admin, site).all_done

    def test_it_comes_back_after_an_unpublish(self, home_page, admin):
        site = self.finished(home_page)
        Page.objects.get(slug="about", locale=site.root_page.locale).specific.unpublish()

        result = panel(admin, site)

        assert not result.all_done
        assert ("About us", "Draft") in statuses(result.groups[0])


class TestRegistrationReminder:
    def test_asks_while_settings_have_no_registration(self, home_page, admin):
        site = built_site(home_page)

        assert panel(admin, site).add_registration_url == reverse(
            "wagtailsettings:edit", args=["core", "sitesettings", site.pk]
        )

    def test_gone_once_settings_have_it(self, home_page, admin):
        site = built_site(home_page)
        settings = SiteSettings.for_site(site)
        settings.charity_number = "123"
        settings.save()

        assert panel(admin, site).add_registration_url is None


class TestOnTheDashboard:
    def test_it_is_shown_first_with_its_count(self, home_page, admin, client):
        built_site(home_page)
        client.force_login(admin)

        html = client.get(reverse("wagtailadmin_home")).content.decode()

        assert "Pages still to write: 12 of 12" in html
        assert html.index("Pages still to write") < html.index("Fundraising overview")

    def test_a_site_with_nothing_to_say_shows_no_panel(self, home_page, admin, client):
        site = built_site(home_page)
        finish_every_page(site)
        PageLogEntry.objects.filter(action=NEW_SITE_BUILT).delete()
        settings = SiteSettings.for_site(site)
        settings.charity_number = "123"
        settings.save()
        client.force_login(admin)

        assert b"still-to-write" not in client.get(reverse("wagtailadmin_home")).content
