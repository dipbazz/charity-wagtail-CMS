from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from wagtail.contrib.search_promotions.models import Query
from wagtail.models import Page

RESULTS_PER_PAGE = 10


def search(request):
    search_query = request.GET.get("query", "").strip()

    if search_query:
        # public() drops pages behind a password, login or group restriction.
        search_results = Page.objects.live().public().search(search_query)
        # Log the query so editors can see what people look for and add promotions.
        Query.get(search_query).add_hit()
    else:
        search_results = Page.objects.none()

    paginator = Paginator(search_results, RESULTS_PER_PAGE)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": paginator.get_page(request.GET.get("page")),
        },
    )
