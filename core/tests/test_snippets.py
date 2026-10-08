import pytest
from django.urls import reverse
from django.utils.translation import override
from wagtail.snippets.models import get_snippet_models
from wagtail_factories import ImageFactory

# Imported via their modules: names starting with "Test" would be collected by pytest.
from core import blocks, models
from core.blocks import PartnersBlock
from core.models import Partner

pytestmark = pytest.mark.django_db


def make_testimonial(publish=False, **kwargs):
    defaults = {"quote": "The new well means my daughter is back at school.", "name": "Grace"}
    testimonial = models.Testimonial(live=False, **{**defaults, **kwargs})
    testimonial.save()
    revision = testimonial.save_revision()
    if publish:
        revision.publish()
    testimonial.refresh_from_db()
    return testimonial


def test_partner_and_testimonial_are_registered_as_snippets():
    assert {Partner, models.Testimonial} <= set(get_snippet_models())


class TestPartner:
    def test_partners_are_ordered_by_sort_order(self):
        Partner.objects.create(name="Second", sort_order=2)
        Partner.objects.create(name="First", sort_order=1)

        assert [p.name for p in Partner.objects.all()] == ["First", "Second"]

    def test_partners_block_renders_every_partner_with_logo_and_link(self):
        Partner.objects.create(
            name="Water Foundation",
            url="https://water.example.org",
            logo=ImageFactory(description="Water Foundation logo"),
        )
        Partner.objects.create(name="Local Council")
        block = PartnersBlock()

        html = block.render(block.to_python({"heading": "Our partners"}))

        assert "Our partners" in html
        assert 'href="https://water.example.org"' in html
        assert 'alt="Water Foundation logo"' in html
        assert "Local Council" in html

    def test_editors_can_list_and_search_partners_in_the_admin(self, admin_client):
        Partner.objects.create(name="Water Foundation")
        Partner.objects.create(name="Local Council")

        response = admin_client.get(reverse("wagtailsnippets_core_partner:list"), {"q": "water"})

        assert response.status_code == 200
        assert "Water Foundation" in response.content.decode()
        assert "Local Council" not in response.content.decode()


class TestTestimonial:
    def test_new_testimonials_are_drafts_until_published(self):
        testimonial = make_testimonial()

        assert testimonial.live is False
        assert testimonial.has_unpublished_changes

    def test_publishing_makes_a_testimonial_live_and_keeps_revision_history(self):
        testimonial = make_testimonial(publish=True)

        assert testimonial.live is True
        assert testimonial.revisions.count() == 1
        assert testimonial.live_revision is not None

    def test_block_hides_draft_testimonials(self):
        block = blocks.TestimonialBlock()
        draft = make_testimonial()

        assert block.render(draft).strip() == ""

    def test_block_renders_published_testimonials(self):
        block = blocks.TestimonialBlock()
        testimonial = make_testimonial(publish=True, role="Parent, Kisumu")

        html = block.render(testimonial)

        assert "my daughter is back at school" in html
        assert "Grace" in html
        assert "Parent, Kisumu" in html

    def test_can_be_previewed_before_publishing(self):
        testimonial = make_testimonial()

        response = testimonial.make_preview_request()

        assert response.status_code == 200
        assert "my daughter is back at school" in response.content.decode()

    def test_admin_listing_shows_publication_status(self, admin_client):
        make_testimonial(name="Grace")

        response = admin_client.get(reverse("wagtailsnippets_core_testimonial:list"))

        assert response.status_code == 200
        assert "Grace" in response.content.decode()
        assert "draft" in response.content.decode().lower()


class TestInNepali:
    """Partners and testimonials in the reader's language, else the main language's (#117)."""

    def test_partners_block_shows_each_partner_in_the_language_being_read(self, nepali_locale):
        partner = Partner.objects.create(name="Water Foundation")
        translation = partner.copy_for_translation(nepali_locale)
        translation.name = "जल फाउन्डेसन"
        translation.save()
        Partner.objects.create(name="Local Council")
        block = PartnersBlock()

        with override("ne"):
            html = block.render(block.to_python({"heading": ""}))

        assert "जल फाउन्डेसन" in html
        assert "Water Foundation" not in html
        assert "Local Council" in html

    def test_testimonial_block_shows_the_published_translation(self, nepali_locale):
        testimonial = make_testimonial(publish=True)
        translate_testimonial(testimonial, nepali_locale, publish=True)
        block = blocks.TestimonialBlock()

        with override("ne"):
            nepali = block.render(testimonial, context={})
        english = block.render(testimonial, context={})

        assert "नयाँ इनार" in nepali
        assert "my daughter is back at school" in english

    def test_testimonial_block_shows_the_original_until_the_translation_is_published(
        self, nepali_locale
    ):
        testimonial = make_testimonial(publish=True)
        translate_testimonial(testimonial, nepali_locale)
        block = blocks.TestimonialBlock()

        with override("ne"):
            html = block.render(testimonial, context={})

        assert "my daughter is back at school" in html

    def test_translation_of_a_testimonial_starts_as_a_draft(self, nepali_locale):
        testimonial = make_testimonial(publish=True)

        translation = testimonial.copy_for_translation(nepali_locale)
        translation.save()

        assert translation.live is False
        assert translation.live_revision is None


def translate_testimonial(testimonial, locale, publish=False):
    translation = testimonial.copy_for_translation(locale)
    translation.quote = "नयाँ इनारले गर्दा मेरी छोरी फेरि स्कुल जान थालेकी छ।"
    translation.save()
    revision = translation.save_revision()
    if publish:
        revision.publish()
    return translation


def test_chooser_searches_testimonials_in_one_language(admin_client, nepali_locale):
    """The chooser narrows by language before searching, which needs locale in the index."""
    make_testimonial(name="Grace")
    url = reverse("wagtailsnippetchoosers_core_testimonial:choose_results")

    response = admin_client.get(url, {"q": "Grace", "locale": "en"})

    assert response.status_code == 200
    assert "Grace" in response.content.decode()
