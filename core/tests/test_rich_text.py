from wagtail.admin.rich_text.converters.contentstate import ContentstateConverter

from core.blocks import RICH_TEXT_FEATURES


class TestHighlightRichTextFeature:
    def test_is_available_in_paragraph_blocks(self):
        assert "mark" in RICH_TEXT_FEATURES

    def test_highlight_survives_the_editor_round_trip(self):
        converter = ContentstateConverter(features=["mark"])
        html = '<p data-block-key="a1b2c">Every <mark>£10</mark> helps.</p>'

        stored = converter.to_database_format(converter.from_database_format(html))

        assert "<mark>£10</mark>" in stored
