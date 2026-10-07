from django.conf import settings
from wagtail.coreutils import get_supported_content_language_variant


def language_codes():
    """The site's languages, in the order of LANGUAGES."""
    return [code for code, _name in settings.LANGUAGES]


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
