"""What stops a page going live (#175).

A page can't go live while it holds placeholder text ("[Write: …]"), while it collects personal
details and its site's privacy notice isn't live, or while it's a form that emails nobody.
`reasons_not_to_publish` is the one check; every route that publishes asks it: the editor's form,
bulk publish, workflow approval, scheduled publishing and code (`PublishGuardMixin`).
"""

import logging
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags
from modelcluster.fields import ParentalKey
from wagtail.admin.forms import WagtailAdminPageForm
from wagtail.blocks import StreamBlockValidationError, StreamValue
from wagtail.contrib.forms.forms import WagtailAdminFormPageForm
from wagtail.contrib.forms.models import AbstractEmailForm
from wagtail.fields import StreamField
from wagtail.log_actions import log
from wagtail.models import COMMENTS_RELATION_NAME, Page, Revision

from core.models import SiteSettings

logger = logging.getLogger(__name__)

# The History entry of a page whose scheduled publishing was refused.
SCHEDULED_PUBLISHING_REFUSED = "charity.publish.scheduled.refused"

# How each placeholder starts, in each language one is written in. A placeholder is one line in
# square brackets, such as "[Write: one sentence on what your charity does and where.]".
PLACEHOLDER_STARTS = {"en": "[Write:", "ne": "[लेख्नुहोस्:"}
PLACEHOLDER = re.compile(
    "|".join(re.escape(start) for start in PLACEHOLDER_STARTS.values()), re.IGNORECASE
)

# The admin is in English only, so these aren't marked for translation.
REPLACE_PLACEHOLDERS = "Replace the text in [square brackets] with your own before publishing."
PUBLISH_PRIVACY_NOTICE = "Publish the privacy notice first: this form collects personal details."
ADD_RECIPIENT = "Add the email address that gets each message before publishing."

# The fields every page has that an editor writes; the rest are Wagtail's own.
PAGE_FIELDS_WRITTEN = ("title", "seo_title", "search_description")


def has_placeholder(value):
    """Whether a field's value holds placeholder text, in plain or rich text or in any block."""
    if isinstance(value, StreamValue):
        value = value.get_prep_value()
    if isinstance(value, str):
        return bool(PLACEHOLDER.search(strip_tags(value)))
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(has_placeholder(item) for item in value)
    return False


def written_fields(model):
    """The names of the fields of `model` that an editor writes text in."""
    page_fields = {field.name for field in Page._meta.concrete_fields}
    return [
        field.name
        for field in model._meta.concrete_fields
        if isinstance(field, models.CharField | models.TextField | StreamField)
        and (field.name not in page_fields or field.name in PAGE_FIELDS_WRITTEN)
    ]


def fields_with_placeholders(obj):
    """The written fields of `obj`, a page or one of its rows, that hold a placeholder."""
    return [name for name in written_fields(type(obj)) if has_placeholder(getattr(obj, name))]


def rows(page):
    """The page's own rows, such as a form's fields or the Donate page's amounts.

    A page from a revision holds its rows in memory, as they were when the revision was saved.
    """
    for relation in page._meta.related_objects:
        if isinstance(relation.remote_field, ParentalKey) and relation.name != (
            COMMENTS_RELATION_NAME
        ):
            yield from getattr(page, relation.get_accessor_name()).all()


def has_placeholders(page):
    return bool(fields_with_placeholders(page)) or any(
        fields_with_placeholders(row) for row in rows(page)
    )


def privacy_notice_is_live(site):
    """Whether the privacy notice chosen in the site's settings is published."""
    notice = site and SiteSettings.for_site(site).privacy_page
    return notice is not None and notice.live


def what_a_form_lacks(page, site):
    """What a page with a form lacks to go live, as (field, message) pairs: a live privacy notice
    (no field of the page's) and an address to send messages to."""
    lacks = []
    if page.collects_personal_details and not privacy_notice_is_live(site):
        lacks.append((None, PUBLISH_PRIVACY_NOTICE))
    if isinstance(page, AbstractEmailForm) and not page.to_address.strip():
        lacks.append(("to_address", ADD_RECIPIENT))
    return lacks


def latest_draft(page):
    """The page as publishing it now would make it: its latest revision."""
    revision = page.get_latest_revision()
    return revision.as_object() if revision else page.specific


