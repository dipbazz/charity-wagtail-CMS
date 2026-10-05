import datetime

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import PageViewRestriction
from wagtail.test.utils.form_data import inline_formset, nested_form_data, rich_text, streamfield

from campaigns.models import DonatePage
from campaigns.tests.factories import (
    CampaignIndexPageFactory,
    CampaignPageFactory,
    DonatePageFactory,
)
from core.models import SiteSettings
from home.models import StandardPage

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


@pytest.fixture
def appeals(home_page):
    index = CampaignIndexPageFactory(parent=home_page, title="Appeals", slug="appeals")
    CampaignPageFactory(parent=index, title="Flood relief", slug="flood-relief")
    CampaignPageFactory(
        parent=index,
        title="Last year's appeal",
        slug="last-year",
        start_date=TODAY - datetime.timedelta(days=400),
        end_date=TODAY - datetime.timedelta(days=30),
    )
    private = CampaignPageFactory(parent=index, title="Trustees' appeal", slug="trustees")
    PageViewRestriction.objects.create(
        page=private, restriction_type=PageViewRestriction.PASSWORD, password="trustees"
    )
    return index


@pytest.fixture
def donate_page(home_page, appeals):
    page = DonatePageFactory(
        parent=home_page,
        offer_gift_aid=True,
        body=[("paragraph", "<p>Where every Rs 100 goes</p>")],
    )
    page.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
    page.donation_amounts.create(amount=10000, impact="Water purification for a month")
    page.save_revision().publish()
    return page


VALID = {
    "amount": "2500",
    "other_amount": "",
    "frequency": "one-off",
    "name": "Sita Sharma",
    "email": "sita@example.com",
    "phone_country": "NP",
    "phone": "",
    "appeal": "",
    "address": "",
    "postcode": "",
}


def pledge(client, page, **changes):
    return client.post(page.url, {**VALID, **changes})


def stored(page):
    return FormSubmission.objects.get(page=page).form_data


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def is_checked(response, name, value):
    """Whether the radio button or select option with this value starts out chosen."""
    html = soup(response)
    select = html.find("select", attrs={"name": name})
    if select:
        option = select.find("option", attrs={"value": value})
        return option is not None and option.has_attr("selected")
    radio = html.find("input", attrs={"name": name, "value": value})
    return radio is not None and radio.has_attr("checked")


class TestPageTreeRules:
    def test_lives_under_the_home_page_only_once(self, home_page):
        about = StandardPage(title="About")
        home_page.add_child(instance=about)

        assert DonatePage.can_create_at(home_page)
        assert not DonatePage.can_create_at(about)

        DonatePageFactory(parent=home_page)
        assert not DonatePage.can_create_at(home_page)

    def test_has_no_child_pages(self):
        assert DonatePage.subpage_types == []


