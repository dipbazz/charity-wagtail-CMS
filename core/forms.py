"""Admin forms for the site's own models."""

from django.utils import translation
from django.utils.text import get_text_list
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.models import Locale

from core.languages import language_codes


class TextInEachLanguageForm(WagtailAdminModelForm):
    """A setting's form whose `texts` rows must agree on what's filled in.

    A field the row model lists in `in_every_language`, once filled in for one language, must be
    filled in for every language the site has: a refund policy for English readers alone would
    tell Nepali readers something else (#202). The other fields fall back to the main language's.
    """

    def is_valid(self):
        valid = super().is_valid()
        texts = self.formsets["texts"]
        if texts.is_valid():
            valid = self.texts_agree(texts) and valid
        return valid

    def texts_agree(self, texts):
        rows = {
            form.cleaned_data["locale"].language_code: form
            for form in texts.forms
            if form.cleaned_data.get("locale") and not form.cleaned_data.get("DELETE")
        }
        languages = Locale.objects.filter(language_code__in=language_codes()).values_list(
            "language_code", flat=True
        )
        missing_rows = {}
        agree = True
        for field in texts.model.in_every_language:
            filled = [code for code, form in rows.items() if form.cleaned_data.get(field)]
            if not filled:
                continue
            for code in languages:
                if code not in rows:
                    missing_rows.setdefault(code, []).append(field)
                elif not rows[code].cleaned_data.get(field):
                    rows[code].add_error(
                        field,
                        f"Write this in {language_name(code)} too: it's filled in for "
                        f"{language_name(filled[0])}, and readers of every language must be "
                        "told the same.",
                    )
                    agree = False
        for code, fields in missing_rows.items():
            names = [str(texts.model._meta.get_field(field).verbose_name) for field in fields]
            self.add_error(
                None,
                f"Add a row for {language_name(code)} too, with its "
                f"{get_text_list(names, 'and')}: readers of every language must be told the same.",
            )
            agree = False
        return agree


def language_name(code):
    """The language's name in English, the admin's language."""
    return translation.get_language_info(code)["name"]
