"""Form pages in a real browser: what only happens there (scripts).

pytest's HTML checks in test_form_page.py can't see these. Run `uv run playwright install
--with-deps chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from playwright.sync_api import expect

from conftest import SITE
from contact.models import FormField

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


def test_a_send_with_mistakes_focuses_the_error_summary(site_page, volunteer_form):
    """charity.js focuses it as the page opens (#167), so a screen reader reads it first."""
    site_page.goto(SITE + volunteer_form.url)

    site_page.get_by_role("button", name="Send").click()

    expect(site_page.locator(".error-summary")).to_be_focused()


def test_a_summary_link_shows_the_question_and_its_mistake_on_a_phone(site_page, volunteer_form):
    """A plain #id jump puts the box at the top of the screen, its label and mistake above it."""
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + volunteer_form.url)
    site_page.get_by_role("button", name="Send").click()

    site_page.locator(".error-summary a").nth(1).click()

    expect(site_page.get_by_label("Email address")).to_be_focused()
    field = site_page.locator(".field").filter(has=site_page.get_by_label("Email address"))
    expect(field.locator("label")).to_be_in_viewport(ratio=1)
    expect(field.locator(".errorlist")).to_be_in_viewport(ratio=1)


def test_a_group_of_choices_leaves_the_same_space_as_any_other_field(site_page, volunteer_form):
    """The choices' fieldset sits in a .field group; their two margins added up to 2.75rem."""
    for order, (label, field_type) in enumerate(
        [("How would you like to help?", "checkboxes"), ("I agree to be contacted", "checkbox")],
        start=10,
    ):
        FormField.objects.create(
            page=volunteer_form,
            sort_order=order,
            label=label,
            field_type=field_type,
            choices="Events\nShops" if field_type == "checkboxes" else "",
        )
    volunteer_form.save_revision().publish()
    site_page.goto(SITE + volunteer_form.url)

    # From the end of what each group shows (its last box or fieldset) to the next group's top.
    gaps = site_page.evaluate(
        """() => [...document.querySelectorAll("form > .field")].map((group) => [
            group.getBoundingClientRect().top,
            group.lastElementChild.getBoundingClientRect().bottom,
        ]).map(([, end], i, all) => all[i + 1] && Math.round(all[i + 1][0] - end)).slice(0, -1)"""
    )

    assert len(set(gaps)) == 1, gaps
