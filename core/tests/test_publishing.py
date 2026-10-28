"""What stops a page going live (#175), on every route that publishes a page.

A page can't go live while it holds "[Write: …]" placeholder text, while it's a form and its
site's privacy notice isn't live, or while it's a form that emails nobody.
"""

import datetime

import pytest
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.contrib.forms.forms import WagtailAdminFormPageForm
from wagtail.models import Page, PageLogEntry, Revision, WorkflowState, get_page_models
from wagtail.test.utils.form_data import inline_formset, nested_form_data, rich_text, streamfield

from campaigns.models import DonatePage
from contact.models import FormField, FormPage
from core.publishing import (
    ADD_RECIPIENT,
    PUBLISH_PRIVACY_NOTICE,
    REPLACE_PLACEHOLDERS,
    PublishCheckFormMixin,
    PublishGuardMixin,
    PublishRefused,
    has_placeholder,
    reasons_not_to_publish,
)
from home.models import StandardPage

pytestmark = pytest.mark.django_db

PLACEHOLDER = "[Write: one sentence on what your charity does and where.]"
NEPALI_PLACEHOLDER = "[लेख्नुहोस्: तपाईंको संस्थाले के गर्छ, एक वाक्यमा।]"


def draft(parent, page):
    """`page` added under `parent` as a draft, as an editor's new page is."""
    page.live = False
    parent.add_child(instance=page)
    return page


def volunteer_form(parent, **fields):
    page = FormPage(
        title="Volunteer with us",
        slug="volunteer",
        to_address="volunteers@brightwell.example",
        **fields,
    )
    page.form_fields = [FormField(label="Your name", field_type="singleline", required=True)]
    return draft(parent, page)


class TestPlaceholderText:
    @pytest.mark.parametrize(
        "text",
        [
            PLACEHOLDER,
            NEPALI_PLACEHOLDER,
            f"Our story. {PLACEHOLDER}",
            f"<p>{PLACEHOLDER}</p>",
            # An editor who makes part of it bold still hasn't written their own text.
            "<p>[<b>Write</b>: who you help.]</p>",
        ],
    )
    def test_is_found(self, text):
        assert has_placeholder(text)

    @pytest.mark.parametrize(
        "text",
        ["Footnote [1].", "[Note] We're closed on Fridays.", "Write: to us", "[Writing: soon]", ""],
    )
    def test_other_brackets_pass(self, text):
        assert not has_placeholder(text)


class TestWhereThePlaceholderIs:
    """Each kind of field an editor writes in is read: the page can't go live from any of them."""

    @pytest.mark.parametrize(
        "fields",
        [
            {"title": PLACEHOLDER},
            {"seo_title": PLACEHOLDER},
            {"search_description": PLACEHOLDER},
            {"introduction": NEPALI_PLACEHOLDER},
            {"body": [("paragraph", f"<p>{PLACEHOLDER}</p>")]},
            {
                "body": [
                    (
                        "impact_stats",
                        {"heading": "", "stats": [{"figure": "412", "label": PLACEHOLDER}]},
                    )
                ]
            },
        ],
        ids=["title", "SEO title", "search description", "text", "paragraph", "nested block"],
    )
    def test_on_a_page(self, home_page, fields):
        page = draft(home_page, StandardPage(**{"title": "About us", "slug": "about", **fields}))

        assert reasons_not_to_publish(page) == [REPLACE_PLACEHOLDERS]

    def test_in_a_form_fields_label(self, home_page, privacy_notice):
        page = volunteer_form(home_page)
        page.form_fields = [FormField(label=PLACEHOLDER, field_type="singleline")]

        assert reasons_not_to_publish(page) == [REPLACE_PLACEHOLDERS]

    def test_in_a_forms_thank_you_text(self, home_page, privacy_notice):
        page = volunteer_form(home_page, thank_you_text=f"<p>{PLACEHOLDER}</p>")

        assert reasons_not_to_publish(page) == [REPLACE_PLACEHOLDERS]

    def test_a_page_without_one_can_go_live(self, home_page):
        page = draft(home_page, StandardPage(title="About us [1]", slug="about"))

        assert reasons_not_to_publish(page) == []


