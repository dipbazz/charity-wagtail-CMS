import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.template.response import TemplateResponse
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
from wagtail.contrib.forms.models import AbstractForm
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Orderable, Page, PageManager
from wagtail.query import PageQuerySet
from wagtail.search import index

from campaigns.forms import PledgeForm
from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.models import SiteSettings, SocialMetaMixin


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


class DonatePage(SocialMetaMixin, AbstractForm):
    """The page every Donate button leads to: suggested amounts and a pledge form.

    The form's fields are fixed (`campaigns.forms.PledgeForm`), not built by editors, but pledges
    are saved as form submissions, so they're listed in the admin and export to CSV.
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

    content_panels = AbstractForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("introduction"),
        InlinePanel("donation_amounts", heading="Suggested amounts", label="Amount", max_num=6),
        FieldPanel("payment_notice"),
        FieldPanel("body"),
        FieldPanel("thank_you_text"),
    ]
    promote_panels = SocialMetaMixin.promote_panels

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    data_fields = [
        ("submit_time", "Submission date"),
        ("amount", "Amount"),
        ("currency", "Currency"),
        ("frequency", "Frequency"),
        ("name", "Name"),
        ("email", "Email"),
        ("phone", "Mobile number"),
        ("appeal", "Appeal"),
        ("address", "Address"),
        ("postcode", "Postcode or postal code"),
    ]

    def get_appeals(self):
        return CampaignPage.objects.live().public().active().order_by("title")

    def get_form_fields(self):
        return []

    def get_data_fields(self):
        return self.data_fields

    def get_form_class(self):
        return PledgeForm

    def get_form(self, *args, request=None, **kwargs):
        if request is None:  # the admin preview
            site_settings = SiteSettings.for_site(self.get_site())
        else:
            site_settings = SiteSettings.for_request(request)
        return PledgeForm(
            *args,
            amounts=self.donation_amounts.all(),
            appeals=self.get_appeals(),
            currency=site_settings.currency,
            phone_country=site_settings.phone_country,
            **kwargs,
        )

    def serve(self, request, *args, **kwargs):
        if request.method == "POST":
            form = self.get_form(request.POST, request=request, page=self, user=request.user)
            if form.is_valid():
                submission = self.process_form_submission(form)
                return self.render_landing_page(request, submission, *args, **kwargs)
        else:
            form = self.get_form(request=request, link=request.GET, page=self, user=request.user)

        context = self.get_context(request)
        context["form"] = form
        return TemplateResponse(request, self.get_template(request), context)

    def process_form_submission(self, form):
        return self.get_submission_class().objects.create(form_data=form.pledge_data(), page=self)

    def get_appeals_page(self):
        return CampaignIndexPage.objects.live().public().first()

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # Only the thank-you page shows it; templates call a method only if they use it.
        context["appeals_page"] = self.get_appeals_page
        return context


class DonatePageAmount(AbstractDonationAmount):
    page = ParentalKey(DonatePage, on_delete=models.CASCADE, related_name="donation_amounts")
