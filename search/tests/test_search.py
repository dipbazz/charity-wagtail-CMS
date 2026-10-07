import pytest
from wagtail.contrib.search_promotions.models import Query, SearchPromotion
from wagtail.models import PageViewRestriction

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from home.models import StandardPage
from news.tests.factories import NewsIndexPageFactory, NewsPageFactory

pytestmark = pytest.mark.django_db


def search(client, query, path="/search/", **params):
    return client.get(path, {"query": query, **params})


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
    CampaignPageFactory.create_batch(11, parent=campaign_index, summary="Clean water project")

    response = search(client, "water")

    assert len(response.context["search_results"]) == 10
    assert "query=water&amp;page=2" in response.content.decode()


def test_header_contains_a_search_form(client, home_page):
    html = client.get("/").content.decode()

    assert 'role="search"' in html
    assert 'action="/search/"' in html


@pytest.fixture
def nepali_news_index(news_index, nepali_home_page):
    translation = news_index.copy_for_translation(nepali_home_page.locale)
    translation.title = "समाचार"
    translation.save_revision().publish()
    return translation


def test_finds_nepali_pages_by_a_word_with_conjuncts_and_vowel_signs(client, nepali_news_index):
    # सम्पन्न has a conjunct (म्प) and a virama; पुनर्निर्माण has vowel signs above and below.
    NewsPageFactory(
        parent=nepali_news_index,
        title="धारा मर्मत सम्पन्न",
        slug="tap-repaired",
        body=[("paragraph", "<p>बाढीपछि गाउँको पानी प्रणालीको पुनर्निर्माण भयो।</p>")],
    )

    assert result_titles(search(client, "सम्पन्न", path="/ne/search/")) == ["धारा मर्मत सम्पन्न"]
    assert result_titles(search(client, "पुनर्निर्माण", path="/ne/search/")) == ["धारा मर्मत सम्पन्न"]


@pytest.fixture
def jhapa_story(news_index, nepali_news_index):
    """A story in English and Nepali that both mention Jhapa in English letters."""
    english = NewsPageFactory(parent=news_index, title="Wells for Jhapa", slug="jhapa")
    nepali = english.copy_for_translation(nepali_news_index.locale)
    nepali.title = "Jhapa का लागि इनार"
    nepali.save_revision().publish()
    return english, nepali


def test_lists_only_pages_in_the_language_being_read(client, jhapa_story):
    assert result_titles(search(client, "jhapa")) == ["Wells for Jhapa"]
    assert result_titles(search(client, "jhapa", path="/ne/search/")) == ["Jhapa का लागि इनार"]


def test_promotes_only_pages_in_the_language_being_read(client, jhapa_story):
    english, nepali = jhapa_story
    query = Query.get("jhapa")
    SearchPromotion.objects.create(query=query, page=english, description="Read in English")
    SearchPromotion.objects.create(query=query, page=nepali, description="नेपालीमा पढ्नुहोस्")

    english_html = search(client, "jhapa").content.decode()
    nepali_html = search(client, "jhapa", path="/ne/search/").content.decode()

    assert "Read in English" in english_html and "नेपालीमा पढ्नुहोस्" not in english_html
    assert "नेपालीमा पढ्नुहोस्" in nepali_html and "Read in English" not in nepali_html


def test_promoted_external_links_show_in_every_language(client, home_page, nepali_home_page):
    SearchPromotion.objects.create(
        query=Query.get("report"),
        external_link_url="https://example.org/annual-report.pdf",
        external_link_text="Annual report",
    )

    assert "Annual report" in search(client, "report").content.decode()
    assert "Annual report" in search(client, "report", path="/ne/search/").content.decode()
