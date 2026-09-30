import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
)
from wagtail.api import APIField
from wagtail.fields import StreamField
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Orderable, Page, PageManager
from wagtail.query import PageQuerySet
from wagtail.search import index

from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.models import SocialMetaMixin


class CampaignIndexPage(Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    parent_page_types = ["home.HomePage"]
    subpage_types = ["campaigns.CampaignPage"]
    max_count = 1

    campaigns_per_page = 9
    status_filters = {"active": "Open appeals", "closed": "Past appeals"}

    def get_campaigns(self, status=None):
        campaigns = with_card_images(
            CampaignPage.objects.child_of(self).live().order_by("-start_date", "title")
        )
        if status == "active":
            return campaigns.active()
        if status == "closed":
            return campaigns.closed()
        return campaigns

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        status = request.GET.get("status")
        if status not in self.status_filters:
            status = None
        paginator = Paginator(self.get_campaigns(status), self.campaigns_per_page)
        context["campaigns"] = paginator.get_page(request.GET.get("page"))
        context["status"] = status
        context["status_filters"] = self.status_filters
        return context


class CampaignPageQuerySet(PageQuerySet):
    def active(self):
        today = datetime.date.today()
        return self.filter(Q(end_date__isnull=True) | Q(end_date__gte=today))

    def closed(self):
        return self.filter(end_date__lt=datetime.date.today())


CampaignPageManager = PageManager.from_queryset(CampaignPageQuerySet)


class CampaignPage(SocialMetaMixin, Page):
    summary = models.TextField(max_length=300, help_text="Shown on listing cards and in search.")
    hero_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = StreamField(BaseStreamBlock(), blank=True)

    target_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    amount_raised = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    start_date = models.DateField(default=datetime.date.today)
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for ongoing appeals.")

    objects = CampaignPageManager()

    content_panels = Page.content_panels + [
        FieldPanel("summary"),
        FieldPanel("hero_image"),
        FieldPanel("body"),
    ]
    fundraising_panels = [
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("target_amount"), FieldPanel("amount_raised")]),
                FieldRowPanel([FieldPanel("start_date"), FieldPanel("end_date")]),
            ],
            heading="Target and dates",
        ),
        InlinePanel(
            "donation_amounts",
            heading="Suggested donations",
            label="Donation amount",
            max_num=4,
        ),
    ]
    edit_handler = TabbedInterface(
        [
            ObjectList(content_panels, heading="Content"),
            ObjectList(fundraising_panels, heading="Fundraising"),
            ObjectList(SocialMetaMixin.promote_panels, heading="Promote"),
            ObjectList(Page.settings_panels, heading="Settings"),
        ]
    )

    parent_page_types = ["campaigns.CampaignIndexPage"]
    subpage_types = []

    preview_modes = [("", "Full page"), ("card", "Listing card")]

    search_fields = Page.search_fields + [
        index.SearchField("summary"),
        index.SearchField("body"),
        index.FilterField("end_date"),
    ]

    api_fields = [
        APIField("summary"),
        APIField("hero_image", serializer=ImageRenditionField("fill-800x450")),
        APIField("body"),
        APIField("target_amount"),
        APIField("amount_raised"),
        APIField("progress_percent"),
        APIField("start_date"),
        APIField("end_date"),
        APIField("is_active"),
        APIField("donation_amounts"),
    ]

    @property
    def progress_percent(self):
        if not self.target_amount:
            return 0
        return min(int(self.amount_raised / self.target_amount * 100), 100)

    @property
    def is_active(self):
        return self.end_date is None or self.end_date >= datetime.date.today()

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date must be after the start date."})

    def get_preview_template(self, request, mode_name):
        if mode_name == "card":
            return "campaigns/previews/campaign_card.html"
        return super().get_preview_template(request, mode_name)


class DonationAmount(Orderable):
    """A suggested gift and what it pays for, e.g. £10 = clean water for one person."""

    page = ParentalKey(CampaignPage, on_delete=models.CASCADE, related_name="donation_amounts")
    amount = models.PositiveIntegerField(help_text="In pounds.")
    impact = models.CharField(max_length=255)

    panels = [FieldPanel("amount"), FieldPanel("impact")]
    api_fields = [APIField("amount"), APIField("impact")]

    def __str__(self):
        return f"£{self.amount}: {self.impact}"