def reasons_not_to_publish(page, site=None):
    """Why `page`, as it would be published, can't go live: [] if it can.

    `site` is the page's site, found from the page if not given.
    """
    reasons = [REPLACE_PLACEHOLDERS] if has_placeholders(page) else []
    return reasons + [message for _, message in what_a_form_lacks(page, site or page.get_site())]


def placeholder_error(value):
    """The error for a field holding a placeholder; in a StreamField, on each block holding one."""
    if isinstance(value, StreamValue):
        return StreamBlockValidationError(
            block_errors={
                index: ValidationError(REPLACE_PLACEHOLDERS)
                for index, block in enumerate(value.get_prep_value())
                if has_placeholder(block)
            }
        )
    return ValidationError(REPLACE_PLACEHOLDERS)


# The editor's buttons that send a page live, or to a moderator to publish.
GOING_LIVE = ("action-publish", "action-submit", "action-restart-workflow")


class PublishCheckFormMixin:
    """For a page's admin form: Publish, Submit and Approve are refused for what
    `reasons_not_to_publish` stops, each error where the editor can fix it. Drafts save."""

    def is_valid(self):
        valid = super().is_valid()
        if self.goes_live():
            valid = self.can_go_live() and valid
        return valid

    def goes_live(self):
        approving = self.data.get("workflow-action-name") == "approve"
        return any(self.data.get(button) for button in GOING_LIVE) or bool(
            self.data.get("action-workflow-action") and approving
        )

    def can_go_live(self):
        """Adds an error for each reason the page, as the form would save it, can't go live."""
        rows = [
            form
            for name, formset in self.formsets.items()
            if name != "comments"
            for form in formset.forms
            if not getattr(form, "cleaned_data", {}).get("DELETE")
        ]
        can = True
        for form in [self, *rows]:
            for name in fields_with_placeholders(form.instance):
                error = placeholder_error(getattr(form.instance, name))
                form.add_error(name if name in form.fields else None, error)
                can = False
        for field, message in what_a_form_lacks(self.instance, self.parent_page.get_site()):
            self.add_error(field, message)
            can = False
        return can


class PageForm(PublishCheckFormMixin, WagtailAdminPageForm):
    """The admin form of every page type but those whose form editors build."""


class FormPageForm(PublishCheckFormMixin, WagtailAdminFormPageForm):
    """The admin form of a page whose form editors build (Wagtail's `AbstractForm`)."""


class PublishRefused(Exception):
    """A page can't be published, for `reasons`. The message names the page.

    Not a `PermissionDenied`: the admin turns those into its own "Sorry, you do not have
    permission" message, so the reason would be lost. `core.middleware` shows this one's.
    """

    def __init__(self, page, reasons):
        self.page = page
        self.reasons = reasons
        super().__init__(f"“{page.title}” wasn't published. {' '.join(reasons)}")


class PublishGuardMixin:
    """For every page type: `publish()` refuses a page `reasons_not_to_publish` stops.

    Workflow approval, bulk publish, scheduled publishing and code call `publish()`. The editor's
    Publish button doesn't, so its form checks the page itself: a page type whose form editors
    build sets `base_form_class = FormPageForm`.
    """

    # Whether the page has a form for personal details, so needs the privacy notice live.
    collects_personal_details = False
    base_form_class = PageForm

    def publish(self, revision, *args, **kwargs):
        page = revision.as_object()
        reasons = reasons_not_to_publish(page)
        if not reasons:
            return super().publish(revision, *args, **kwargs)
        if revision.approved_go_live_at and revision.approved_go_live_at <= timezone.now():
            refuse_scheduled(page, revision, reasons)
            return None
        raise PublishRefused(page, reasons)


def refuse_scheduled(page, revision, reasons):
    """`publish_scheduled` publishes every page due in one loop, so a refusal mustn't stop it:
    the page stays as it is with its schedule cleared, and the server log and its History say
    why."""
    Revision.objects.filter(pk=revision.pk).update(approved_go_live_at=None)
    logger.warning(
        "Scheduled publishing of “%s” (page %s) refused: %s", page.title, page.pk, " ".join(reasons)
    )
    log(instance=page, action=SCHEDULED_PUBLISHING_REFUSED, data={"reasons": reasons})
