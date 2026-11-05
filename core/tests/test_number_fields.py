"""Numbers in the admin: text boxes with a number keypad, never `<input type="number">`, whose
value a scroll over it changes (#97). They take an amount written the way the site shows it."""

from decimal import Decimal

import pytest
from django import forms
from django.db import models
from wagtail.admin.panels import FieldPanel, ObjectList, get_edit_handler

from core.models import SiteSettings
from core.number_fields import DecimalNumberField, WholeNumberField


class TestWholeNumberField:
    @pytest.mark.parametrize(
        ("typed", "number"),
        [("2500", 2500), ("1,00,000", 100000), ("100,000", 100000), ("4 000", 4000)],
    )
    def test_takes_a_number_written_the_way_the_site_shows_it(self, typed, number):
        assert WholeNumberField().clean(typed) == number

    @pytest.mark.parametrize("typed", ["abc", "25.50", "1,00,000.5"])
    def test_refuses_what_isnt_a_whole_number(self, typed):
        with pytest.raises(forms.ValidationError):
            WholeNumberField().clean(typed)


class TestDecimalNumberField:
    @pytest.mark.parametrize(
        ("typed", "number"),
        [
            ("50000", Decimal("50000")),
            ("1,00,000", Decimal("100000")),
            ("1,00,000.50", Decimal("100000.50")),
            ("4 000.25", Decimal("4000.25")),
        ],
    )
    def test_takes_a_number_written_the_way_the_site_shows_it(self, typed, number):
        assert DecimalNumberField(max_digits=12, decimal_places=2).clean(typed) == number

    @pytest.mark.parametrize("typed", ["abc", "1.234"])
    def test_refuses_what_isnt_an_amount(self, typed):
        with pytest.raises(forms.ValidationError):
            DecimalNumberField(max_digits=12, decimal_places=2).clean(typed)


class Counted(models.Model):
    """A model with every kind of number field, to build an admin form for."""

    whole = models.IntegerField()
    positive = models.PositiveIntegerField()
    small = models.PositiveSmallIntegerField()
    decimal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = "core"
        managed = False

    def __str__(self):
        return str(self.whole)


def admin_form(model, fields):
    return ObjectList([FieldPanel(name) for name in fields]).bind_to_model(model).get_form_class()


class TestEveryAdminNumberField:
    @pytest.mark.parametrize("name", ["whole", "positive", "small"])
    def test_a_whole_number_is_a_text_box_with_the_number_keypad(self, name):
        field = admin_form(Counted, [name])().fields[name]

        assert isinstance(field, WholeNumberField)
        assert field.widget.input_type == "text"
        assert field.widget.attrs["inputmode"] == "numeric"

    def test_a_decimal_is_a_text_box_with_the_decimal_keypad(self):
        field = admin_form(Counted, ["decimal"])().fields["decimal"]

        assert isinstance(field, DecimalNumberField)
        assert field.widget.input_type == "text"
        assert field.widget.attrs["inputmode"] == "decimal"

    def test_keeps_the_model_s_limits(self):
        form = admin_form(Counted, ["positive", "decimal"])(
            data={"positive": "-1", "decimal": "1,00,00,00,00,000"}
        )

        assert set(form.errors) == {"positive", "decimal"}

    def test_a_panel_s_own_widget_still_wins(self):
        """The logo size stays a slider (a range input), which a scroll doesn't change."""
        field = get_edit_handler(SiteSettings).get_form_class()().fields["logo_size"]

        assert field.widget.input_type == "range"
