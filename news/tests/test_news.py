import datetime
import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from wagtail.models import PageViewRestriction
from wagtail.snippets.models import get_snippet_models
from wagtail.test.utils.form_data import nested_form_data, streamfield
from wagtail_factories import ImageFactory

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

    def test_cards_offer_small_modern_images_that_load_lazily(self, client, news_index):
        NewsPageFactory(
            parent=news_index, hero_image=ImageFactory(file__width=1600, file__height=900)
        )

        html = BeautifulSoup(client.get(news_index.url).content, "html.parser")

        img = html.select_one(".news-card picture img")
        # The <img> keeps its full size, so it fills the card; the browser picks a smaller file.
        assert (img["width"], img["height"]) == ("640", "360")
        assert img["loading"] == "lazy"

    def test_card_images_add_no_query_per_card(self, cold_cache_queries, news_index):
        NewsPageFactory(parent=news_index, hero_image=ImageFactory())
        with_one_card = cold_cache_queries(news_index.url)
        for _ in range(2):
            NewsPageFactory(parent=news_index, hero_image=ImageFactory())

        assert cold_cache_queries(news_index.url) == with_one_card


class TestPrivateStories:
    """A story behind a password or a login is held back, so no public list may give it away.

    Feed readers keep their own copy, so a title that reaches the feed can't be taken back.
    """

    @pytest.fixture
    def private_story(self, news_index):
        stories = NewsCategoryFactory(name="Stories", slug="stories")
        publish_story(news_index, title="Public story", tags=["water"], categories=[stories])
        return publish_story(
            news_index,
            title="Embargoed story",
            introduction="Waiting for consent.",
            tags=["water"],
            categories=[stories],
        )

    @pytest.mark.parametrize(
        "restriction_type", [PageViewRestriction.PASSWORD, PageViewRestriction.LOGIN]
    )
    @pytest.mark.parametrize("listing", ["", "tag/water/", "category/stories/", "feed/"])
    def test_is_left_out_of_every_listing_and_the_feed(
        self, client, news_index, private_story, restriction_type, listing
    ):
        PageViewRestriction.objects.create(
            page=private_story, restriction_type=restriction_type, password="trustees"
        )

        body = client.get(news_index.url + listing).content.decode()

        assert "Public story" in body
        assert "Embargoed story" not in body
        assert "Waiting for consent." not in body


class TestFollowNews:
    """Visitors copy the feed address into a news reader rather than opening raw XML."""

    def test_offers_the_full_feed_address_to_copy(self, client, news_index):
        html = client.get(news_index.url).content.decode()

        assert "Follow our news" in html
        assert 'value="http://testserver/news/feed/"' in html
        assert "Copy link" in html

    def test_no_visible_link_opens_the_raw_feed(self, client, news_index):
        html = client.get(news_index.url).content.decode()

        assert not re.search(r'<a [^>]*href="[^"]*/feed/"', html)

    def test_feed_readers_can_still_discover_the_feed(self, client, news_index):
        html = client.get(news_index.url).content.decode()

        assert '<link rel="alternate" type="application/rss+xml"' in html


class TestNewsPage:
    def test_main_photo_comes_in_modern_formats_and_is_not_lazy(self, client, news_index):
        photo = ImageFactory(file__width=1600, file__height=1200, credit="Photo: Amara Okafor")
        story = publish_story(news_index, hero_image=photo)

        html = BeautifulSoup(client.get(story.url).content, "html.parser")

        picture = html.select_one("article figure picture")
        assert [source["type"] for source in picture.find_all("source")] == [
            "image/avif",
            "image/webp",
        ]
        assert "loading" not in picture.img.attrs
        assert "Photo: Amara Okafor" in html.select_one("article figcaption").text

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
