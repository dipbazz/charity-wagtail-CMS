import pytest
from bs4 import BeautifulSoup
from django.core import mail
from django.urls import reverse
from wagtail.contrib.forms.models import FormSubmission

from contact.models import FormField, FormPage
from home.models import StandardPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def volunteer_form(home_page):
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

    def test_no_privacy_link_without_a_privacy_notice(self, client, volunteer_form):
        assert "How we use your details" not in client.get(volunteer_form.url).content.decode()

    def test_valid_submission_is_stored_and_shows_thank_you(self, client, volunteer_form):
        response = client.post(volunteer_form.url, VALID_DATA)

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

        response = client.post(volunteer_form.url, VALID_DATA)

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
