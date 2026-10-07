from dataclasses import dataclass, field

from django import template
from django.conf import settings
from django.urls import translate_url
from django.utils import translation
from wagtail.models import Page, Site

from core.languages import hreflang_alternates, language_codes

register = template.Library()


@dataclass(frozen=True)
class LanguageLink:
    code: str
    name: str
    url: str
    current: bool


@dataclass(frozen=True)
class LanguageVersions:
    links: list[LanguageLink] = field(default_factory=list)
    alternates: list[tuple[str, str]] = field(default_factory=list)


@register.simple_tag(takes_context=True)
def language_versions(context):
    """Where a reader can switch language to, and the page's `hreflang` alternates (#115).

    The switcher links to the page being read in each language that has a live home page on this
    site: to the page's live translation if there is one, otherwise to that language's home page,
    so it never leads to a 404. Without a page (search), it goes to the same view in the other
    language. It has no links when the site has content in one language only.
    """
    request = context.get("request")
    site = Site.find_for_request(request)
    if site is None:
        return LanguageVersions()

    page = context.get("page")
    if not isinstance(page, Page):
        page = None
    home_key = site.root_page.translation_key
    keys = {home_key} if page is None else {home_key, page.translation_key}
    # One query for the home pages and the page's translations, in every language.
    homes, translations = {}, {}
    for live_page in Page.objects.live().filter(translation_key__in=keys).select_related("locale"):
        code = live_page.locale.language_code
        if live_page.translation_key == home_key:
            homes[code] = live_page
        if page is not None and live_page.translation_key == page.translation_key:
            translations[code] = live_page

    codes = [code for code in language_codes() if code in homes]
    if len(codes) < 2:
        return LanguageVersions(alternates=hreflang_alternates(translations, request))

    names = dict(settings.LANGUAGES)
    current_language = translation.get_language()
    current_path = request.get_full_path()
    match = request.resolver_match
    serves_a_view = page is None and match is not None and match.url_name != "wagtail_serve"
    links = []
    for code in codes:
        if code == current_language:
            url = current_path
        elif code in translations:
            url = translations[code].get_url(request)
        elif serves_a_view:
            url = translate_url(current_path, code)
        else:
            url = homes[code].get_url(request)
        links.append(LanguageLink(code, names[code], url, code == current_language))
    return LanguageVersions(links, hreflang_alternates(translations, request))
