from django.contrib import messages
from django.shortcuts import redirect
from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import InlineStyleElementHandler
from wagtail.admin.rich_text.editors.draftail.features import InlineStyleFeature
from wagtail.admin.ui.tables import LiveStatusTagColumn, UpdatedAtColumn
from wagtail.log_actions import LogFormatter
from wagtail.models import Page
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from core.models import Partner, Testimonial
from core.publishing import (
    SCHEDULED_PUBLISHING_REFUSED,
    PublishRefused,
    latest_draft,
    reasons_not_to_publish,
)


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


@hooks.register("register_log_actions")
def register_scheduled_publishing_refused(actions):
    @actions.register_action(SCHEDULED_PUBLISHING_REFUSED)
    class ScheduledPublishingRefused(LogFormatter):
        label = "Scheduled publishing refused"

        def format_message(self, log_entry):
            return f"Scheduled publishing refused: {' '.join(log_entry.data['reasons'])}"


@hooks.register("before_bulk_action")
def check_every_page_before_bulk_publishing(request, action_type, objects, action):
    """Bulk publish publishes the chosen pages, and their drafts below if asked, one at a time:
    check them all first, so it publishes all of them or none, naming each page that stops it."""
    if action_type != "publish" or not issubclass(action.model, Page):
        return None
    pages = list(objects)
    if action.cleaned_form.cleaned_data["include_descendants"]:
        for page in objects:
            pages += [
                draft
                for draft in page.get_descendants().not_live().specific()
                if draft.permissions_for_user(request.user).can_publish()
            ]
    refusals = [
        PublishRefused(page, reasons)
        for page in map(latest_draft, pages)
        if (reasons := reasons_not_to_publish(page))
    ]
    if not refusals:
        return None
    messages.error(request, "Nothing was published.")
    for refusal in refusals:
        messages.error(request, str(refusal))
    return redirect(action.next_url)


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
