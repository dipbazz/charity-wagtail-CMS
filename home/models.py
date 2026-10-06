from django.conf import settings
from django.db import models
from django.http import Http404
from django.utils import translation
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.fields import StreamField
from wagtail.models import Page, Site
from wagtail.search import index

from campaigns.models import CampaignPage
from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.models import SocialMetaMixin


class HomePage(SocialMetaMixin, Page):
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

    def route(self, request, path_components):
        # Wagtail starts routing at the home page in the language being read, but falls back to
        # the main language's when that language has no live home page: /ne/news/ would serve the
        # English news page marked as Nepali. A language without its own home page has no pages
        # here; core.middleware.URLLocaleMiddleware then redirects to the main language's page.
        # The site root paths are cached, so this check costs no query.
        language = get_supported_content_language_variant(
            translation.get_language() or settings.LANGUAGE_CODE
        )
        if not any(
            root.root_path == self.url_path and root.language_code == language
            for root in Site.get_site_root_paths()
        ):
            raise Http404
        return super().route(request, path_components)

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["featured_campaigns"] = with_card_images(
            CampaignPage.objects.live()
            .public()
            .active()
            .filter(locale_id=self.locale_id)
            .order_by("-start_date")
        )[:3]
        return context


class StandardPage(SocialMetaMixin, Page):
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