class TestForms:
    def test_need_the_privacy_notice_live(self, home_page, privacy_notice):
        privacy_notice.unpublish()

        assert reasons_not_to_publish(volunteer_form(home_page)) == [PUBLISH_PRIVACY_NOTICE]

    def test_need_a_privacy_notice_chosen(self, home_page):
        assert reasons_not_to_publish(volunteer_form(home_page)) == [PUBLISH_PRIVACY_NOTICE]

    def test_the_donate_page_is_a_form_too(self, home_page):
        donate = draft(home_page, DonatePage(title="Donate", slug="donate"))

        assert reasons_not_to_publish(donate) == [PUBLISH_PRIVACY_NOTICE]

    def test_a_nepali_form_needs_the_chosen_notice_live(
        self, home_page, nepali_home_page, privacy_notice
    ):
        nepali_form = volunteer_form(home_page).copy_for_translation(nepali_home_page.locale)
        privacy_notice.unpublish()

        assert reasons_not_to_publish(nepali_form) == [PUBLISH_PRIVACY_NOTICE]

    @pytest.mark.parametrize("to_address", ["", "  "])
    def test_need_an_email_address_to_send_to(self, home_page, privacy_notice, to_address):
        page = volunteer_form(home_page, thank_you_text="<p>Thanks!</p>")
        page.to_address = to_address

        assert reasons_not_to_publish(page) == [ADD_RECIPIENT]

    def test_with_both_can_go_live(self, home_page, privacy_notice):
        assert reasons_not_to_publish(volunteer_form(home_page)) == []

    def test_every_reason_is_given(self, home_page):
        page = volunteer_form(home_page, intro=f"<p>{PLACEHOLDER}</p>")
        page.to_address = ""

        assert reasons_not_to_publish(page) == [
            REPLACE_PLACEHOLDERS,
            PUBLISH_PRIVACY_NOTICE,
            ADD_RECIPIENT,
        ]


