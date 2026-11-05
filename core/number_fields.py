"""Numbers typed into forms: text boxes with a number keypad, never `<input type="number">`.

A browser changes a focused number input's value when the pointer scrolls over it, so an editor
scrolling the page, or a donor, could save an amount they never meant (#89, #97). `inputmode`
still brings up the number keypad on a phone. The fields also take a number written the way the
site shows amounts: "1,00,000" or "4 000".
"""

from django import forms
from django.db import models
from wagtail.admin.forms.models import register_form_field_override


def without_separators(value):
    """A typed number without the commas and spaces that group its digits."""
    if isinstance(value, str):
        return value.replace(",", "").replace(" ", "")
    return value


class WholeNumberField(forms.IntegerField):
    """A whole number, in a text box with the number keypad."""

    widget = forms.TextInput(attrs={"inputmode": "numeric"})

    def to_python(self, value):
        return super().to_python(without_separators(value))


class DecimalNumberField(forms.DecimalField):
    """A number that may have a part after the point, in a text box with the decimal keypad."""

    widget = forms.TextInput(attrs={"inputmode": "decimal"})

    def to_python(self, value):
        return super().to_python(without_separators(value))


# Each kind of model number field (and its subclasses), and the form field it gets.
FORM_CLASSES = {models.IntegerField: WholeNumberField, models.DecimalField: DecimalNumberField}


def use_text_boxes_for_admin_numbers():
    """Make every number field in a Wagtail admin form built from panels one of these, whatever
    the model: pages, their inline rows, snippets and settings. A panel's own widget still wins
    (the logo size slider)."""
    for model_field, form_class in FORM_CLASSES.items():
        register_form_field_override(model_field, override={"form_class": form_class})


def number_formfield(db_field, **kwargs):
    """The model field's form field, one of these if it's a number: for an admin form built
    without panels, such as a ModelViewSet's `form_fields`, which Wagtail's overrides miss."""
    for model_field, form_class in FORM_CLASSES.items():
        if isinstance(db_field, model_field):
            kwargs.setdefault("form_class", form_class)
    return db_field.formfield(**kwargs)
