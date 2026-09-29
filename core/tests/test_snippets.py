import pytest
from django.urls import reverse
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
