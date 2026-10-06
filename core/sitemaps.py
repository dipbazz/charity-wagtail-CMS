from django.db.models import Q
from wagtail.contrib.sitemaps import Sitemap
from wagtail.models import Page


class AllLanguagesSitemap(Sitemap):
    """Wagtail's sitemap, listing the pages of every language.

    Wagtail's own lists only the site's main language: the pages under the Site's root page, but
    not under that page's translations, such as the Nepali home page at /ne/.
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
