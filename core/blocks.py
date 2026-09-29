from django.core.exceptions import ValidationError
from wagtail import blocks
from wagtail.blocks import StructBlockValidationError
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

RICH_TEXT_FEATURES = ["h2", "h3", "bold", "italic", "link", "document-link", "ol", "ul"]


class HeadingBlock(blocks.StructBlock):
    heading_text = blocks.CharBlock(form_classname="title")
    size = blocks.ChoiceBlock(
        choices=[("h2", "H2"), ("h3", "H3"), ("h4", "H4")],
        default="h2",
    )

    class Meta:
        icon = "title"
        template = "core/blocks/heading_block.html"


class CaptionedImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)

    class Meta:
        icon = "image"
        template = "core/blocks/captioned_image_block.html"


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock()
    attribution = blocks.CharBlock(required=False)

    class Meta:
        icon = "openquote"
        template = "core/blocks/quote_block.html"


class CallToActionBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    text = blocks.TextBlock(required=False)
    button_text = blocks.CharBlock(default="Donate")
    page = blocks.PageChooserBlock(required=False, help_text="Link to a page on this site…")
    url = blocks.URLBlock(required=False, help_text="…or to an external address.")

    class Meta:
        icon = "pick"
        template = "core/blocks/call_to_action_block.html"

    def clean(self, value):
        value = super().clean(value)
        if bool(value["page"]) == bool(value["url"]):
            error = ValidationError("Choose either a page or a URL.")
            raise StructBlockValidationError(block_errors={"page": error, "url": error})
        return value

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["href"] = value["page"].url if value["page"] else value["url"]
        return context


class StatBlock(blocks.StructBlock):
    figure = blocks.CharBlock(help_text="e.g. 12,000 or 95%")
    label = blocks.CharBlock()


class ImpactStatsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    stats = blocks.ListBlock(StatBlock(), min_num=1, max_num=4)

    class Meta:
        icon = "table"
        template = "core/blocks/impact_stats_block.html"


class DocumentBlock(blocks.StructBlock):
    document = DocumentChooserBlock()
    link_text = blocks.CharBlock(required=False, help_text="Defaults to the document title.")

    class Meta:
        icon = "doc-full"
        template = "core/blocks/document_block.html"


class BaseStreamBlock(blocks.StreamBlock):
    heading = HeadingBlock()
    paragraph = blocks.RichTextBlock(features=RICH_TEXT_FEATURES, icon="pilcrow")
    image = CaptionedImageBlock()
    quote = QuoteBlock()
    call_to_action = CallToActionBlock()
    impact_stats = ImpactStatsBlock()
    embed = EmbedBlock(help_text="A YouTube or Vimeo link", icon="media")
    table = TableBlock()
    document = DocumentBlock()
