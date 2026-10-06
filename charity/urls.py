from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from charity.api import api_router
from core.sitemaps import AllLanguagesSitemap
from core.views import robots_txt, serve_media
from search import views as search_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v2/", api_router.urls),
    path("sitemap.xml", sitemap, {"sitemaps": {"wagtail": AllLanguagesSitemap}}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
]


if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static files from the development server. Media goes through serve_media below
    # (dev settings turn SERVE_MEDIA on), so dev keeps private documents out of /media/ too.
    urlpatterns += staticfiles_urlpatterns()

    if "debug_toolbar" in settings.INSTALLED_APPS:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()

urlpatterns = urlpatterns + [
    path("media/<path:path>", serve_media, name="media"),
]

# Pages and search in each language: the main language (LANGUAGE_CODE) at /, the other under its
# prefix, e.g. /ne/ on an English site or /en/ on a Nepali one.
urlpatterns += i18n_patterns(
    path("search/", search_views.search, name="search"),
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    prefix_default_language=False,
)
