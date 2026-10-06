import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from wagtail.test.utils.form_data import inline_formset, nested_form_data, rich_text, streamfield

from campaigns.forms import PledgeForm
from campaigns.models import CampaignPage, DonatePage, Frequency, Pledge
from campaigns.tests.factories import DonatePageFactory
from core.models import SiteSettings
from home.models import StandardPage

pytestmark = pytest.mark.django_db

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
    return Pledge.objects.get(page=page)


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

    # Regression: a two-line {# #} note printed as text above "How often"
    # Found in review of #89 on 2026-10-05
    def test_shows_no_template_notes(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "{#" not in html
        assert "charity.css shows" not in html

    def test_shows_the_body_below_the_form(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert html.index("</form>") < html.index("Where every Rs 100 goes")

    def test_offers_open_public_appeals_and_wherever_needed_most(self, client, donate_page):
        select = soup(client.get(donate_page.url)).find("select", attrs={"name": "appeal"})
        options = [option.get_text(strip=True) for option in select.find_all("option")]

        assert options == ["Wherever it's needed most", "Flood relief"]


class TestPledgeModelAndForm:
    """PledgeForm builds its fields from Pledge, so what a field accepts can't drift apart. The
    model's names are neutral (they head the admin columns); the form words them for donors."""

    @pytest.mark.parametrize("name", ["name", "email", "phone", "address", "postcode", "message"])
    def test_what_each_field_accepts_comes_from_the_model(self, name):
        form_field = PledgeForm.base_fields[name]
        model_field = Pledge._meta.get_field(name)

        assert form_field.required == (not model_field.blank)
        if name != "phone":  # the form allows a longer typed number; clean() normalises it
            assert form_field.max_length == model_field.max_length

    def test_frequency_choices_are_the_shared_frequency_choices(self):
        assert list(PledgeForm.base_fields["frequency"].choices) == Frequency.choices

    @pytest.mark.parametrize(
        ("name", "model_label", "form_label"),
        [
            ("name", "name", "Your name"),
            ("appeal", "appeal", "Which appeal would you like to support?"),
            ("phone", "mobile number", "Number"),
            ("frequency", "how often", "How often"),
            ("message", "message", "A message with your gift"),
            (
                "email_updates",
                "email updates",
                "Email me stories from our projects and appeals that need help",
            ),
            ("show_on_website", "show on website", "Show my gift on our website"),
        ],
    )
    def test_the_model_is_named_for_the_team_and_the_form_for_donors(
        self, name, model_label, form_label
    ):
        assert Pledge._meta.get_field(name).verbose_name == model_label
        assert PledgeForm.base_fields[name].label == form_label

    def test_the_mobile_number_help_is_the_reminder_consent(self):
        help_text = PledgeForm.base_fields["phone"].help_text

        assert "WhatsApp" in help_text and "text message" in help_text


class TestPledging:
    def test_a_pledge_records_the_page_it_came_from(self, client, donate_page):
        pledge(client, donate_page)

        assert stored(donate_page).page == donate_page

    def test_a_suggested_amount_is_saved(self, client, donate_page):
        response = pledge(client, donate_page, frequency="monthly", appeal="flood-relief")

        assert response.status_code == 200
        saved = stored(donate_page)
        assert saved.amount == 2500
        assert saved.currency == "NPR"
        assert saved.frequency == Frequency.MONTHLY
        assert saved.name == "Sita Sharma"
        assert saved.email == "sita@example.com"
        assert saved.appeal == CampaignPage.objects.get(slug="flood-relief")

    def test_a_different_amount_is_saved(self, client, donate_page):
        pledge(client, donate_page, amount="other", other_amount="4000")

        assert stored(donate_page).amount == 4000

    def test_typing_an_amount_without_choosing_other_is_enough(self, client, donate_page):
        pledge(client, donate_page, amount="", other_amount="4000")

        assert stored(donate_page).amount == 4000

    # Regression: ISSUE-002 — a typed amount was silently dropped when a card was also chosen
    # Found by /qa on 2026-10-05
    # Report: .gstack/qa-reports/run-20261005T080853Z/qa-report-127.0.0.1-2026-10-05.md
    def test_choosing_a_suggested_amount_and_typing_another_asks_which(self, client, donate_page):
        response = pledge(client, donate_page, amount="2500", other_amount="4000")

        assert "Choose a suggested amount or type your own, not both." in (
            response.content.decode()
        )
        assert not Pledge.objects.exists()

    def test_own_amount_is_labelled_with_the_currency(self, client, donate_page):
        label = soup(client.get(donate_page.url)).find("label", attrs={"for": "id_other_amount"})

        assert label.get_text(strip=True) == "Your own amount (Rs)"

    def test_wherever_needed_most_is_the_default_appeal(self, client, donate_page):
        pledge(client, donate_page)

        assert stored(donate_page).appeal is None

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
        assert not Pledge.objects.exists()

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
        assert not Pledge.objects.exists()

    def test_thank_you_page_links_back_to_the_appeals(self, client, donate_page, appeals):
        response = pledge(client, donate_page)

        html = response.content.decode()
        assert "Thank you for your pledge." in html
        assert f'href="{appeals.url}"' in html


class TestOwnAmountField:
    """Only "Other amount" reveals "Your own amount"; charity.css hides it otherwise."""

    def own_amount(self, response):
        return (
            soup(response)
            .find("input", attrs={"name": "other_amount"})
            .find_parent(class_="other-amount")
        )

    def test_sits_with_the_amount_cards_and_starts_hidden(self, client, donate_page):
        field = self.own_amount(client.get(donate_page.url))

        assert field.find_parent(class_="amount-options")
        assert "is-shown" not in field["class"]

    def test_is_shown_with_its_value_when_both_were_given(self, client, donate_page):
        response = pledge(client, donate_page, amount="2500", other_amount="4000")

        field = self.own_amount(response)
        assert "is-shown" in field["class"]
        assert field.find("input")["value"] == "4000"


class TestOwnAmountInput:
    def test_is_a_text_box_with_a_number_keypad_so_scrolling_cannot_change_it(
        self, client, donate_page
    ):
        field = soup(client.get(donate_page.url)).find("input", attrs={"name": "other_amount"})

        assert field["type"] == "text"
        assert field["inputmode"] == "numeric"

    @pytest.mark.parametrize(
        ("typed", "stored_amount"), [("1,00,000", 100000), ("4,000", 4000), ("4 000", 4000)]
    )
    def test_accepts_amounts_written_with_commas_or_spaces(
        self, client, donate_page, typed, stored_amount
    ):
        pledge(client, donate_page, amount="other", other_amount=typed)

        assert stored(donate_page).amount == stored_amount

    @pytest.mark.parametrize("typed", ["abc", "12.5"])
    def test_rejects_anything_but_a_whole_amount(self, client, donate_page, typed):
        response = pledge(client, donate_page, amount="other", other_amount=typed)

        assert "Enter a whole number." in response.content.decode()
        assert not Pledge.objects.exists()


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


class TestAddress:
    def test_a_nepali_address_without_a_postal_code_is_accepted(self, client, donate_page):
        pledge(client, donate_page, address="Ward 4, Thamel, Kathmandu")

        saved = stored(donate_page)
        assert saved.address == "Ward 4, Thamel, Kathmandu"
        assert saved.postcode == ""

    def test_a_uk_address_with_a_postcode_is_saved(self, client, donate_page):
        pledge(client, donate_page, address="1 Example Street\nBirmingham", postcode="B1 1AA")

        saved = stored(donate_page)
        assert saved.address == "1 Example Street\nBirmingham"
        assert saved.postcode == "B1 1AA"


class TestOptionalLabels:
    """Optional fields say so after their label, in grey (.optional in charity.css)."""

    def label(self, response, for_id):
        return soup(response).find("label", attrs={"for": for_id})

    @pytest.mark.parametrize("for_id", ["id_message", "id_address", "id_postcode"])
    def test_optional_fields_say_so(self, client, donate_page, for_id):
        optional = self.label(client.get(donate_page.url), for_id).find(class_="optional")

        assert optional.get_text(strip=True) == "(optional)"

    @pytest.mark.parametrize("for_id", ["id_name", "id_email", "id_phone"])
    def test_required_fields_and_the_number_do_not(self, client, donate_page, for_id):
        assert not self.label(client.get(donate_page.url), for_id).find(class_="optional")

    def test_the_mobile_number_says_so_once_for_both_its_fields(self, client, donate_page):
        legend = soup(client.get(donate_page.url)).find("fieldset", class_="phone-field").legend

        assert legend.find(class_="optional").get_text(strip=True) == "(optional)"


class TestMobileNumber:
    """Asked for only with a monthly gift, for the monthly reminder; charity.css hides it
    until Monthly is chosen."""

    def phone_field(self, response):
        return (
            soup(response).find("input", attrs={"name": "phone"}).find_parent(class_="phone-field")
        )

    def test_is_optional(self, client, donate_page):
        pledge(client, donate_page, frequency="monthly")

        assert stored(donate_page).phone == ""

    def test_comes_straight_after_how_often_and_starts_hidden(self, client, donate_page):
        response = client.get(donate_page.url)
        html = response.content.decode()

        assert html.index('id="id_frequency') < html.index('name="phone"')
        assert html.index('name="phone"') < html.index('name="appeal"')
        field = self.phone_field(response)
        assert field.find_parent(class_="giving-frequency")
        assert "is-shown" not in field["class"]

    def test_starts_on_the_country_chosen_in_site_settings(self, client, site, donate_page):
        settings = SiteSettings.for_site(site)
        settings.phone_country = "GB"
        settings.save()

        response = client.get(donate_page.url)

        assert is_checked(response, "phone_country", "GB")

    def test_nepali_number_is_saved_with_its_country_code(self, client, donate_page):
        pledge(client, donate_page, frequency="monthly", phone="984-1234567")

        assert stored(donate_page).phone == "+9779841234567"

    def test_uk_number_is_saved_with_its_country_code(self, client, donate_page):
        pledge(client, donate_page, frequency="monthly", phone_country="GB", phone="07400 123456")

        assert stored(donate_page).phone == "+447400123456"

    @pytest.mark.parametrize("phone", ["01-4567890", "98abc12345"])
    def test_a_number_that_cannot_get_messages_shows_an_error(self, client, donate_page, phone):
        response = pledge(client, donate_page, frequency="monthly", phone=phone)

        assert "Enter a mobile number, like 984-1234567." in response.content.decode()
        assert not Pledge.objects.exists()

    # Regression: ISSUE-001 — after a mobile number error, choosing One-off left it on screen
    # Found by /qa on 2026-10-05
    # Report: .gstack/qa-reports/run-20261005T090524Z/qa-report-127.0.0.1-2026-10-05.md
    def test_error_leaves_its_visibility_to_the_monthly_choice(self, client, donate_page):
        response = pledge(client, donate_page, frequency="monthly", phone="12345")

        assert is_checked(response, "frequency", "monthly")
        assert "is-shown" not in self.phone_field(response)["class"]

    @pytest.mark.parametrize("phone", ["984-1234567", "not a number"])
    def test_is_not_kept_for_a_one_off_gift(self, client, donate_page, phone):
        response = pledge(client, donate_page, frequency="one-off", phone=phone)

        assert response.status_code == 200
        assert stored(donate_page).phone == ""

    def test_says_it_is_only_for_a_whatsapp_or_text_reminder(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "WhatsApp" in html
        assert "text message" in html


class TestMessage:
    """A note to the team with the gift, e.g. who it's in memory of. Never shown on the site."""

    def test_is_optional(self, client, donate_page):
        pledge(client, donate_page)

        assert stored(donate_page).message == ""

    def test_is_saved(self, client, donate_page):
        pledge(client, donate_page, message="In memory of my father, Hari.")

        assert stored(donate_page).message == "In memory of my father, Hari."

    def test_a_message_over_1000_characters_shows_an_error(self, client, donate_page):
        response = pledge(client, donate_page, message="x" * 1001)

        assert "at most 1000 characters" in response.content.decode()
        assert not Pledge.objects.exists()

    def test_says_only_the_team_reads_it(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert "Only our team will read it." in html


class TestChoices:
    """Two separate consents, both unticked until the supporter ticks one (opt-in)."""

    @pytest.mark.parametrize("name", ["email_updates", "show_on_website"])
    def test_starts_unticked(self, client, donate_page, name):
        box = soup(client.get(donate_page.url)).find("input", attrs={"name": name})

        assert box["type"] == "checkbox"
        assert not box.has_attr("checked")

    def test_leaving_both_unticked_saves_no_consent(self, client, donate_page):
        pledge(client, donate_page)

        saved = stored(donate_page)
        assert saved.email_updates is False
        assert saved.show_on_website is False

    def test_ticking_email_updates_saves_only_that(self, client, donate_page):
        pledge(client, donate_page, email_updates="on")

        saved = stored(donate_page)
        assert saved.email_updates is True
        assert saved.show_on_website is False

    def test_ticking_show_on_website_saves_only_that(self, client, donate_page):
        pledge(client, donate_page, show_on_website="on")

        saved = stored(donate_page)
        assert saved.show_on_website is True
        assert saved.email_updates is False

    def test_a_ticked_box_stays_ticked_when_the_form_has_errors(self, client, donate_page):
        response = pledge(client, donate_page, name="", show_on_website="on")

        box = soup(response).find("input", attrs={"name": "show_on_website"})
        assert box.has_attr("checked")

    def test_show_on_website_says_exactly_what_is_shown(self, client, donate_page):
        """This help text is the consent to the recent supporters list (#99)."""
        help_text = PledgeForm.base_fields["show_on_website"].help_text

        for shown in ("name", "amount", "appeal", "date"):
            assert shown in help_text
        assert "Nothing else about you is shown." in help_text
        box = soup(client.get(donate_page.url)).find("input", attrs={"name": "show_on_website"})
        assert box.find_next(class_="helptext").get_text(strip=True) == help_text

    def test_email_updates_says_you_can_stop(self, client, donate_page):
        assert "You can ask us to stop at any time." in client.get(donate_page.url).content.decode()

    @pytest.mark.parametrize("name", ["email_updates", "show_on_website"])
    def test_each_box_is_inside_its_label_and_described_by_its_help_text(
        self, client, donate_page, name
    ):
        """Inside its label, so the whole row can be tapped, like the radio buttons."""
        html = soup(client.get(donate_page.url))
        box = html.find("input", attrs={"name": name})

        assert box.find_parent("label")["for"] == box["id"]
        assert html.find(id=box["aria-describedby"]).get_text(strip=True)


class TestFormOrder:
    def test_the_message_comes_after_the_appeal_and_before_your_details(self, client, donate_page):
        html = client.get(donate_page.url).content.decode()

        assert html.index('name="appeal"') < html.index('name="message"')
        assert html.index('name="message"') < html.index("<legend>Your details</legend>")

    def test_the_choices_come_after_your_details_and_before_the_button(self, client, donate_page):
        response = client.get(donate_page.url)
        html = response.content.decode()

        assert html.index('name="postcode"') < html.index('name="email_updates"')
        assert html.index('name="email_updates"') < html.index('name="show_on_website"')
        assert html.index('name="show_on_website"') < html.index("Send my pledge")
        choices = (
            soup(response).find("input", attrs={"name": "email_updates"}).find_parent("fieldset")
        )
        assert choices.legend.get_text(strip=True) == "Your choices"


class TestDonatePageInTheAdmin:
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
