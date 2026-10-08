"""Appeals and the pledge form in Nepali (#116): the words around the editors' content."""

import pytest
from bs4 import BeautifulSoup
from django.utils import translation

from campaigns.forms import PledgeForm
from campaigns.models import Pledge
from core.models import SiteSettings

pytestmark = pytest.mark.django_db


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def visible_text(response):
    return soup(response).get_text(" ", strip=True)


def translated(page, locale):
    translation_ = page.copy_for_translation(locale)
    translation_.save_revision().publish()
    return translation_


@pytest.fixture
def nepali_donate_page(donate_page, nepali_home_page):
    return translated(donate_page, nepali_home_page.locale)


@pytest.fixture
def nepali_appeal(appeals, nepali_home_page):
    index = translated(appeals, nepali_home_page.locale)
    flood_relief = appeals.get_children().get(slug="flood-relief").specific
    return translated(flood_relief, index.locale)


class TestEnglishIsUnchanged:
    def test_the_pledge_form_stays_english(self, client, donate_page):
        text = visible_text(client.get(donate_page.url))

        assert "How much would you like to give?" in text
        assert "Other amount" in text
        assert "Send my pledge" in text

    def test_the_labels_the_form_words_itself_match_the_model_s_wording(self):
        form = PledgeForm.base_fields

        assert str(form["frequency"].label) == "How often"
        assert str(form["email"].label) == "Email address"
        assert str(form["postcode"].label) == "Postcode or postal code"


class TestAppealsInNepali:
    def test_the_donate_button_in_nepali(self, client, nepali_home_page, donate_page, home_page):
        settings = SiteSettings.for_site(home_page.get_site())
        settings.donate_page = donate_page
        settings.save()

        assert ">दान दिनुहोस्</a>" in client.get("/ne/").content.decode()

    def test_the_appeals_list_in_nepali(self, client, nepali_appeal):
        text = visible_text(client.get(nepali_appeal.get_parent().url))

        assert "सबै अपिलहरू" in text
        assert "खुला अपिलहरू" in text
        assert "विगतका अपिलहरू" in text
        assert "All appeals" not in text

    def test_amounts_keep_their_lakh_grouping(self, client, nepali_appeal):
        nepali_appeal.target_amount = 4687500
        nepali_appeal.amount_raised = 100000
        nepali_appeal.save_revision().publish()

        response = client.get(nepali_appeal.url)

        assert "Rs 46,87,500 मध्ये Rs 1,00,000 जम्मा भयो" in visible_text(response)
        assert 'aria-label="कोष सङ्कलनको प्रगति"' in response.content.decode()

    def test_an_appeal_s_closing_date_in_nepali(self, client, nepali_appeal):
        nepali_appeal.end_date = nepali_appeal.start_date.replace(year=2099)
        nepali_appeal.save_revision().publish()

        text = visible_text(client.get(nepali_appeal.url))

        assert "मा बन्द हुन्छ" in text
        assert "closes" not in text

    def test_a_closed_appeal_card_in_nepali(self, client, appeals, nepali_home_page):
        index = translated(appeals, nepali_home_page.locale)
        last_year = appeals.get_children().get(slug="last-year").specific
        translated(last_year, index.locale)

        assert "यो अपिल बन्द भइसकेको छ।" in visible_text(client.get(index.url, {"status": "closed"}))


class TestThePledgeFormInNepali:
    def test_labels_and_choices(self, client, nepali_donate_page):
        text = visible_text(client.get(nepali_donate_page.url))

        for nepali in [
            "तपाईं कति दान दिन चाहनुहुन्छ?",
            "अन्य रकम",
            "कति पटक",
            "एक पटक",
            "मासिक",
            "मोबाइल नम्बर",
            "वैकल्पिक",
            "तपाईंको पुरा नाम",
            "इमेल ठेगाना",
            "हुलाक कोड",
            "तपाईंका रोजाइहरू",
            "मेरो प्रतिबद्धता पठाउनुहोस्",
        ]:
            assert nepali in text
        for english in ["How much", "Other amount", "One-off", "optional", "Send my pledge"]:
            assert english not in text

    def test_the_own_amount_names_the_currency_in_nepali(self, client, nepali_donate_page):
        assert "तपाईंको आफ्नै रकम (Rs)" in visible_text(client.get(nepali_donate_page.url))

    def test_the_character_count_is_worded_in_nepali(self, client, nepali_donate_page):
        message = soup(client.get(nepali_donate_page.url)).find("textarea", {"name": "message"})

        # charity.js fills in the numbers.
        assert message["data-count-text"] == "{typed}/{limit} अक्षर"
        assert "{left}" in message["data-left-text"]
        assert "{limit}" in message["data-full-text"]

    def test_the_phone_countries_in_nepali(self, client, nepali_donate_page):
        options = soup(client.get(nepali_donate_page.url)).select("#id_phone_country option")

        assert options[0].text == "नेपाल (+977)"
        assert "बेलायत (+44)" in [option.text for option in options]

    def test_errors(self, client, nepali_donate_page):
        response = client.post(nepali_donate_page.url, {"amount": "", "phone_country": "NP"})
        text = visible_text(response)

        assert "कृपया आफ्नो प्रतिबद्धता जाँच्नुहोस्" in text
        assert "रकम छान्नुहोस् वा आफ्नै रकम लेख्नुहोस्।" in text
        assert "आफ्नो नाम लेख्नुहोस्।" in text
        assert "आफ्नो इमेल ठेगाना लेख्नुहोस्।" in text
        assert "Please check" not in text
        assert "Enter your" not in text

    def test_a_choice_of_two_amounts_is_refused_in_nepali(self, client, nepali_donate_page):
        response = client.post(
            nepali_donate_page.url,
            {"amount": "2500", "other_amount": "300", "phone_country": "NP"},
        )

        assert "दुवै होइन।" in visible_text(response)

    def test_a_mobile_number_error(self, client, nepali_donate_page):
        response = client.post(
            nepali_donate_page.url,
            {"amount": "2500", "frequency": "monthly", "phone": "123", "phone_country": "NP"},
        )

        assert "मोबाइल नम्बर लेख्नुहोस्, जस्तै" in visible_text(response)

    def test_django_s_own_errors_are_in_nepali_too(self, nepali_donate_page):
        form = PledgeForm(
            {"message": "x" * 1001},
            page=nepali_donate_page,
            currency="NPR",
            phone_country="NP",
        )

        with translation.override("ne"):
            form.is_valid()
            error = str(form.errors["message"][0])

        assert "1000" in error
        assert "Ensure" not in error

    def test_the_thank_you_page(self, client, nepali_donate_page):
        response = client.post(
            nepali_donate_page.url,
            {
                "amount": "2500",
                "frequency": "one-off",
                "name": "Sita Sharma",
                "email": "sita@example.com",
                "phone_country": "NP",
            },
            follow=True,
        )

        assert Pledge.objects.count() == 1
        assert soup(response).h1.text == "धन्यवाद"


class TestThePledgeModelStaysEnglishForTheAdmin:
    def test_labels_and_help_texts(self):
        with translation.override("ne"):
            assert Pledge._meta.get_field("frequency").verbose_name == "how often"
            assert str(Pledge._meta.get_field("address").help_text).startswith("House or ward")
