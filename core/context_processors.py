from django.db.models import Q
from django.utils.functional import SimpleLazyObject
from wagtail.models import Page

from core.languages import reading_language
from core.menu import SECTIONS, SHOWN, menu_sections, private_paths
from core.models import AnnouncementBanner, SiteSettings


def chosen_pages(request):
    """The pages chosen in settings that every page links to, in the language being read.

    `privacy_page` is the privacy notice for the footer and forms (#105) and `donate_page_link` the
    header's Donate button: each None until a page is chosen and published. `banner_link_page` is
    the announcement banner's link (#117). `menu_sections` are the menu's sections that have a
    published, public page, in the standard's order (#171). Each page is its published translation
    in the language being read, else the chosen page.

    Looked up only when a template uses one, and then all together in one query: the chosen pages
    and their published translations in the language being read. The menu's sections add one, for
    the pages behind a password or login, when any section has a page.
    """

    def find():
        site_settings = SiteSettings.for_request(request)
        banner = AnnouncementBanner.for_request(request)
        chosen = {
            "privacy_page": site_settings.privacy_page_id,
            "donate_page_link": site_settings.donate_page_id,
            "banner_link_page": banner.link_page_id if banner.enabled else None,
        }
        for section in SECTIONS:
            chosen[section.setting] = getattr(site_settings, f"{section.setting}_id")
        found = find_in_reading_language(chosen)
        sections = [section.setting for section in SECTIONS]
        in_menu = {name: found.pop(name) for name in sections}
        private = private_paths() if any(page is not None for page in in_menu.values()) else []
        found["menu_sections"] = [
            section
            for section in menu_sections(site_settings, in_menu, private)
            if section.status == SHOWN
        ]
        return found

    def find_in_reading_language(chosen):
        ids = {pk for pk in chosen.values() if pk is not None}
        if not ids:
            return dict.fromkeys(chosen)
        language = reading_language()
        pages = Page.objects.filter(
            Q(pk__in=ids)
            | Q(
                translation_key__in=Page.objects.filter(pk__in=ids).values("translation_key"),
                locale__language_code=language,
                live=True,
            )
        ).select_related("locale")
        by_id = {page.pk: page for page in pages}
        translations = {
            page.translation_key: page
            for page in by_id.values()
            if page.locale.language_code == language and page.live
        }
        found = {}
        for name, pk in chosen.items():
            page = by_id.get(pk)
            found[name] = page and translations.get(page.translation_key, page)
        for name in ("privacy_page", "donate_page_link"):
            if found[name] is not None and not found[name].live:
                found[name] = None
        return found

    pages = SimpleLazyObject(find)
    names = ("privacy_page", "donate_page_link", "banner_link_page", "menu_sections")
    return {name: SimpleLazyObject(lambda name=name: pages[name]) for name in names}
