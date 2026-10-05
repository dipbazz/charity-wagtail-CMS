from dataclasses import dataclass

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator

from campaigns.models import Frequency, Pledge
from core.money import CURRENCIES, format_money
from core.phone import normalise_mobile, phone_country_choices

NEEDED_MOST = "Wherever it's needed most"
CHOOSE_AN_AMOUNT = "Choose an amount or enter your own."
OTHER = "other"


@dataclass(frozen=True)
class AmountLabel:
    """A suggested amount's label, kept in parts so the template can lay them out.

    Not a tuple: Django would read a tuple label as a group of choices.
    """

    amount: str
    impact: str = ""

    def __str__(self):
        return f"{self.amount}: {self.impact}" if self.impact else self.amount


class WholeAmountField(forms.IntegerField):
    """A whole amount, also written the way the site shows amounts: "1,00,000" or "4 000"."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(",", "").replace(" ", "")
        return super().to_python(value)


class PledgeForm(forms.ModelForm):
    """A pledge to give, saved as a Pledge. No payment is taken.

    Fields, labels, help text and choices come from the Pledge model; this form only adds how
    the page asks for them: the amount cards, the supporter's own amount and the phone country.
    """

    # Adds "(optional)" to the labels of fields marked show_optional in __init__.
    template_name_label = "campaigns/forms/label.html"

    # Not required: typing your own amount without choosing "Other amount" is enough (clean()).
    amount = forms.ChoiceField(
        required=False,
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": CHOOSE_AN_AMOUNT},
    )
    # A text box, not type="number": scrolling over a number input changes its value, so a donor
    # could pledge an amount they never meant. inputmode still brings up the number keypad.
    other_amount = WholeAmountField(
        required=False,
        max_value=99_999_999,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )
    phone_country = forms.ChoiceField(choices=phone_country_choices, label="Country")

    class Meta:
        model = Pledge
        fields = ["frequency", "phone", "appeal", "name", "email", "address", "postcode"]
        widgets = {
            "frequency": forms.RadioSelect,
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel-national"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "address": forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
        }
        # Each error says which field it's about, because the summary at the top lists them all.
        error_messages = {
            "name": {"required": "Enter your name."},
            "email": {"required": "Enter your email address."},
        }

    def __init__(self, *args, page, currency, phone_country, link=None, **kwargs):
        """`page` is the Donate page (its suggested amounts and appeals), and `link` the query
        string of the link that brought the visitor here (?amount=&appeal=).
        """
        kwargs.setdefault("label_suffix", "")  # "Your name", not "Your name:"
        super().__init__(*args, **kwargs)
        self.page = page
        self.currency = currency
        amounts = page.donation_amounts.all()
        self.suggested = {str(option.amount) for option in amounts}
        self.fields["amount"].choices = [
            (str(option.amount), AmountLabel(format_money(option.amount, currency), option.impact))
            for option in amounts
        ] + [(OTHER, AmountLabel("Other amount"))]
        self.fields["other_amount"].label = f"Your own amount ({CURRENCIES[currency][1].strip()})"

        # Appeals are chosen and linked by slug: /donate/?appeal=flood-relief.
        appeal = self.fields["appeal"]
        appeal.queryset = page.get_appeals()
        appeal.to_field_name = "slug"
        appeal.empty_label = NEEDED_MOST
        appeal.help_text = ""
        if self.initial.get("appeal") is None:
            self.initial["appeal"] = ""  # renders "Wherever it's needed most" as chosen

        # The column holds the cleaned-up number (E.164, at most 16 characters), but people type
        # spaces, dashes and brackets, so allow more here; clean() normalises it.
        phone = self.fields["phone"]
        phone.max_length = 30
        phone.validators = [MaxLengthValidator(30)]
        phone.widget.attrs["maxlength"] = "30"

        self.fields["phone_country"].initial = phone_country
        # Not every optional field: the appeal has a default, and the mobile number's legend
        # already says it's optional.
        for name in ("address", "postcode"):
            self.fields[name].show_optional = True
        if link is not None:
            self.initial.update(self.initial_from_link(link))

    def initial_from_link(self, link):
        """Preselect the amount and appeal named in the link, ignoring any that aren't offered."""
        initial = {}
        slug = link.get("appeal")
        if slug and self.fields["appeal"].queryset.filter(slug=slug).exists():
            initial["appeal"] = slug
        amount = link.get("amount", "")
        if amount in self.suggested:
            initial["amount"] = amount
        elif amount.isdecimal() and int(amount) > 0:
            initial["amount"] = OTHER
            initial["other_amount"] = int(amount)
        return initial

    def clean(self):
        cleaned_data = super().clean()
        if "amount" not in self.errors:
            other_amount = cleaned_data.get("other_amount")
            if not cleaned_data.get("amount") and other_amount:
                cleaned_data["amount"] = OTHER
            if not cleaned_data.get("amount") or (
                cleaned_data["amount"] == OTHER and not (other_amount or 0) > 0
            ):
                self.add_error("amount", CHOOSE_AN_AMOUNT)
            elif cleaned_data["amount"] != OTHER and other_amount:
                # Saving either one could record a gift the supporter didn't mean.
                self.add_error("amount", "Choose a suggested amount or type your own, not both.")

        # The number is only for the monthly reminder, so a one-off gift doesn't keep it.
        if cleaned_data.get("frequency") != Frequency.MONTHLY:
            cleaned_data["phone"] = ""
        phone = cleaned_data.get("phone", "").strip()
        if phone and cleaned_data.get("phone_country"):
            try:
                cleaned_data["phone"] = normalise_mobile(phone, cleaned_data["phone_country"])
            except ValidationError as error:
                self.add_error("phone", error)

        return cleaned_data

    def save(self, commit=True):
        pledge = super().save(commit=False)
        chosen = self.cleaned_data["amount"]
        pledge.amount = self.cleaned_data["other_amount"] if chosen == OTHER else int(chosen)
        pledge.currency = self.currency
        pledge.page = self.page
        if commit:
            pledge.save()
        return pledge
