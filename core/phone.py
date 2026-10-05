import re

import phonenumbers
from django.core.exceptions import ValidationError
from phonenumbers import PhoneNumberFormat, PhoneNumberType

# Countries offered for phone numbers: Nepal, then where most Nepali supporters live or work.
# Add a country with its ISO 3166 code; the calling code comes from phonenumbers.
PHONE_COUNTRIES = (
    ("NP", "Nepal"),
    ("IN", "India"),
    ("GB", "United Kingdom"),
    ("US", "United States"),
    ("AU", "Australia"),
    ("CA", "Canada"),
    ("QA", "Qatar"),
    ("AE", "United Arab Emirates"),
    ("SA", "Saudi Arabia"),
    ("KW", "Kuwait"),
    ("MY", "Malaysia"),
    ("JP", "Japan"),
    ("KR", "South Korea"),
)

# Number types that can receive a text or WhatsApp message. Some countries (the US, Canada,
# India) don't tell mobiles and landlines apart, so those numbers are accepted too.
MESSAGEABLE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}

PHONE_CHARACTERS = re.compile(r"^[\d\s()+.-]+$")


def phone_country_choices():
    return [
        (code, f"{name} (+{phonenumbers.country_code_for_region(code)})")
        for code, name in PHONE_COUNTRIES
    ]


def normalise_mobile(number, region):
    """Return a mobile number in E.164 (+9779841234567), or raise ValidationError.

    A number typed with its own +country code keeps it; otherwise `region` supplies it.
    """
    try:
        if not PHONE_CHARACTERS.match(number):
            raise phonenumbers.NumberParseException(0, "Not a phone number")
        parsed = phonenumbers.parse(number, region)
    except phonenumbers.NumberParseException:
        parsed = None
    if (
        parsed is None
        or not phonenumbers.is_valid_number(parsed)
        or phonenumbers.number_type(parsed) not in MESSAGEABLE_TYPES
    ):
        example = phonenumbers.example_number_for_type(region, PhoneNumberType.MOBILE)
        raise ValidationError(
            "Enter a mobile number, like %(example)s.",
            code="invalid_mobile",
            params={"example": phonenumbers.format_number(example, PhoneNumberFormat.NATIONAL)},
        )
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
