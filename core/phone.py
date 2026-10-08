import re

import phonenumbers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext, gettext_lazy, gettext_noop
from phonenumbers import PhoneNumberFormat, PhoneNumberType

# Countries offered for phone numbers: Nepal, then where most Nepali supporters live or work.
# Add a country with its ISO 3166 code; the calling code comes from phonenumbers. The names are
# only marked here (gettext_noop): the admin lists them in English, and supporters' form translates
# them (phone_country_choices(translate=True)).
PHONE_COUNTRIES = (
    ("NP", gettext_noop("Nepal")),
    ("IN", gettext_noop("India")),
    ("GB", gettext_noop("United Kingdom")),
    ("US", gettext_noop("United States")),
    ("AU", gettext_noop("Australia")),
    ("CA", gettext_noop("Canada")),
    ("QA", gettext_noop("Qatar")),
    ("AE", gettext_noop("United Arab Emirates")),
    ("SA", gettext_noop("Saudi Arabia")),
    ("KW", gettext_noop("Kuwait")),
    ("MY", gettext_noop("Malaysia")),
    ("JP", gettext_noop("Japan")),
    ("KR", gettext_noop("South Korea")),
)

# Number types that can receive a text or WhatsApp message. Some countries (the US, Canada,
# India) don't tell mobiles and landlines apart, so those numbers are accepted too.
MESSAGEABLE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}

PHONE_CHARACTERS = re.compile(r"^[\d\s()+.-]+$")


def phone_country_choices(translate=False):
    choices = []
    for code, name in PHONE_COUNTRIES:
        calling_code = phonenumbers.country_code_for_region(code)
        choices.append((code, f"{gettext(name) if translate else name} (+{calling_code})"))
    return choices


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
            gettext_lazy("Enter a mobile number, like %(example)s."),
            code="invalid_mobile",
            params={"example": phonenumbers.format_number(example, PhoneNumberFormat.NATIONAL)},
        )
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
