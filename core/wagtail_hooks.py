from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import InlineStyleElementHandler
from wagtail.admin.rich_text.editors.draftail.features import InlineStyleFeature
from wagtail.admin.ui.tables import LiveStatusTagColumn, UpdatedAtColumn
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from core.models import Partner, Testimonial


class PartnerViewSet(SnippetViewSet):
    model = Partner
    icon = "group"
    list_display = ["name", "url"]
    search_fields = ["name"]


class TestimonialViewSet(SnippetViewSet):
    model = Testimonial
    icon = "openquote"
    list_display = ["name", "role", LiveStatusTagColumn(), UpdatedAtColumn()]
    list_filter = ["live"]


class SupportersViewSetGroup(SnippetViewSetGroup):
    menu_label = "Supporters"
    menu_icon = "group"
    menu_order = 300
    items = (PartnerViewSet, TestimonialViewSet)


register_snippet(SupportersViewSetGroup)


@hooks.register("register_rich_text_features")
def register_highlight_feature(features):
    """A 'highlight' button that wraps text in <mark>, e.g. to pick out key figures."""
    feature_name = "mark"
    style_type = "MARK"

    features.register_editor_plugin(
        "draftail",
        feature_name,
        InlineStyleFeature(
            {
                "type": style_type,
                "label": "H",
                "description": "Highlight",
                "style": {"backgroundColor": "#f2b134"},
            }
        ),
    )
    features.register_converter_rule(
        "contentstate",
        feature_name,
        {
            "from_database_format": {"mark": InlineStyleElementHandler(style_type)},
            "to_database_format": {"style_map": {style_type: "mark"}},
        },
    )
