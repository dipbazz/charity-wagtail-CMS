import datetime

import factory
from factory.django import DjangoModelFactory
from wagtail_factories import PageFactory

from news.models import NewsCategory, NewsIndexPage, NewsPage


class NewsIndexPageFactory(PageFactory):
    title = "News"
    slug = "news"

    class Meta:
        model = NewsIndexPage


class NewsPageFactory(PageFactory):
    title = factory.Sequence(lambda n: f"News story {n}")
    date = factory.LazyFunction(datetime.date.today)
    introduction = "An update from the field."

    class Meta:
        model = NewsPage


class NewsCategoryFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")

    class Meta:
        model = NewsCategory
