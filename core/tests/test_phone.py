import pytest
from django.core.exceptions import ValidationError
from django.utils import translation

from core.models import SiteSettings
from core.phone import normalise_mobile, phone_country_choices

pytestmark = pytest.mark.django_db


class TestNormaliseMobile:
    def test_nepali_mobile_is_stored_with_its_country_code(self):
        assert normalise_mobile("984-1234567", "NP") == "+9779841234567"

    def test_uk_mobile_drops_the_leading_zero(self):
        assert normalise_mobile("07400 123456", "GB") == "+447400123456"

    def test_a_number_typed_with_its_own_country_code_wins_over_the_chosen_country(self):
        assert normalise_mobile("+44 7400 123456", "NP") == "+447400123456"

    def test_us_numbers_can_be_mobile_or_landline_so_are_accepted(self):
        assert normalise_mobile("(201) 555-0123", "US") == "+12015550123"

    @pytest.mark.parametrize(
        "number",
        [
            "01-4567890",  # a Kathmandu landline can't receive a text
            "984123",  # too short for Nepal
            "98abc12345",
            "FLOWERS",
        ],
    )
    def test_rejects_what_cannot_receive_a_message(self, number):
        with pytest.raises(ValidationError, match="like 984-1234567"):
            normalise_mobile(number, "NP")

    def test_the_error_is_in_the_language_being_read(self):
        with translation.override("ne"):
            with pytest.raises(ValidationError) as error:
                normalise_mobile("123", "NP")
            message = error.value.messages[0]

        assert "मोबाइल नम्बर लेख्नुहोस्, जस्तै 984-1234567" in message


class TestPhoneCountryChoices:
    def test_nepal_comes_first_with_its_calling_code(self):
        assert phone_country_choices()[0] == ("NP", "Nepal (+977)")

    def test_includes_where_nepali_supporters_live_and_work(self):
        codes = [code for code, label in phone_country_choices()]

        assert {"IN", "GB", "QA", "AE", "MY", "JP", "KR"} <= set(codes)


def test_new_sites_default_to_nepal_for_phone_numbers(site):
    assert SiteSettings.for_site(site).phone_country == "NP"
