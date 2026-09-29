import pytest
from django.core.exceptions import ValidationError
from wagtail_factories import DocumentFactory, ImageFactory

from core.blocks import (
    BaseStreamBlock,
    CallToActionBlock,
    CaptionedImageBlock,
    DocumentBlock,
    HeadingBlock,
    ImpactStatsBlock,
    QuoteBlock,
)


def render(block, data):
    return block.render(block.to_python(data))


def test_base_stream_block_offers_every_content_block():
    assert set(BaseStreamBlock.base_blocks) == {
        "heading",
        "paragraph",
        "image",
        "quote",
        "call_to_action",
        "impact_stats",
        "embed",
        "table",
        "document",
    }


def test_heading_block_renders_the_chosen_level():
    html = render(HeadingBlock(), {"heading_text": "Our mission", "size": "h3"})

    assert "<h3" in html
    assert "Our mission" in html


def test_quote_block_renders_quote_and_attribution():
    html = render(
        QuoteBlock(), {"text": "Water changed everything.", "attribution": "Grace, Kenya"}
    )

    assert "<blockquote" in html
    assert "Water changed everything." in html
    assert "Grace, Kenya" in html


def test_impact_stats_block_renders_every_statistic():
    html = render(
        ImpactStatsBlock(),
        {
            "heading": "Our impact in 2025",
            "stats": [
                {"figure": "12,000", "label": "people with clean water"},
                {"figure": "48", "label": "wells built"},
            ],
        },
    )

    assert "Our impact in 2025" in html
    assert "12,000" in html
    assert "wells built" in html


@pytest.mark.django_db
def test_captioned_image_block_shows_caption_and_photo_credit():
    image = ImageFactory(credit="Photo: Amara Okafor", description="A new well")

    html = render(CaptionedImageBlock(), {"image": image.pk, "caption": "The well in Kisumu"})

    assert "<img" in html
    assert "The well in Kisumu" in html
    assert "Photo: Amara Okafor" in html


@pytest.mark.django_db
def test_document_block_links_to_the_document():
    document = DocumentFactory(title="Annual report 2025")

    html = render(DocumentBlock(), {"document": document.pk, "link_text": ""})

    assert document.url in html
    assert "Annual report 2025" in html


class TestCallToActionBlock:
    def test_links_to_an_external_url(self):
        html = render(
            CallToActionBlock(),
            {
                "title": "Give monthly",
                "text": "",
                "button_text": "Donate",
                "page": None,
                "url": "https://example.org/donate",
            },
        )

        assert 'href="https://example.org/donate"' in html
        assert "Donate" in html

    @pytest.mark.django_db
    def test_links_to_an_internal_page(self, home_page):
        block = CallToActionBlock()
        value = block.to_python(
            {
                "title": "Volunteer",
                "text": "",
                "button_text": "Find out more",
                "page": home_page.pk,
                "url": "",
            }
        )

        assert f'href="{home_page.url}"' in block.render(value)

    def test_requires_a_page_or_a_url(self):
        block = CallToActionBlock()
        value = block.to_python(
            {"title": "Give", "text": "", "button_text": "Donate", "page": None, "url": ""}
        )

        with pytest.raises(ValidationError):
            block.clean(value)

    @pytest.mark.django_db
    def test_rejects_both_a_page_and_a_url(self, home_page):
        block = CallToActionBlock()
        value = block.to_python(
            {
                "title": "Give",
                "text": "",
                "button_text": "Donate",
                "page": home_page.pk,
                "url": "https://example.org",
            }
        )

        with pytest.raises(ValidationError):
            block.clean(value)
