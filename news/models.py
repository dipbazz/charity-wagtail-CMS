import datetime

from django import forms
from django.contrib.syndication.views import Feed
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.http import Http404
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import StreamField
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Page, TranslatableMixin
from wagtail.search import index

from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.languages import in_reading_language
from core.models import SocialMetaMixin


class NewsCategory(TranslatableMixin, models.Model):
    name = models.CharField(max_length=100)
    # Unique in each language: a translation keeps the slug, so a category's address differs
    # between languages only by the prefix, as a page's does.
    slug = models.SlugField()

    panels = [FieldPanel("name"), FieldPanel("slug")]

    class Meta(TranslatableMixin.Meta):
        ordering = ["name"]
        verbose_name_plural = "news categories"
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "locale"], name="unique_category_slug_per_language"
            )
        ]

    def __str__(self):
        return self.name

    def validate_constraints(self, exclude=None):
        """Checks the slug is unique in its language, which the admin's form leaves to the
        database because the form has no locale field."""
        super().validate_constraints(exclude)
        if exclude and "slug" in exclude:
            return
        duplicates = NewsCategory.objects.filter(slug=self.slug, locale_id=self.locale_id)
        if self.locale_id and duplicates.exclude(pk=self.pk).exists():
            raise ValidationError(
                {"slug": "Another category in this language already has this slug."}
            )


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
    # One per home page, so one per language.
    max_count_per_parent = 1

    stories_per_page = 10

    def get_stories(self):
        return (
            NewsPage.objects.child_of(self)
            .live()
            .public()
            .prefetch_related("tags", "categories")
            .order_by("-date", "-pk")
        )

    def render_listing(self, request, stories, active_filter=None, active_category=None):
        paginator = Paginator(with_card_images(stories), self.stories_per_page)
        return self.render(
            request,
            context_overrides={
                "stories": paginator.get_page(request.GET.get("page")),
                "active_filter": active_filter,
                "active_category": active_category,
                "categories": in_reading_language(NewsCategory.objects.all()),
                "feed_url": request.build_absolute_uri(
                    self.get_url(request) + self.reverse_subpage("feed")
                ),
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
        # Stories in this language may have either language's version of the category.
        category = next(iter(in_reading_language(NewsCategory.objects.filter(slug=category))), None)
        if category is None:
            raise Http404
        stories = (
            self.get_stories()
            .filter(categories__translation_key=category.translation_key)
            .distinct()
        )
        return self.render_listing(request, stories, category.name, category)

    @path("feed/", name="feed")
    def feed(self, request):
        return NewsFeed(self, request)(request)


class NewsPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "news.NewsPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class NewsPage(SocialMetaMixin, Page):
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

    api_fields = [
        APIField("date"),
        APIField("introduction"),
        APIField("hero_image", serializer=ImageRenditionField("fill-800x450")),
        APIField("body"),
        APIField("tags"),
        APIField("category_names"),
    ]

    def get_categories(self):
        """The story's categories in the language being read, else in the main language.

        A translated story keeps the categories chosen for the original, so each is looked up by
        its translation key (#117).
        """
        return in_reading_language(
            NewsCategory.objects.filter(
                translation_key__in=self.categories.all().values("translation_key")
            )
        )

    @property
    def category_names(self):
        return [category.name for category in self.categories.all()]

    @property
    def news_index(self):
        return self.get_parent().specific
