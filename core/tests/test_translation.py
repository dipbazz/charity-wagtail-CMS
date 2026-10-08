"""Editors write a page in one language and translate it later (#114).

Wagtail's simple_translation app adds a Translate action that copies a page into the other
language as a draft. Every test logs in as an editor or moderator, not a superuser, because a
superuser can do everything and would hide a missing permission.
"""

import pytest
from django.urls import reverse
from wagtail.models import Locale
from wagtail.test.utils.form_data import nested_form_data, rich_text, streamfield

# Imported via the module: names starting with "Test" would be collected by pytest.
from core import models
from core.models import Partner
from home.models import StandardPage

pytestmark = pytest.mark.django_db


def add_page(parent, **fields):
    page = StandardPage(**fields)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


def page_form(**fields):
    return nested_form_data(
        {
            "introduction": "",
            "body": streamfield([("paragraph", rich_text("<p>सबैका लागि सफा पानी</p>"))]),
            **fields,
        }
    )


@pytest.fixture
def about(home_page):
    return add_page(
        home_page,
        title="About us",
        slug="about",
        body=[("paragraph", "<p>Clean water for everyone</p>")],
    )


def test_editor_sees_the_translate_button_on_an_english_page(client, editor, about):
    client.force_login(editor)

    html = client.get(reverse("wagtailadmin_pages:edit", args=[about.pk])).content.decode()

    assert reverse("simple_translation:submit_page_translation", args=[about.pk]) in html


def test_translating_copies_the_page_into_nepali_as_a_draft(
    client, editor, about, nepali_home_page
):
    client.force_login(editor)
    nepali = Locale.objects.get(language_code="ne")

    response = client.post(
        reverse("simple_translation:submit_page_translation", args=[about.pk]),
        {"locales": [nepali.pk]},
    )

    translation = about.get_translation(nepali).specific
    assert response.status_code == 302
    assert response.url == reverse("wagtailadmin_pages:edit", args=[translation.pk])
    assert not translation.live
    assert translation.get_parent().pk == nepali_home_page.pk
    assert translation.slug == "about"
    assert "Clean water for everyone" in str(translation.body)
    # Still a draft, so Nepali readers get the English page until it's published.
    assert client.get("/ne/about/").url == "/about/"


def test_moderator_publishes_a_translation_and_it_is_served_in_nepali(
    client, editor, moderator, about, nepali_home_page
):
    nepali = Locale.objects.get(language_code="ne")
    client.force_login(editor)
    client.post(
        reverse("simple_translation:submit_page_translation", args=[about.pk]),
        {"locales": [nepali.pk]},
    )
    translation = about.get_translation(nepali)
    client.force_login(moderator)

    client.post(
        reverse("wagtailadmin_pages:edit", args=[translation.pk]),
        page_form(title="हाम्रो बारेमा", slug="about", **{"action-publish": "publish"}),
    )

    response = client.get("/ne/about/")
    assert response.status_code == 200
    assert "हाम्रो बारेमा" in response.content.decode()
    assert client.get("/about/").status_code == 200


class TestNepaliOnlyPage:
    """A page can exist in Nepali only, with no English version to wait for."""

    @pytest.fixture
    def nepali_only(self, client, editor, moderator, nepali_home_page):
        client.force_login(editor)
        client.post(
            reverse("wagtailadmin_pages:add", args=("home", "standardpage", nepali_home_page.pk)),
            page_form(title="धारा मर्मत", slug="tap-repair", **{"action-submit": "submit"}),
        )
        page = StandardPage.objects.get(slug="tap-repair")
        assert not page.live  # editors draft; moderators publish
        client.force_login(moderator)
        client.post(
            reverse("wagtailadmin_pages:edit", args=[page.pk]),
            page_form(title="धारा मर्मत", slug="tap-repair", **{"action-publish": "publish"}),
        )
        client.logout()
        page.refresh_from_db()
        return page

    def test_publishes_with_no_english_version(self, nepali_only):
        assert nepali_only.live
        assert nepali_only.locale.language_code == "ne"
        assert not nepali_only.get_translations().exists()

    def test_is_served_in_nepali(self, client, nepali_only):
        response = client.get("/ne/tap-repair/")

        html = response.content.decode()
        assert response.status_code == 200
        assert '<html lang="ne"' in html
        assert "सबैका लागि सफा पानी" in html

    def test_has_no_english_address(self, client, nepali_only):
        assert client.get("/tap-repair/").status_code == 404

    def test_editor_can_translate_it_into_english_later(self, client, editor, nepali_only):
        english = Locale.objects.get(language_code="en")
        client.force_login(editor)

        client.post(
            reverse("simple_translation:submit_page_translation", args=[nepali_only.pk]),
            {"locales": [english.pk]},
        )

        translation = nepali_only.get_translation(english)
        assert not translation.live
        assert translation.get_parent().specific.locale == english
        # Same address in both languages; only the /ne/ prefix differs.
        assert translation.slug == "tap-repair"


