from django.db.models import Q
from django.utils.functional import SimpleLazyObject
from wagtail.models import Page

from core.languages import reading_language
from core.models import AnnouncementBanner, SiteSettings


def chosen_pages(request):
    """The pages chosen in settings that every page links to, in the language being read.

    `privacy_page` is the privacy notice for the footer and forms (#105): None until a page is
    chosen and published. `donate_page_link` is the header's Donate button and `banner_link_page`
    the announcement banner's link (#117). Each is its published translation in the language
    being read, else the chosen page.

    Looked up only when a template uses one, and then all together in one query: the chosen pages
    and their published translations in the language being read.
    """

    def find():
        site_settings = SiteSettings.for_request(request)
        banner = AnnouncementBanner.for_request(request)
        chosen = {
            "privacy_page": site_settings.privacy_page_id,
            "donate_page_link": site_settings.donate_page_id,
            "banner_link_page": banner.link_page_id if banner.enabled else None,
        }
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
        if found["privacy_page"] is not None and not found["privacy_page"].live:
            found["privacy_page"] = None
        return found

    pages = SimpleLazyObject(find)
    names = ("privacy_page", "donate_page_link", "banner_link_page")
    return {name: SimpleLazyObject(lambda name=name: pages[name]) for name in names}
