import datetime

import pytest
from django.urls import reverse
from wagtail.snippets.models import get_snippet_models
from wagtail.test.utils.form_data import nested_form_data, streamfield

from news.models import NewsCategory, NewsIndexPage, NewsPage
from news.tests.factories import NewsCategoryFactory, NewsIndexPageFactory, NewsPageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def news_index(home_page):
    return NewsIndexPageFactory(parent=home_page)


def publish_story(parent, tags=(), categories=(), **kwargs):
    story = NewsPageFactory(parent=parent, **kwargs)
    story.tags.add(*tags)
    story.categories.set(categories)
    story.save_revision().publish()
    return story


def titles(response):
    return [story.title for story in response.context["stories"]]


class TestPageTreeRules:
    def test_news_index_lives_under_home(self, home_page):
        assert NewsIndexPage.can_create_at(home_page)

    def test_news_pages_live_only_under_the_news_index(self, home_page, news_index):
        assert NewsPage.can_create_at(news_index)
        assert not NewsPage.can_create_at(home_page)


class TestNewsIndex:
    def test_lists_live_stories_newest_first(self, client, news_index):
        today = datetime.date.today()
        NewsPageFactory(parent=news_index, title="Older", date=today - datetime.timedelta(days=5))
        NewsPageFactory(parent=news_index, title="Newer", date=today)
        NewsPageFactory(parent=news_index, title="Unpublished", live=False)

        response = client.get(news_index.url)

        assert titles(response) == ["Newer", "Older"]

    def test_filters_by_tag(self, client, news_index):
        publish_story(news_index, title="Well opens", tags=["water"])
        publish_story(news_index, title="School rebuilt", tags=["education"])

        response = client.get(news_index.url + "tag/water/")

        assert response.status_code == 200
        assert titles(response) == ["Well opens"]
        assert response.context["active_filter"] == "water"

    def test_filters_by_category(self, client, news_index):
        stories = NewsCategoryFactory(name="Stories", slug="stories")
        press = NewsCategoryFactory(name="Press releases", slug="press")
        publish_story(news_index, title="Grace's story", categories=[stories])
        publish_story(news_index, title="Annual results", categories=[press])

        response = client.get(news_index.url + "category/stories/")

        assert titles(response) == ["Grace's story"]
        assert response.context["active_filter"] == "Stories"

    def test_unknown_category_is_a_404(self, client, news_index):
        assert client.get(news_index.url + "category/nope/").status_code == 404

    def test_rss_feed_lists_latest_stories(self, client, news_index):
        publish_story(news_index, title="Well opens in Kisumu", introduction="A big day.")

        response = client.get(news_index.url + "feed/")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/rss+xml")
        body = response.content.decode()
        assert "Well opens in Kisumu" in body
        assert "A big day." in body


class TestNewsPage:
    def test_links_tags_and_categories_to_filtered_listings(self, client, news_index):
        category = NewsCategoryFactory(name="Stories", slug="stories")
        story = publish_story(news_index, title="Well opens", tags=["water"], categories=[category])

        html = client.get(story.url).content.decode()

        assert f'href="{news_index.url}tag/water/"' in html
        assert f'href="{news_index.url}category/stories/"' in html

    def test_editor_can_create_a_story_with_tags_and_categories(self, admin_client, news_index):
        category = NewsCategoryFactory(name="Stories", slug="stories")
        url = reverse("wagtailadmin_pages:add", args=("news", "newspage", news_index.pk))
        data = nested_form_data(
            {
                "title": "Volunteers of the year",
                "slug": "volunteers-of-the-year",
                "date": datetime.date.today().isoformat(),
                "introduction": "Celebrating our volunteers.",
                "body": streamfield([]),
                "tags": "volunteering, awards",
                "action-publish": "publish",
            }
        )
        # A multi-select posts repeated keys; nested_form_data would flatten a list to indexes.
        data["categories"] = [category.pk]

        response = admin_client.post(url, data)

        assert response.status_code == 302
        story = NewsPage.objects.get(slug="volunteers-of-the-year")
        assert sorted(story.tags.names()) == ["awards", "volunteering"]
        assert list(story.categories.all()) == [category]


def test_news_category_is_a_snippet():
    assert NewsCategory in get_snippet_models()
