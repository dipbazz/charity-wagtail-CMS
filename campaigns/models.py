import datetime
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.http import HttpResponseRedirect
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
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import RichTextField, StreamField
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Orderable, Page, PageManager
from wagtail.query import PageQuerySet
from wagtail.search import index

from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.models import SiteSettings, SocialMetaMixin
from core.money import CURRENCY_CHOICES, format_money


class CampaignIndexPage(Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    parent_page_types = ["home.HomePage"]
    subpage_types = ["campaigns.CampaignPage"]
    # One per home page, so one per language.
    max_count_per_parent = 1

    campaigns_per_page = 9
    status_filters = {"active": "Open appeals", "closed": "Past appeals"}

    def get_campaigns(self, status=None):
        campaigns = with_card_images(
            CampaignPage.objects.child_of(self).live().public().order_by("-start_date", "title")
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


class AbstractDonationAmount(Orderable):
    """A suggested gift and what it pays for, e.g. 1,500 = clean water for one person."""

    amount = models.PositiveIntegerField(help_text="A whole amount in the site's currency.")
    impact = models.CharField(max_length=255)

    panels = [FieldPanel("amount"), FieldPanel("impact")]
    api_fields = [APIField("amount"), APIField("impact")]

    class Meta(Orderable.Meta):
        abstract = True

    def __str__(self):
        return f"{self.amount:,}: {self.impact}"


class DonationAmount(AbstractDonationAmount):
    page = ParentalKey(CampaignPage, on_delete=models.CASCADE, related_name="donation_amounts")


DEFAULT_PAYMENT_NOTICE = (
    "<p>No payment is taken on this website yet. Send this form and we'll contact you about how "
    "to pay. If you choose monthly, we'll help you set up a regular payment.</p>"
)


class DonatePage(RoutablePageMixin, SocialMetaMixin, Page):
    """The page every Donate button leads to: suggested amounts and a pledge form.

    Each pledge it takes is saved as a `Pledge`, listed under Pledges in the admin. The form
    then redirects to its own thank-you page, so reloading that page can't send it again.
    """

    introduction = models.TextField(blank=True)
    payment_notice = RichTextField(
        default=DEFAULT_PAYMENT_NOTICE,
        help_text="Shown above the form: say plainly how payment works and what happens next.",
    )
    body = StreamField(
        BaseStreamBlock(),
        blank=True,
        help_text="Shown below the form, e.g. a table of where the money goes.",
    )
    thank_you_text = RichTextField(blank=True, help_text="Shown after someone sends the form.")

    content_panels = Page.content_panels + [
        FieldPanel("introduction"),
        InlinePanel("donation_amounts", heading="Suggested amounts", label="Amount", max_num=6),
        FieldPanel("payment_notice"),
        FieldPanel("body"),
        FieldPanel("thank_you_text"),
    ]
    promote_panels = SocialMetaMixin.promote_panels

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    # One per home page, so one per language.
    max_count_per_parent = 1

    landing_page_template = "campaigns/donate_page_landing.html"
    preview_modes = [("", "Donate page"), ("thank-you", "Thank-you page")]

    def get_appeals(self):
        return (
            CampaignPage.objects.live()
            .public()
            .active()
            .filter(locale_id=self.locale_id)
            .order_by("title")
        )

    def get_form(self, *args, site_settings, **kwargs):
        from campaigns.forms import PledgeForm  # forms imports this module's Pledge

        return PledgeForm(
            *args,
            page=self,
            currency=site_settings.currency,
            phone_country=site_settings.phone_country,
            **kwargs,
        )

    @path("")
    def pledge_form(self, request):
        site_settings = SiteSettings.for_request(request)
        if request.method == "POST":
            form = self.get_form(request.POST, site_settings=site_settings)
            if form.is_valid():
                form.save()
                # 303 See Other: the browser fetches the thank-you page with GET, so reloading
                # it doesn't send the form again.
                thank_you = self.get_url(request) + self.reverse_subpage("thank_you")
                return HttpResponseRedirect(thank_you, status=303)
        else:
            form = self.get_form(site_settings=site_settings, link=request.GET)
        return self.render(request, context_overrides={"form": form})

    @path("thank-you/", name="thank_you")
    def thank_you(self, request):
        return self.render(request, template=self.landing_page_template)

    def serve_preview(self, request, mode_name):
        if mode_name == "thank-you":
            return self.thank_you(request)
        return super().serve_preview(request, mode_name)

    def get_appeals_page(self):
        return CampaignIndexPage.objects.live().public().filter(locale_id=self.locale_id).first()

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # Only the thank-you page shows it; templates call a method only if they use it.
        context["appeals_page"] = self.get_appeals_page
        return context


class DonatePageAmount(AbstractDonationAmount):
    page = ParentalKey(DonatePage, on_delete=models.CASCADE, related_name="donation_amounts")


class Frequency(models.TextChoices):
    """How often a supporter gives. Shared by pledges, the pledge form and anything that acts on
    them (such as monthly reminders), so compare with Frequency.MONTHLY, never the string."""

    ONE_OFF = "one-off", "One-off"
    MONTHLY = "monthly", "Monthly"


class Pledge(models.Model):
    """A supporter's promise to give, sent from the Donate page. No payment is taken yet."""

    page = models.ForeignKey(
        DonatePage, null=True, on_delete=models.SET_NULL, related_name="pledges"
    )
    appeal = models.ForeignKey(
        CampaignPage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pledges",
        help_text="Blank means wherever it's needed most.",
    )
    amount = models.PositiveIntegerField(help_text="A whole amount in the pledge's currency.")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    frequency = models.CharField(
        "how often", max_length=7, choices=Frequency, default=Frequency.ONE_OFF
    )
    name = models.CharField(max_length=255)
    email = models.EmailField("email address")
    phone = models.CharField(
        "mobile number",
        max_length=16,
        blank=True,
        help_text="In international form (+9779841234567). Monthly pledges only, for the reminder.",
    )
    address = models.TextField(
        blank=True,
        help_text="House or ward number, street or tole, town or municipality, district.",
    )
    postcode = models.CharField("postcode or postal code", max_length=12, blank=True)
    message = models.TextField(
        max_length=1000, blank=True, help_text="For the team only; never shown on the site."
    )
    # Consents, both opt-in. The pledge form's help texts are what the supporter agreed to.
    email_updates = models.BooleanField(
        default=False, help_text="Agreed to emails about our projects and appeals."
    )
    show_on_website = models.BooleanField(
        default=False,
        help_text="Agreed to their name, amount, appeal and date being listed once received.",
    )
    created_at = models.DateTimeField("sent", auto_now_add=True)
    # The one-time ID of the copy of the form it was sent from. Sending that copy again (after
    # going back from the thank-you page) updates this pledge instead of adding another.
    submission_id = models.UUIDField(null=True, unique=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.display_amount()} {self.get_frequency_display().lower()}"

    @admin.display(description="Amount")
    def display_amount(self):
        return format_money(self.amount, self.currency)
