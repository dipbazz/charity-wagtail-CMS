import uuid
from dataclasses import dataclass

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import IntegrityError, transaction

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


class TextareaField(forms.CharField):
    """Text from a <textarea>, with line breaks counted as one character, as the browser counts
    them against maxlength while the supporter types.

    Browsers send each line break as two characters (CRLF), so a message that fits the box would
    otherwise fail max_length by one character per line.
    """

    def to_python(self, value):
        return super().to_python(value).replace("\r\n", "\n")


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
    # A one-time ID for this copy of the form: sending the same copy again updates its pledge
    # instead of adding a second one. Going back from the thank-you page can reload the page with
    # a new ID, so charity.js puts back the ID that was sent.
    submission_id = forms.CharField(required=False, initial=uuid.uuid4, widget=forms.HiddenInput)

    class Meta:
        model = Pledge
        fields = [
            "frequency",
            "phone",
            "appeal",
            "message",
            "name",
            "email",
            "address",
            "postcode",
            "email_updates",
            "show_on_website",
        ]
        widgets = {
            "frequency": forms.RadioSelect,
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel-national"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "address": forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}),
            "postcode": forms.TextInput(attrs={"autocomplete": "postal-code"}),
            # charity.js shows "10/1000 characters" below it (data-char-count).
            "message": forms.Textarea(attrs={"rows": 3, "data-char-count": ""}),
        }
        field_classes = {"message": TextareaField}
        # The model's names head the admin's columns; donors are asked in their own words.
        labels = {
            "name": "Your name",
            "appeal": "Which appeal would you like to support?",
            "phone": "Number",  # under its "Mobile number (optional)" legend
            "message": "A message with your gift",
            "email_updates": "Email me stories from our projects and appeals that need help",
            "show_on_website": "Show my gift on our website",
        }
        help_texts = {
            "message": (
                "For example, if you're giving in memory of someone. Only our team will read it."
            ),
            # The supporter's consents. Each says exactly what they agree to; the recent
            # supporters list (#99) must show no more than show_on_website's text promises.
            "email_updates": "You can ask us to stop at any time.",
            "show_on_website": (
                "Once your gift reaches us, we'll list your name, the amount, the appeal and the "
                "date. Nothing else about you is shown."
            ),
            # The supporter's consent to the monthly reminder (#90): keep its purpose this clear.
            "phone": (
                "We'll only use this to send you a monthly reminder on WhatsApp, or by text "
                "message if you're in Nepal and not on WhatsApp."
            ),
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
        appeal.help_text = ""  # the model's note for the team, not for donors
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
        for name in ("message", "address", "postcode"):
            self.fields[name].show_optional = True
        if link is not None:
            self.initial.update(self.initial_from_link(link))
        if self.is_bound:
            self.instance = self.pledge_sent_before() or self.instance

    def pledge_sent_before(self):
        """The pledge already saved from this copy of the form, if it's being sent again."""
        try:
            sent = uuid.UUID(self.data.get(self.add_prefix("submission_id"), ""))
        except ValueError:
            return None
        return Pledge.objects.filter(submission_id=sent).first()

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

    def clean_submission_id(self):
        """This copy's ID, or a new one if it's missing or unreadable (a page opened before IDs
        existed): never a reason to turn a pledge away."""
        try:
            return uuid.UUID(self.cleaned_data["submission_id"])
        except ValueError:
            return uuid.uuid4()

    def save(self, commit=True):
        pledge = super().save(commit=False)
        chosen = self.cleaned_data["amount"]
        pledge.amount = self.cleaned_data["other_amount"] if chosen == OTHER else int(chosen)
        pledge.currency = self.currency
        pledge.page = self.page
        pledge.submission_id = self.cleaned_data["submission_id"]
        if commit:
            try:
                with transaction.atomic():
                    pledge.save()
            except IntegrityError:
                # The same copy sent twice at once (a double click): the first one saved it.
                return Pledge.objects.get(submission_id=pledge.submission_id)
        return pledge
