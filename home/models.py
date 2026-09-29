from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from campaigns.models import CampaignPage
from core.blocks import BaseStreamBlock


class HomePage(Page):
    hero_heading = models.CharField(max_length=255, blank=True)
    hero_text = models.TextField(blank=True)
    hero_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_cta_text = models.CharField("Hero button text", max_length=50, blank=True)
    hero_cta_page = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Hero button link",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = StreamField(BaseStreamBlock(), blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_heading"),
                FieldPanel("hero_text"),
                FieldPanel("hero_image"),
                FieldPanel("hero_cta_text"),
                FieldPanel("hero_cta_page"),
            ],
            heading="Hero",
        ),
        FieldPanel("body"),
    ]

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["featured_campaigns"] = (
            CampaignPage.objects.live()
            .active()
            .select_related("hero_image")
            .order_by("-start_date")[:3]
        )
        return context


class StandardPage(Page):
    """A general-purpose content page, e.g. About us or Our work."""

    introduction = models.TextField(blank=True)
    body = StreamField(BaseStreamBlock(), blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("introduction"),
        FieldPanel("body"),
    ]

    parent_page_types = ["home.HomePage", "home.StandardPage"]

    search_fields = Page.search_fields + [
        index.SearchField("introduction"),
        index.SearchField("body"),
    ]
