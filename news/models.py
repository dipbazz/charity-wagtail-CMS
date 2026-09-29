import datetime

from django import forms
from django.contrib.syndication.views import Feed
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import get_object_or_404
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from core.blocks import BaseStreamBlock


class NewsCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    panels = [FieldPanel("name"), FieldPanel("slug")]

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "news categories"

    def __str__(self):
        return self.name


class NewsFeed(Feed):
    def __init__(self, index_page, request):
        super().__init__()
        self.index_page = index_page
        self.request = request

    def title(self):
        return self.index_page.title

    def link(self):
        return self.index_page.get_full_url(self.request)

    def description(self):
        return self.index_page.introduction

    def items(self):
        return self.index_page.get_stories()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.introduction

    def item_link(self, item):
        return item.get_full_url(self.request)

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class NewsIndexPage(RoutablePageMixin, Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    parent_page_types = ["home.HomePage"]
    subpage_types = ["news.NewsPage"]
    max_count = 1

    stories_per_page = 10

    def get_stories(self):
        return (
            NewsPage.objects.child_of(self)
            .live()
            .select_related("hero_image")
            .prefetch_related("tags", "categories")
            .order_by("-date", "-pk")
        )

    def render_listing(self, request, stories, active_filter=None):
        paginator = Paginator(stories, self.stories_per_page)
        return self.render(
            request,
            context_overrides={
                "stories": paginator.get_page(request.GET.get("page")),
                "active_filter": active_filter,
                "categories": NewsCategory.objects.all(),
            },
        )

    @path("")
    def all_stories(self, request):
        return self.render_listing(request, self.get_stories())

    @path("tag/<str:tag>/", name="tag")
    def stories_by_tag(self, request, tag):
        return self.render_listing(request, self.get_stories().filter(tags__slug=tag), tag)

    @path("category/<slug:category>/", name="category")
    def stories_by_category(self, request, category):
        category = get_object_or_404(NewsCategory, slug=category)
        stories = self.get_stories().filter(categories=category)
        return self.render_listing(request, stories, category.name)

    @path("feed/", name="feed")
    def feed(self, request):
        return NewsFeed(self, request)(request)


class NewsPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "news.NewsPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class NewsPage(Page):
    date = models.DateField("Post date", default=datetime.date.today)
    introduction = models.TextField(max_length=300)
    hero_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = StreamField(BaseStreamBlock(), blank=True)
    tags = ClusterTaggableManager(through=NewsPageTag, blank=True)
    categories = ParentalManyToManyField(NewsCategory, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("introduction"),
        FieldPanel("hero_image"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("tags"), FieldPanel("categories", widget=forms.CheckboxSelectMultiple)],
            heading="Tags and categories",
        ),
    ]

    parent_page_types = ["news.NewsIndexPage"]
    subpage_types = []

    search_fields = Page.search_fields + [
        index.SearchField("introduction"),
        index.SearchField("body"),
        index.RelatedFields("tags", [index.SearchField("name")]),
        index.FilterField("date"),
    ]

    @property
    def news_index(self):
        return self.get_parent().specific
