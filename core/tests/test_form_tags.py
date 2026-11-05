from django import forms

from core.templatetags.form_tags import error_summary


class Pledge(forms.Form):
    name = forms.CharField()
    amount = forms.ChoiceField(
        choices=[("500", "Rs 500"), ("1000", "Rs 1,000")], widget=forms.RadioSelect
    )
    size = forms.ChoiceField(choices=[("s", "Small"), ("l", "Large")])
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            reply = "Give us an email or phone number so we can reply."
            self.add_error(None, reply)
            self.add_error("email", reply)
        return data


def summary(data):
    form = Pledge(data)
    form.is_valid()
    return error_summary(form)


def test_each_field_error_links_to_its_field():
    assert summary({"amount": "500", "size": "s", "email": "sam@example.com"}) == [
        {"message": "This field is required.", "target": "id_name"},
    ]


def test_a_radio_group_links_to_its_first_choice_and_a_dropdown_to_itself():
    """A radio group has no box of its own to go to; a dropdown does."""
    entries = summary({"name": "Sam", "size": "x", "email": "sam@example.com"})

    assert [entry["target"] for entry in entries] == ["id_amount_0", "id_size"]


def test_a_form_wide_error_comes_first_and_links_to_the_field_that_shows_it():
    """Shown once, though the form and the Email field both have it (#167)."""
    entries = summary({"amount": "500", "size": "s"})

    assert entries == [
        {"message": "Give us an email or phone number so we can reply.", "target": "id_email"},
        {"message": "This field is required.", "target": "id_name"},
    ]


def test_a_form_wide_error_no_field_shows_has_no_link():
    form = Pledge({"name": "Sam", "amount": "500", "size": "s", "email": "sam@example.com"})
    form.is_valid()
    form.add_error(None, "Something went wrong.")

    assert error_summary(form) == [{"message": "Something went wrong.", "target": None}]


def test_a_valid_form_has_no_summary():
    assert summary({"name": "Sam", "amount": "500", "size": "s", "phone": "9800000000"}) == []
