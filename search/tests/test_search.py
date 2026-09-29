import pytest
from wagtail.contrib.search_promotions.models import Query, SearchPromotion
from wagtail.models import PageViewRestriction

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from home.models import StandardPage
from news.tests.factories import NewsIndexPageFactory, NewsPageFactory

pytestmark = pytest.mark.django_db


def search(client, query, **params):
    return client.get("/search/", {"query": query, **params})


def result_titles(response):
    return [result.title for result in response.context["search_results"]]


@pytest.fixture
def campaign_index(home_page):
    return CampaignIndexPageFactory(parent=home_page)


@pytest.fixture
def news_index(home_page):
    return NewsIndexPageFactory(parent=home_page)


def test_empty_query_returns_no_results(client, home_page):
    response = search(client, "")

    assert response.status_code == 200
    assert result_titles(response) == []


def test_finds_campaigns_by_summary(client, campaign_index):
    CampaignPageFactory(
        parent=campaign_index, title="Winter appeal", summary="Blankets for refugees"
    )

    assert result_titles(search(client, "blankets")) == ["Winter appeal"]


def test_finds_news_by_streamfield_body(client, news_index):
    NewsPageFactory(
        parent=news_index,
        title="Field update",
        body=[("paragraph", "<p>The borehole reached fresh groundwater.</p>")],
    )

    assert result_titles(search(client, "borehole")) == ["Field update"]


def test_finds_standard_pages_by_introduction(client, home_page):
    home_page.add_child(instance=StandardPage(title="Safeguarding", introduction="Our policy"))

    assert result_titles(search(client, "policy")) == ["Safeguarding"]


def test_excludes_unpublished_pages(client, campaign_index):
    CampaignPageFactory(parent=campaign_index, title="Secret appeal", live=False)

    assert result_titles(search(client, "secret")) == []


def test_excludes_password_protected_pages(client, home_page):
    page = StandardPage(title="Trustee papers", introduction="Board minutes")
    home_page.add_child(instance=page)
    PageViewRestriction.objects.create(
        page=page, restriction_type=PageViewRestriction.PASSWORD, password="trustees"
    )

    assert result_titles(search(client, "minutes")) == []


def test_logs_each_query_for_editors(client, home_page):
    search(client, "Volunteer")
    search(client, "volunteer ")

    assert Query.get("volunteer").hits == 2


def test_shows_editor_promoted_results_first(client, home_page):
    donate = StandardPage(title="Donate", introduction="Give today")
    home_page.add_child(instance=donate)
    SearchPromotion.objects.create(
        query=Query.get("gift aid"), page=donate, description="Add 25% to your gift"
    )

    response = search(client, "gift aid")

    html = response.content.decode()
    assert "Add 25% to your gift" in html
    assert html.index("Add 25% to your gift") < html.index("search-results")


def test_paginated_links_keep_the_query(client, campaign_index):
    for n in range(11):
        CampaignPageFactory(parent=campaign_index, summary="Clean water project")

    response = search(client, "water")

    assert len(response.context["search_results"]) == 10
    assert "query=water&amp;page=2" in response.content.decode()


def test_header_contains_a_search_form(client, home_page):
    html = client.get("/").content.decode()

    assert 'role="search"' in html
    assert 'action="/search/"' in html
