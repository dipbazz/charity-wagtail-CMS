from django.conf import settings
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.http import Http404, HttpResponseRedirect
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from wagtail.models import Site


class URLLocaleMiddleware(LocaleMiddleware):
    """Django's LocaleMiddleware, for URLs that alone set the language.

    With `prefix_default_language=False`, a URL without a prefix is always in LANGUAGE_CODE and a
    prefixed one in its prefix's language. So:

    - a second-language address with no page there (/ne/news/ before the news page is translated)
      redirects to the same address in the main language (/news/), if a page is there;
    - responses don't get `Vary: Accept-Language`. Django adds it to unprefixed URLs, which would
      make caches keep one copy of each page per browser language, and costs every response 17
      bytes (#120).
    """

    def process_response(self, request, response):
        response = super().process_response(request, response)
        if response.status_code == 404:
            fallback = self.main_language_url(request)
            if fallback:
                return HttpResponseRedirect(fallback)

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

    def main_language_url(self, request):
        """The same address in the main language, if a page is there; otherwise None."""
        language = translation.get_language_from_path(request.path_info)
        main_language = translation.get_supported_language_variant(settings.LANGUAGE_CODE)
        site = Site.find_for_request(request)
        if not language or language == main_language or site is None:
            return None

        path = request.path_info.removeprefix(f"/{language}")
        with translation.override(main_language):
            try:
                site.root_page.localized.specific.route(request, [c for c in path.split("/") if c])
            except Http404:
                return None
        query = request.META.get("QUERY_STRING")
        return f"{path}?{query}" if query else path
