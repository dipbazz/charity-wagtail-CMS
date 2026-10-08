from django.conf import settings
from django.utils import translation
from wagtail.coreutils import get_supported_content_language_variant


def language_codes():
    """The site's languages, in the order of LANGUAGES."""
    return [code for code, _name in settings.LANGUAGES]


def main_language():
    """The language the site opens in: its pages have no prefix in their address."""
    return get_supported_content_language_variant(settings.LANGUAGE_CODE)


def reading_language():
    """The language of the page being read, which its address sets."""
    return get_supported_content_language_variant(translation.get_language())


def in_reading_language(snippets):
    """Each translatable snippet in the language being read, else in the main language (#117).

    One query, in the queryset's order. A snippet with neither version is left out, as a page only
    in one language is listed only in that language.
    """
    reading, main = reading_language(), main_language()
    candidates = list(
        snippets.filter(locale__language_code__in={reading, main}).select_related("locale")
    )
    translated = {
        snippet.translation_key for snippet in candidates if snippet.locale.language_code == reading
    }
    return [
        snippet
        for snippet in candidates
        if snippet.locale.language_code == reading or snippet.translation_key not in translated
    ]


def hreflang_alternates(translations, request=None):
    """The `hreflang` links for one page, given its live translations as {language code: page}.

    Each language's version, then `x-default` for the main language's, so search engines know the
    pages are one page in several languages. Empty for a page in one language only (#115).
    """
    if len(translations) < 2:
        return []
    alternates = [
        (code, translations[code].get_full_url(request))
        for code in language_codes()
        if code in translations
    ]
    main_language = get_supported_content_language_variant(settings.LANGUAGE_CODE)
    if main_language in translations:
        alternates.append(("x-default", translations[main_language].get_full_url(request)))
    return alternates
