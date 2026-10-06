from django.conf import settings
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.middleware.locale import LocaleMiddleware


class URLLocaleMiddleware(LocaleMiddleware):
    """Django's LocaleMiddleware, without `Vary: Accept-Language` when the URL sets the language.

    With `prefix_default_language=False`, a URL without a prefix is always in LANGUAGE_CODE and a
    prefixed one in its prefix's language: the browser's Accept-Language never changes a response.
    Django still adds the header to unprefixed URLs, which would make caches keep one copy of each
    page per browser language, and costs every response 17 bytes (#120).
    """

    def process_response(self, request, response):
        response = super().process_response(request, response)
        urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
        i18n_patterns_used, prefixed_default_language = is_language_prefix_patterns_used(urlconf)
        if i18n_patterns_used and not prefixed_default_language and response.has_header("Vary"):
            vary = [
                header
                for header in (h.strip() for h in response["Vary"].split(","))
                if header and header.lower() != "accept-language"
            ]
            if vary:
                response["Vary"] = ", ".join(vary)
            else:
                del response["Vary"]
        return response