class TestDonatePage:
    def test_shows_suggested_amounts_with_what_they_pay_for(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "Rs 2,500" in html and "A hygiene kit for a family" in html
        assert "Rs 10,000" in html and "Water purification for a month" in html

    def test_says_no_payment_is_taken_online(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "No payment is taken online yet." in html

    def test_shows_the_body_below_the_form(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert html.index("</form>") < html.index("Where every Rs 100 goes")

    def test_offers_open_public_appeals_and_wherever_needed_most(self, client, donate_page):
        select = soup(client.get(donate_page.url)).find("select", attrs={"name": "appeal"})
        options = [option.get_text(strip=True) for option in select.find_all("option")]

        assert options == ["Wherever it's needed most", "Flood relief"]


class TestPledging:
    def test_a_suggested_amount_is_saved(self, client, donate_page):
        response = pledge(client, donate_page, frequency="monthly", appeal="flood-relief")

        assert response.status_code == 200
        data = stored(donate_page)
        assert data["amount"] == "2500"
        assert data["currency"] == "NPR"
        assert data["frequency"] == "Monthly"
        assert data["name"] == "Sita Sharma"
        assert data["email"] == "sita@example.com"
        assert data["appeal"] == "Flood relief"

    def test_a_different_amount_is_saved(self, client, donate_page):
        pledge(client, donate_page, amount="other", other_amount="4000")

        assert stored(donate_page)["amount"] == "4000"

    def test_typing_an_amount_without_choosing_other_is_enough(self, client, donate_page):
        pledge(client, donate_page, amount="", other_amount="4000")

        assert stored(donate_page)["amount"] == "4000"

    # Regression: ISSUE-002 — a typed amount was silently dropped when a card was also chosen
    # Found by /qa on 2026-10-05
    # Report: .gstack/qa-reports/run-20261005T080853Z/qa-report-127.0.0.1-2026-10-05.md
    def test_choosing_a_suggested_amount_and_typing_another_asks_which(self, client, donate_page):
        response = pledge(client, donate_page, amount="2500", other_amount="4000")

        assert "Choose a suggested amount or type your own, not both." in (
            response.content.decode()
        )
        assert not FormSubmission.objects.exists()

    def test_own_amount_is_labelled_with_the_currency(self, client, donate_page):
        label = soup(client.get(donate_page.url)).find("label", attrs={"for": "id_other_amount"})

        assert label.get_text(strip=True) == "Your own amount (Rs)"

    def test_wherever_needed_most_is_the_default_appeal(self, client, donate_page):
        pledge(client, donate_page)

        assert stored(donate_page)["appeal"] == "Wherever it's needed most"

    @pytest.mark.parametrize(
        "amount",
        [
            {"amount": ""},
            {"amount": "other", "other_amount": ""},
            {"amount": "other", "other_amount": "0"},
            {"amount": "999"},  # not one of the suggested amounts
        ],
    )
    def test_a_missing_amount_shows_an_error_and_saves_nothing(self, client, donate_page, amount):
        response = pledge(client, donate_page, **amount)

        assert response.status_code == 200
        assert "Choose an amount or enter your own." in response.content.decode()
        assert not FormSubmission.objects.exists()

    # Regression: ISSUE-001 — the error summary said "This field is required." twice
    # Found by /qa on 2026-10-05
    # Report: .gstack/qa-reports/run-20261005T080853Z/qa-report-127.0.0.1-2026-10-05.md
    def test_missing_name_and_email_errors_say_which_field(self, client, donate_page):
        response = pledge(client, donate_page, name="", email="")

        html = response.content.decode()
        assert "Enter your name." in html
        assert "Enter your email address." in html
        assert "This field is required." not in html

    def test_a_closed_appeal_cannot_be_chosen(self, client, donate_page):
        response = pledge(client, donate_page, appeal="last-year")

        assert "Select a valid choice." in response.content.decode()
        assert not FormSubmission.objects.exists()

    def test_thank_you_page_links_back_to_the_appeals(self, client, donate_page, appeals):
        response = pledge(client, donate_page)

        html = response.content.decode()
        assert "Thank you for your pledge." in html
        assert f'href="{appeals.url}"' in html


class TestPreselecting:
    def test_arriving_from_an_appeal_preselects_it(self, client, donate_page):
        response = client.get(donate_page.url, {"appeal": "flood-relief"})

        assert is_checked(response, "appeal", "flood-relief")

    @pytest.mark.parametrize("slug", ["last-year", "trustees", "no-such-appeal"])
    def test_closed_private_or_unknown_appeals_are_not_preselected(self, client, donate_page, slug):
        response = client.get(donate_page.url, {"appeal": slug})

        assert response.status_code == 200
        assert is_checked(response, "appeal", "")

    def test_a_suggested_amount_in_the_link_is_preselected(self, client, donate_page):
        response = client.get(donate_page.url, {"amount": "2500", "appeal": "flood-relief"})

        assert is_checked(response, "amount", "2500")
        assert is_checked(response, "appeal", "flood-relief")

    def test_another_amount_in_the_link_fills_other_amount(self, client, donate_page):
        response = client.get(donate_page.url, {"amount": "4000"})

        assert is_checked(response, "amount", "other")
        other = soup(response).find("input", attrs={"name": "other_amount"})
        assert other["value"] == "4000"

    def test_nonsense_amounts_in_the_link_are_ignored(self, client, donate_page):
        response = client.get(donate_page.url, {"amount": "abc"})

        assert response.status_code == 200
        assert not soup(response).find(attrs={"name": "amount", "checked": True})


class TestGiftAid:
    def test_needs_an_address_and_postcode(self, client, donate_page):
        response = pledge(client, donate_page, gift_aid="on")

        html = response.content.decode()
        assert "Enter your home address to claim Gift Aid." in html
        assert "Enter your postcode to claim Gift Aid." in html
        assert not FormSubmission.objects.exists()

    def test_is_saved_with_the_address(self, client, donate_page):
        pledge(
            client,
            donate_page,
            gift_aid="on",
            address="1 Example Street\nBirmingham",
            postcode="B1 1AA",
        )

        data = stored(donate_page)
        assert data["gift_aid"] is True
        assert data["address"] == "1 Example Street\nBirmingham"
        assert data["postcode"] == "B1 1AA"

    def test_a_nepali_address_without_a_postal_code_is_fine_without_gift_aid(
        self, client, donate_page
    ):
        pledge(client, donate_page, address="Ward 4, Thamel, Kathmandu")

        data = stored(donate_page)
        assert data["address"] == "Ward 4, Thamel, Kathmandu"
        assert data["gift_aid"] is False

    def test_is_not_offered_when_switched_off(self, client, donate_page):
        donate_page.offer_gift_aid = False
        donate_page.save_revision().publish()

        assert 'name="gift_aid"' not in client.get(donate_page.url).content.decode()

        pledge(client, donate_page, gift_aid="on")
        assert stored(donate_page)["gift_aid"] is False


class TestMobileNumber:
    def test_is_optional(self, client, donate_page):
        pledge(client, donate_page)

        assert stored(donate_page)["phone"] == ""

    def test_starts_on_the_country_chosen_in_site_settings(self, client, site, donate_page):
        settings = SiteSettings.for_site(site)
        settings.phone_country = "GB"
        settings.save()

        response = client.get(donate_page.url)

        assert is_checked(response, "phone_country", "GB")

    def test_nepali_number_is_saved_with_its_country_code(self, client, donate_page):
        pledge(client, donate_page, phone="984-1234567")

        assert stored(donate_page)["phone"] == "+9779841234567"

    def test_uk_number_is_saved_with_its_country_code(self, client, donate_page):
        pledge(client, donate_page, phone_country="GB", phone="07400 123456")

        assert stored(donate_page)["phone"] == "+447400123456"

    @pytest.mark.parametrize("phone", ["01-4567890", "98abc12345"])
    def test_a_number_that_cannot_get_messages_shows_an_error(self, client, donate_page, phone):
        response = pledge(client, donate_page, phone=phone)

        assert "Enter a mobile number, like 984-1234567." in response.content.decode()
        assert not FormSubmission.objects.exists()

    def test_says_it_is_only_for_a_whatsapp_or_text_reminder(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "WhatsApp" in html
        assert "text message" in html


class TestPledgesInTheAdmin:
    def test_editors_see_pledges_with_readable_columns(self, client, editor, donate_page):
        pledge(client, donate_page, appeal="flood-relief")
        client.force_login(editor)

        url = reverse("wagtailforms:list_submissions", args=[donate_page.pk])
        html = client.get(url).content.decode()

        assert "sita@example.com" in html
        assert "Flood relief" in html
        assert "Mobile number" in html

    def test_editors_can_export_pledges_as_csv(self, client, editor, donate_page):
        pledge(client, donate_page, phone="984-1234567")
        client.force_login(editor)

        url = reverse("wagtailforms:list_submissions", args=[donate_page.pk])
        response = client.get(url, {"export": "csv"})

        csv = b"".join(response.streaming_content).decode()
        assert csv.splitlines()[0].startswith("Submission date,Amount,Currency,Frequency,Name")
        assert "2500,NPR,One-off,Sita Sharma,sita@example.com,+9779841234567" in csv

    def test_editors_can_draft_a_donate_page_with_amounts(self, client, editor, home_page):
        client.force_login(editor)
        url = reverse("wagtailadmin_pages:add", args=("campaigns", "donatepage", home_page.pk))
        data = nested_form_data(
            {
                "title": "Donate",
                "slug": "donate",
                "introduction": "Every gift helps.",
                "payment_notice": rich_text("<p>No payment is taken online yet.</p>"),
                "body": streamfield([]),
                "thank_you_text": rich_text("<p>Thank you.</p>"),
                "donation_amounts": inline_formset(
                    [{"amount": "1500", "impact": "Safe water for one person for a year"}]
                ),
            }
        )

        response = client.post(url, data)

        assert response.status_code == 302
        page = DonatePage.objects.get(slug="donate")
        draft = page.get_latest_revision_as_object()
        assert draft.donation_amounts.get().impact == "Safe water for one person for a year"