def test_slugs_made_from_a_title_are_in_latin_letters(client, editor, nepali_home_page):
    """Slugs stay in English in both languages, so a page's addresses differ only by /ne/.

    Wagtail makes the slug from the title in the browser. With Unicode slugs it would drop the
    Devanagari vowel signs, turning धारा मर्मत into धर-मरमत, and Django can't validate most Nepali
    words as slugs anyway. With Latin-only slugs a Nepali title leaves the slug empty, so the
    editor types an English one.
    """
    client.force_login(editor)

    html = client.get(
        reverse("wagtailadmin_pages:add", args=("home", "standardpage", nepali_home_page.pk))
    ).content.decode()

    assert 'data-controller="w-slug"' in html
    # Django leaves out a false attribute, and Wagtail's slug script then keeps Latin letters only.
    assert "data-w-slug-allow-unicode-value" not in html


def test_page_explorer_status_panel_shows_the_language(client, editor, nepali_home_page):
    # Wagtail labels rows with their language only at the root, where both home pages are; below
    # that, the status panel (the ⓘ button) names the language and links to the translations.
    add_page(nepali_home_page, title="धारा मर्मत", slug="tap-repair")
    client.force_login(editor)

    html = client.get(reverse("wagtailadmin_explore", args=[nepali_home_page.pk])).content.decode()

    assert "नेपाली" in html
    assert (
        reverse(
            "wagtailadmin_explore",
            args=[nepali_home_page.get_translation(Locale.objects.get(language_code="en")).pk],
        )
        in html
    )


def test_page_explorer_root_labels_each_home_page_with_its_language(
    client, editor, nepali_home_page
):
    client.force_login(editor)

    html = client.get(reverse("wagtailadmin_explore_root")).content.decode()

    assert "नेपाली" in html
    assert "English" in html


class TestTranslatingSnippets:
    """Editors translate partners and testimonials with the same Translate action (#117)."""

    def translate(self, client, snippet):
        nepali = Locale.objects.get(language_code="ne")
        model = snippet._meta
        response = client.post(
            reverse(
                "simple_translation:submit_snippet_translation",
                args=[model.app_label, model.model_name, snippet.pk],
            ),
            {"locales": [nepali.pk]},
        )
        assert response.status_code == 302
        return snippet.get_translation(nepali)

    def test_editor_sees_translate_in_the_partner_listing(self, client, editor):
        partner = Partner.objects.create(name="Water Foundation")
        client.force_login(editor)

        html = client.get(reverse("wagtailsnippets_core_partner:list")).content.decode()

        url = reverse(
            "simple_translation:submit_snippet_translation", args=["core", "partner", partner.pk]
        )
        assert url in html

    def test_editor_translates_a_partner(self, client, editor):
        partner = Partner.objects.create(name="Water Foundation", url="https://example.org")
        client.force_login(editor)

        translation = self.translate(client, partner)

        assert (translation.name, translation.url) == ("Water Foundation", "https://example.org")

    def test_editor_translates_a_testimonial_into_a_draft(self, client, editor, moderator):
        testimonial = models.Testimonial(quote="The well is open.", name="Grace", live=False)
        testimonial.save()
        testimonial.save_revision().publish()
        # A change still waiting for a moderator mustn't go live through its translation.
        testimonial.quote = "Unapproved wording"
        testimonial.save_revision()
        client.force_login(editor)

        translation = self.translate(client, testimonial)

        assert translation.live is False
        assert not models.Testimonial.objects.filter(live=True, quote="Unapproved wording").exists()
