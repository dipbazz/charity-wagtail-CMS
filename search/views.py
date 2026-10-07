from django.core.paginator import Paginator
from django.db.models import Q
from django.template.response import TemplateResponse
from wagtail.contrib.search_promotions.models import Query, SearchPromotion
from wagtail.models import Locale, Page

RESULTS_PER_PAGE = 10


def search(request):
    search_query = request.GET.get("query", "").strip()
    # Results and promotions are in the language being read: /ne/search/ finds Nepali pages (#119).
    locale = Locale.get_active()

    if search_query:
        # public() drops pages behind a password, login or group restriction.
        search_results = Page.objects.live().public().filter(locale=locale).search(search_query)
        # Log the query so editors can see what people look for and add promotions.
        query = Query.get(search_query)
        query.add_hit()
        # Editors promote a page in each language for the same query; external links show in both.
        promotions = query.editors_picks.filter(
            Q(page__isnull=True) | Q(page__locale=locale)
        ).select_related("page")
    else:
        search_results = Page.objects.none()
        promotions = SearchPromotion.objects.none()

    paginator = Paginator(search_results, RESULTS_PER_PAGE)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": paginator.get_page(request.GET.get("page")),
            "promotions": promotions,
        },
    )
