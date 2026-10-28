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
    SCHEDULED_UNPUBLISHING_REFUSED,
    PublishRefused,
    reasons_not_to_publish,
    refusals_to_unpublish,
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


class RefusalFormatter(LogFormatter):
    """A History entry saying why a page's scheduled publishing or expiry was refused."""

    def format_message(self, log_entry):
        return f"{self.label}: {' '.join(log_entry.data['reasons'])}"


@hooks.register("register_log_actions")
def register_refusals(actions):
    @actions.register_action(SCHEDULED_PUBLISHING_REFUSED)
    class ScheduledPublishingRefused(RefusalFormatter):
        label = "Scheduled publishing refused"

    @actions.register_action(SCHEDULED_UNPUBLISHING_REFUSED)
    class ScheduledUnpublishingRefused(RefusalFormatter):
        label = "Scheduled unpublishing refused"


def subpages_acted_on(page, user, publishing):
    """The subpages that publishing `page` with its subpages publishes (its drafts), or
    unpublishing it unpublishes (its live subpages): those `user` may."""
    subpages = page.get_descendants()
    for subpage in subpages.not_live() if publishing else subpages.live():
        permissions = subpage.permissions_for_user(user)
        if permissions.can_publish() if publishing else permissions.can_unpublish():
            yield subpage


@hooks.register("before_unpublish_page")
def check_before_unpublishing(request, page):
    """The editor's Unpublish, of the page and its live subpages if asked, is refused with why
    when the privacy notice is among them while forms link to it."""
    pages = [page]
    if request.POST.get("include_descendants"):
        pages += subpages_acted_on(page, request.user, publishing=False)
    refusals = refusals_to_unpublish(pages)
    if not refusals:
        return None
    for refusal in refusals:
        messages.error(request, str(refusal))
    return redirect("wagtailadmin_pages:edit", page.pk)


@hooks.register("before_bulk_action")
def check_every_page_before_bulk_publishing(request, action_type, objects, action):
    """Bulk publish and unpublish act on the chosen pages, and their subpages if asked, one at a
    time: check them all first, so it acts on all of them or none, naming each page that stops
    it."""
    if action_type not in ("publish", "unpublish") or not issubclass(action.model, Page):
        return None
    publishing = action_type == "publish"
    pages = list(objects)
    if action.cleaned_form.cleaned_data["include_descendants"]:
        for page in objects:
            pages += subpages_acted_on(page, request.user, publishing)
    if publishing:
        drafts = [page.specific.get_latest_revision_as_object() for page in pages]
        refusals = [
            PublishRefused(page, reasons)
            for page in drafts
            if (reasons := reasons_not_to_publish(page))
        ]
    else:
        refusals = refusals_to_unpublish(pages)
    if not refusals:
        return None
    messages.error(request, "Nothing was published." if publishing else "Nothing was unpublished.")
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
