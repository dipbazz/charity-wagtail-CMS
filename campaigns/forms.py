from dataclasses import dataclass

from django import forms
from django.core.exceptions import ValidationError
from wagtail.contrib.forms.forms import BaseForm

from core.money import CURRENCIES, format_money
from core.phone import normalise_mobile, phone_country_choices

FREQUENCIES = {"one-off": "One-off", "monthly": "Monthly"}
NEEDED_MOST = "Wherever it's needed most"
CHOOSE_AN_AMOUNT = "Choose an amount or enter your own."
OTHER = "other"

# HMRC's model Gift Aid declaration for one-off and future donations.
GIFT_AID_DECLARATION = (
    "I want to Gift Aid this donation and any donations I make in the future or have made in the "
    "past 4 years to {charity}. I am a UK taxpayer and understand that if I pay less Income Tax "
    "and/or Capital Gains Tax than the amount of Gift Aid claimed on all my donations in that tax "
    "year it is my responsibility to pay any difference."
)


@dataclass(frozen=True)
class AmountLabel:
    """A suggested amount's label, kept in parts so the template can lay them out.

    Not a tuple: Django would read a tuple label as a group of choices.
    """

    amount: str
    impact: str = ""

    def __str__(self):
        return f"{self.amount}: {self.impact}" if self.impact else self.amount


class PledgeForm(BaseForm):
    """A pledge to give, saved as a form submission. No payment is taken."""

    # Not required: typing your own amount without choosing "Other amount" is enough (clean()).
    amount = forms.ChoiceField(
        required=False,
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": CHOOSE_AN_AMOUNT},
    )
    other_amount = forms.IntegerField(
        required=False,
        max_value=99_999_999,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": 1}),
    )
    frequency = forms.ChoiceField(
        choices=FREQUENCIES.items(),
        widget=forms.RadioSelect,
        initial="one-off",
        label="How often",
    )
    name = forms.CharField(
        max_length=255, label="Your name", widget=forms.TextInput(attrs={"autocomplete": "name"})
    )
    email = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    phone_country = forms.ChoiceField(choices=phone_country_choices, label="Country")
    phone = forms.CharField(
        required=False,
        max_length=30,
        label="Number",
        help_text=(
            "If you give monthly, we'll only use this to send you a monthly reminder "
            "on WhatsApp, or by text message if you're in Nepal and not on WhatsApp."
        ),
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel-national"}),
    )
    appeal = forms.ChoiceField(required=False, label="Which appeal would you like to support?")
    address = forms.CharField(
        required=False,
        max_length=500,
        label="Address",
        help_text="House or ward number, street or tole, town or municipality, district.",
        widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}),
    )
    postcode = forms.CharField(
        required=False,
        max_length=12,
        label="Postcode or postal code",
        widget=forms.TextInput(attrs={"autocomplete": "postal-code"}),
    )
    gift_aid = forms.BooleanField(required=False, label="Yes, add Gift Aid to my gift")

    def __init__(
        self,
        *args,
        amounts,
        appeals,
        currency,
        phone_country,
        charity_name,
        offer_gift_aid,
        link=None,
        **kwargs,
    ):
        """`amounts` are the page's suggested amounts, `appeals` the appeals on offer, and
        `link` the query string of the link that brought the visitor here (?amount=&appeal=).
        """
        super().__init__(*args, **kwargs)
        self.currency = currency
        self.fields["other_amount"].label = f"Your own amount ({CURRENCIES[currency][1].strip()})"
        self.suggested = {str(option.amount) for option in amounts}
        self.fields["amount"].choices = [
            (str(option.amount), AmountLabel(format_money(option.amount, currency), option.impact))
            for option in amounts
        ] + [(OTHER, AmountLabel("Other amount"))]
        self.appeal_titles = {"": NEEDED_MOST} | {appeal.slug: appeal.title for appeal in appeals}
        self.fields["appeal"].choices = self.appeal_titles.items()
        self.fields["phone_country"].initial = phone_country
        if offer_gift_aid:
            self.fields["gift_aid"].help_text = GIFT_AID_DECLARATION.format(charity=charity_name)
        else:
            del self.fields["gift_aid"]
        self.initial.setdefault("appeal", "")
        if link is not None:
            self.initial.update(self.initial_from_link(link))

    def initial_from_link(self, link):
        """Preselect the amount and appeal named in the link, ignoring any that aren't offered."""
        initial = {}
        if link.get("appeal") in self.appeal_titles:
            initial["appeal"] = link["appeal"]
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

        phone = cleaned_data.get("phone", "").strip()
        if phone and cleaned_data.get("phone_country"):
            try:
                cleaned_data["phone"] = normalise_mobile(phone, cleaned_data["phone_country"])
            except ValidationError as error:
                self.add_error("phone", error)

        if cleaned_data.get("gift_aid"):
            if not cleaned_data.get("address"):
                self.add_error("address", "Enter your home address to claim Gift Aid.")
            if not cleaned_data.get("postcode"):
                self.add_error("postcode", "Enter your postcode to claim Gift Aid.")
        return cleaned_data

    def pledge_data(self):
        """The pledge as it's stored and exported: one amount, readable values, JSON-safe."""
        data = self.cleaned_data
        amount = data["other_amount"] if data["amount"] == OTHER else data["amount"]
        return {
            "amount": str(amount),
            "currency": self.currency,
            "frequency": FREQUENCIES[data["frequency"]],
            "name": data["name"],
            "email": data["email"],
            "phone": data["phone"],
            "appeal": self.appeal_titles[data["appeal"]],
            "gift_aid": data.get("gift_aid", False),
            "address": data["address"],
            "postcode": data["postcode"],
        }