class TestPublishingFromCode:
    """`publish()`, which Wagtail's bulk actions, workflows and scheduled publishing call too."""

    def test_is_refused_naming_the_page(self, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER

        with pytest.raises(PublishRefused, match="About us") as refused:
            page.save_revision().publish()

        assert str(REPLACE_PLACEHOLDERS) in str(refused.value)
        page.refresh_from_db()
        assert not page.live

    def test_reads_the_revision_being_published(self, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER
        revision = page.save_revision()
        page.introduction = "Who we are."
        page.save_revision()

        with pytest.raises(PublishRefused):
            revision.publish()

    def test_a_page_without_reasons_goes_live(self, home_page, privacy_notice):
        page = volunteer_form(home_page)

        page.save_revision().publish()

        page.refresh_from_db()
        assert page.live

    def test_drafts_save_as_usual(self, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER

        page.save_revision()

        assert page.get_latest_revision_as_object().introduction == PLACEHOLDER

    def test_every_page_type_is_guarded(self):
        """In code and in its admin form, where a form page keeps Wagtail's checks of its
        fields."""
        unguarded = [
            model.__name__
            for model in get_page_models()
            if model is not Page
            and not (
                issubclass(model, PublishGuardMixin)
                and issubclass(model.get_edit_handler().get_form_class(), PublishCheckFormMixin)
            )
        ]
        assert unguarded == []
        assert issubclass(FormPage.get_edit_handler().get_form_class(), WagtailAdminFormPageForm)


PUBLISH = {"action-publish": "action-publish"}
SUBMIT = {"action-submit": "action-submit"}
APPROVE = {"action-workflow-action": "true", "workflow-action-name": "approve"}


class TestTheEditor:
    """The Publish button doesn't call `publish()`, so the page's form checks it: Publish, Submit
    and Approve are refused, with each error where the editor can fix it. Drafts save."""

    def edit(self, client, user, page, action, **fields):
        client.force_login(user)
        data = nested_form_data(
            {
                "title": page.title,
                "slug": page.slug,
                "introduction": "",
                "body": streamfield([]),
                **fields,
            }
        )
        return client.post(reverse("wagtailadmin_pages:edit", args=[page.pk]), data | action)

    def add_form_page(self, client, user, home_page, **fields):
        client.force_login(user)
        url = reverse("wagtailadmin_pages:add", args=("contact", "formpage", home_page.pk))
        data = nested_form_data(
            {
                "title": "Volunteer with us",
                "slug": "volunteer",
                "intro": rich_text("<p>Give a few hours a month.</p>"),
                "thank_you_text": rich_text("<p>Thank you.</p>"),
                "to_address": "volunteers@brightwell.example",
                "from_address": "",
                "subject": "",
                "form_fields": inline_formset(
                    [{"label": "Your name", "field_type": "singleline", "required": "on"}]
                ),
                **fields,
            }
        )
        return client.post(url, data | PUBLISH)

    def test_publish_puts_the_error_on_the_field(self, client, moderator, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))

        response = self.edit(client, moderator, page, PUBLISH, introduction=PLACEHOLDER)

        assert response.context["form"].errors["introduction"] == [REPLACE_PLACEHOLDERS]
        page.refresh_from_db()
        assert not page.live

    def test_publish_puts_the_error_on_the_block(self, client, moderator, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        body = streamfield(
            [
                ("paragraph", rich_text("<p>Who we are.</p>")),
                ("paragraph", rich_text(f"<p>{NEPALI_PLACEHOLDER}</p>")),
            ]
        )

        response = self.edit(client, moderator, page, PUBLISH, body=body)

        error = response.context["form"].errors["body"].as_data()[0]
        assert {
            index: block_error.messages for index, block_error in error.block_errors.items()
        } == {1: [REPLACE_PLACEHOLDERS]}
        page.refresh_from_db()
        assert not page.live

    def test_submitting_for_moderation_is_refused(self, client, editor, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))

        response = self.edit(client, editor, page, SUBMIT, title=f"About us {PLACEHOLDER}")

        assert response.context["form"].errors["title"] == [REPLACE_PLACEHOLDERS]
        assert page.current_workflow_state is None

    def test_approving_is_refused(self, client, editor, moderator, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER
        page.save_revision(user=editor)
        page.get_workflow().start(page, editor)

        response = self.edit(client, moderator, page, APPROVE, introduction=PLACEHOLDER)

        assert response.context["form"].errors["introduction"] == [REPLACE_PLACEHOLDERS]
        page.refresh_from_db()
        assert not page.live
        assert page.current_workflow_state.status == WorkflowState.STATUS_IN_PROGRESS

    def test_a_draft_saves(self, client, editor, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))

        response = self.edit(client, editor, page, {}, introduction=PLACEHOLDER)

        assert response.status_code == 302
        page.refresh_from_db()
        assert page.get_latest_revision_as_object().introduction == PLACEHOLDER

    def test_a_form_fields_label_shows_the_error(
        self, client, moderator, home_page, privacy_notice
    ):
        fields = inline_formset([{"label": PLACEHOLDER, "field_type": "singleline"}])

        response = self.add_form_page(client, moderator, home_page, form_fields=fields)

        row = response.context["form"].formsets["form_fields"].forms[0]
        assert row.errors["label"] == [REPLACE_PLACEHOLDERS]
        assert not FormPage.objects.exists()

    def test_a_form_needs_the_privacy_notice_live(self, client, moderator, home_page):
        response = self.add_form_page(client, moderator, home_page)

        assert response.context["form"].non_field_errors() == [PUBLISH_PRIVACY_NOTICE]
        assert not FormPage.objects.exists()

    def test_a_form_needs_an_address_to_send_to(self, client, moderator, home_page, privacy_notice):
        response = self.add_form_page(client, moderator, home_page, to_address="")

        assert response.context["form"].errors["to_address"] == [ADD_RECIPIENT]
        assert not FormPage.objects.exists()

    def test_a_page_without_reasons_is_published(
        self, client, moderator, home_page, privacy_notice
    ):
        response = self.add_form_page(client, moderator, home_page)

        assert response.status_code == 302
        assert FormPage.objects.get().live


class TestApprovingATask:
    """Approving from the dashboard or a page listing calls `publish()`: a refusal shows why, on
    the page's edit view, and the task is left to approve once the page is fixed."""

    @pytest.fixture
    def submitted(self, home_page, editor):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER
        page.save_revision(user=editor)
        page.get_workflow().start(page, editor)
        return page

    def approve(self, client, moderator, page, **headers):
        client.force_login(moderator)
        task_state = page.current_workflow_task_state
        url = reverse(
            "wagtailadmin_pages:workflow_action", args=[page.pk, "approve", task_state.pk]
        )
        return client.post(url, {"comment": ""}, headers=headers)

    def test_shows_why(self, client, moderator, submitted):
        response = self.approve(client, moderator, submitted)

        assert response.url == reverse("wagtailadmin_pages:edit", args=[submitted.pk])
        assert [str(message) for message in get_messages(response.wsgi_request)] == [
            f"“About us” wasn't published. {REPLACE_PLACEHOLDERS}"
        ]
        submitted.refresh_from_db()
        assert not submitted.live
        assert submitted.current_workflow_state.status == WorkflowState.STATUS_IN_PROGRESS

    def test_from_the_approval_window(self, client, moderator, submitted):
        response = self.approve(client, moderator, submitted, x_requested_with="XMLHttpRequest")

        assert response.json() == {
            "step": "success",
            "redirect": reverse("wagtailadmin_pages:edit", args=[submitted.pk]),
        }
        assert len(get_messages(response.wsgi_request)) == 1
        submitted.refresh_from_db()
        assert submitted.current_workflow_state.status == WorkflowState.STATUS_IN_PROGRESS


def schedule(page, minutes_ago):
    """`page`'s latest draft, scheduled to go live `minutes_ago`, as Publish with a go-live time
    leaves it once that time has passed."""
    revision = page.save_revision()
    revision.approved_go_live_at = timezone.now() - datetime.timedelta(minutes=minutes_ago)
    revision.save()
    return revision


class TestScheduledPublishing:
    """`publish_scheduled` publishes every page whose time has come in one loop, every 5 minutes.
    A refused page stays as it is, its schedule cleared, and the server log and the page's
    History say why; the pages after it still go live."""

    @pytest.fixture
    def refused(self, home_page, privacy_notice):
        """A form scheduled while the privacy notice was live, which has since been unpublished."""
        page = volunteer_form(home_page)
        schedule(page, minutes_ago=10)
        privacy_notice.unpublish()
        return page

    def test_the_pages_after_a_refused_one_go_live(self, home_page, refused):
        later = draft(home_page, StandardPage(title="Our work", slug="our-work"))
        schedule(later, minutes_ago=5)

        call_command("publish_scheduled")

        assert live(refused, later) == ["Our work"]

    def test_the_refused_page_is_no_longer_scheduled(self, refused):
        call_command("publish_scheduled")

        assert not Revision.page_revisions.filter(approved_go_live_at__isnull=False).exists()

    def test_the_refusal_is_logged(self, refused, caplog):
        call_command("publish_scheduled")

        assert (
            f"Scheduled publishing of “Volunteer with us” (page {refused.pk}) refused: "
            f"{PUBLISH_PRIVACY_NOTICE}"
        ) in caplog.messages

    def test_the_pages_history_says_why(self, refused):
        call_command("publish_scheduled")

        entry = PageLogEntry.objects.get(page=refused, action="charity.publish.scheduled.refused")
        assert entry.message == f"Scheduled publishing refused: {PUBLISH_PRIVACY_NOTICE}"

    def test_a_page_publishing_now_is_refused_as_usual(self, home_page):
        page = draft(home_page, StandardPage(title="About us", slug="about"))
        page.introduction = PLACEHOLDER
        revision = page.save_revision()
        revision.approved_go_live_at = timezone.now() + datetime.timedelta(days=1)
        revision.save()

        with pytest.raises(PublishRefused):
            revision.publish()


def bulk(client, user, action, pages, **data):
    """Run a bulk action from the page listing on `pages`; the messages it leaves."""
    client.force_login(user)
    url = reverse("wagtail_bulk_action", args=("wagtailcore", "page", action))
    ids = "&".join(f"id={page.pk}" for page in pages)
    response = client.post(f"{url}?{ids}&next=/admin/", data)
    assert response.status_code == 302
    return [str(message) for message in get_messages(response.wsgi_request)]


def live(*pages):
    return [page.title for page in Page.objects.filter(pk__in=[p.pk for p in pages], live=True)]


class TestBulkPublishing:
    """Every page is checked before any is published, so bulk publish publishes all the chosen
    pages or none, naming each page that stops it and why."""

    def test_is_refused_naming_each_page(self, client, moderator, home_page):
        ready = draft(home_page, StandardPage(title="Our work", slug="our-work"))
        about = draft(home_page, StandardPage(title="About us", slug="about"))
        about.introduction = PLACEHOLDER
        about.save_revision()
        volunteer = volunteer_form(home_page)

        messages = bulk(client, moderator, "publish", [ready, about, volunteer])

        assert messages == [
            "Nothing was published.",
            f"“About us” wasn't published. {REPLACE_PLACEHOLDERS}",
            f"“Volunteer with us” wasn't published. {PUBLISH_PRIVACY_NOTICE}",
        ]
        assert live(ready, about, volunteer) == []

    def test_reads_the_draft_it_would_publish(self, client, moderator, home_page):
        about = home_page.add_child(instance=StandardPage(title="About us", slug="about"))
        about.introduction = PLACEHOLDER
        about.save_revision()

        messages = bulk(client, moderator, "publish", [about])

        assert messages[0] == "Nothing was published."
        about.refresh_from_db()
        assert about.introduction == ""

    def test_checks_the_subpages_it_would_publish(self, client, moderator, home_page):
        about = draft(home_page, StandardPage(title="About us", slug="about"))
        team = draft(about, StandardPage(title="Our team", slug="team", introduction=PLACEHOLDER))

        messages = bulk(client, moderator, "publish", [about], include_descendants="on")

        assert messages[1:] == [f"“Our team” wasn't published. {REPLACE_PLACEHOLDERS}"]
        assert live(about, team) == []

    def test_leaves_out_subpages_it_wouldnt_publish(self, client, moderator, home_page):
        about = draft(home_page, StandardPage(title="About us", slug="about"))
        team = draft(about, StandardPage(title="Our team", slug="team", introduction=PLACEHOLDER))

        bulk(client, moderator, "publish", [about])

        assert live(about, team) == ["About us"]
