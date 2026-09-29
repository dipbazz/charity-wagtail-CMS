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
