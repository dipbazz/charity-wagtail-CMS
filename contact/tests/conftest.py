import pytest

from contact.models import FormField, FormPage


@pytest.fixture
def volunteer_form(home_page, privacy_notice):
    """A published volunteer sign-up form under the home page: name and email required."""
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
