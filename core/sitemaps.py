from collections import defaultdict

from django.db.models import Q
from wagtail.contrib.sitemaps import Sitemap
from wagtail.models import Locale, Page

from core.languages import hreflang_alternates


class AllLanguagesSitemap(Sitemap):
    """Wagtail's sitemap, listing the pages of every language.

    Wagtail's own lists only the site's main language: the pages under the Site's root page, but
    not under that page's translations, such as the Nepali home page at /ne/. Each translated page
    lists its translations as `hreflang` alternates (#115).
    """

    def items(self):
        root = self.get_wagtail_site().root_page
        trees = Q()
        for home_page in root.get_translations(inclusive=True):
            trees |= Page.objects.descendant_of_q(home_page, inclusive=True)
        return (
            Page.objects.filter(trees)
            .live()
            .public()
            .order_by("path")
            .defer_streamfields()
            .specific()
        )

    def _urls(self, page, protocol, domain):
        # Wagtail's _urls, plus alternates. A page's translations are on the same sitemap page,
        # because a sitemap holds 50,000 pages and this site has far fewer.
        items = list(self.paginator.page(page).object_list)
        languages = dict(Locale.objects.values_list("pk", "language_code"))
        translations = defaultdict(dict)
        for item in items:
            translations[item.translation_key][languages[item.locale_id]] = item

        urls = []
        last_mods = set()
        for item in items:
            alternates = [
                {"lang_code": code, "location": location}
                for code, location in hreflang_alternates(
                    translations[item.translation_key], self.request
                )
            ]
            for url_info in item.get_sitemap_urls(self.request):
                if alternates:
                    url_info["alternates"] = alternates
                urls.append(url_info)
                last_mods.add(url_info.get("lastmod"))

        # last_mods might be empty if the whole site is private
        if last_mods and None not in last_mods:
            self.latest_lastmod = max(last_mods)
        return urls
