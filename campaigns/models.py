import datetime
import logging
import re
import uuid
from decimal import Decimal

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
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

from campaigns.payments import method_choices, provider_for, providers_for
from core.blocks import BaseStreamBlock
from core.images import with_card_images
from core.models import SiteSettings, SocialMetaMixin
from core.money import CURRENCY_CHOICES, format_money
from nepal_payments import PaymentError, PaymentRequest

logger = logging.getLogger(__name__)


class CampaignIndexPage(Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    parent_page_types = ["home.HomePage"]
    subpage_types = ["campaigns.CampaignPage"]
    # One per home page, so one per language.
    max_count_per_parent = 1

    campaigns_per_page = 9
    status_filters = {
        "active": gettext_lazy("Open appeals"),
        "closed": gettext_lazy("Past appeals"),
    }

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


# What asking a provider just now found, for the pay page to say once: a message with this tag.
# Messages are shared with the admin, so the pay page takes only its own.
PAYMENT_MESSAGE = "payment"


def tell_pay_page(request, result):
    """Leave the pay page a one-off result: "checked" (the provider hasn't confirmed the payment
    yet), "unreachable" (it couldn't be asked) or "not-started" (it couldn't start one)."""
    messages.info(request, result, extra_tags=PAYMENT_MESSAGE)


def pay_page_result(request):
    """The result tell_pay_page() left, if any. Any other message is kept for the page it's for."""
    result = None
    others = []
    for message in messages.get_messages(request):
        if PAYMENT_MESSAGE in (message.extra_tags or "").split():
            result = message.message
        else:
            others.append(message)
    for message in others:
        messages.add_message(request, message.level, message.message, message.extra_tags)
    return result


def either(names):
    """The names as a choice, in the reader's language: "eSewa or Khalti", "eSewa, Khalti or
    IME Pay"."""
    if len(names) < 2:
        return "".join(names)
    return gettext("%(names)s or %(last)s") % {"names": ", ".join(names[:-1]), "last": names[-1]}


class DonatePage(RoutablePageMixin, SocialMetaMixin, Page):
    """The page every Donate button leads to: suggested amounts and a pledge form.

    Each pledge it takes is saved as a `Pledge`, listed under Pledges in the admin. The form
    then redirects to the pledge's pay page when a payment provider here can take it, or to the
    thank-you page, so reloading either can't send the form again.
    """

    introduction = models.TextField(blank=True)
    # The page itself says how paying works on this site (online with the providers set up here,
    # or not online at all), so this is only for what a charity wants to add.
    payment_notice = RichTextField(
        blank=True,
        help_text="Anything to add about paying, such as bank details for a transfer. Shown above "
        "the form, after the page's own sentence on how to pay.",
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
    pay_page_template = "campaigns/donate_page_pay.html"
    redirect_template = "campaigns/donate_page_redirect.html"
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
                pledge = form.save()
                # 303 See Other: the browser fetches the next page with GET, so reloading it
                # doesn't send the form again.
                if providers_for(pledge.currency, Decimal(pledge.amount)):
                    return self.redirect_to(request, "pay", pledge.reference)
                return self.redirect_to(request, "thank_you")
        else:
            form = self.get_form(site_settings=site_settings, link=request.GET)
        providers = providers_for(site_settings.currency)
        return self.render(
            request,
            context_overrides={
                "form": form,
                "pay_with": either([provider.name for provider in providers]),
            },
        )

    @path("thank-you/", name="thank_you")
    def thank_you(self, request):
        return self.render(request, template=self.landing_page_template)

    @path("pay/<uuid:reference>/", name="pay")
    def pay(self, request, reference):
        """A pledge's pay page: the ways to pay it, or what became of paying it. Its address is
        the pledge's own reference, so only the person who sent it has it."""
        pledge = get_object_or_404(
            Pledge.objects.select_related("appeal"), reference=reference, page=self
        )
        payments = list(pledge.payments.all())  # newest first
        received = next((p for p in payments if p.status == PaymentStatus.PAID), None)
        # The pledge says whether it's paid: an attempt for another amount (the pledge changed
        # after it started) doesn't pay it, but the money was still received, and isn't asked for
        # again.
        paid = received if pledge.payment_status == PaymentStatus.PAID else None
        latest = payments[0] if payments else None
        site_settings = SiteSettings.for_request(request)
        providers = [] if received else providers_for(pledge.currency, Decimal(pledge.amount))
        return self.render(
            request,
            template=self.pay_page_template,
            context_overrides={
                "pledge": pledge,
                "paid": paid,
                "received": received,
                # Codes and names, not the classes, which templates would try to call.
                "providers": [(provider.code, provider.name) for provider in providers],
                "latest": latest,
                "unfinished": latest if latest and latest.status == PaymentStatus.WAITING else None,
                "result": pay_page_result(request),
                # The others to try when the latest attempt's provider couldn't start it.
                "others": either([p.name for p in providers if latest and p.code != latest.method]),
                "site_settings": site_settings,
                "phone_link": "tel:" + re.sub(r"[^\d+]", "", site_settings.phone),
            },
        )

    @path("pay/<uuid:reference>/<slug:method>/", name="start_payment")
    def start_payment(self, request, reference, method):
        """Start paying a pledge with a provider, and send the payer there."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        pledge = get_object_or_404(
            Pledge.objects.select_related("appeal"), reference=reference, page=self
        )
        if pledge.payment_status == PaymentStatus.PAID:
            return self.redirect_to(request, "pay", pledge.reference)
        provider = provider_for(method)
        if provider is None or type(provider) not in providers_for(
            pledge.currency, Decimal(pledge.amount)
        ):
            raise Http404("No such payment provider here.")

        payment = pledge.start_payment(method, live=provider.live)
        return_path = self.get_url(request) + self.reverse_subpage(
            "payment_return", args=[payment.reference]
        )
        site_settings = SiteSettings.for_request(request)
        appeal = pledge.appeal.title if pledge.appeal else gettext("Wherever it's needed most")
        try:
            started = provider.start(
                PaymentRequest(
                    reference=str(payment.reference),
                    amount=Decimal(payment.amount),
                    currency=payment.currency,
                    return_url=request.build_absolute_uri(return_path),
                    website_url=request.build_absolute_uri("/"),
                    description=gettext("A gift to %(charity)s: %(appeal)s")
                    % {"charity": site_settings.name, "appeal": appeal},
                )
            )
        except PaymentError as error:
            logger.warning("%s couldn't start payment %s: %s", provider.name, payment, error)
            payment.record(PaymentStatus.FAILED)
            tell_pay_page(request, "not-started")
            return self.redirect_to(request, "pay", pledge.reference)

        redirect = started.redirect
        if redirect.method == "GET":
            if started.provider_id:
                Payment.objects.filter(pk=payment.pk).update(provider_id=started.provider_id)
            return HttpResponseRedirect(redirect.url, status=303)
        # A form to post to the provider: kept, and sent from a page fetched with GET, so Back
        # from the provider reloads that page rather than asking to resend this one.
        Payment.objects.filter(pk=payment.pk).update(
            provider_id=started.provider_id,
            provider_form={"url": redirect.url, "fields": redirect.fields},
        )
        return self.redirect_to(request, "go_to_provider", payment.reference)

    @path("payment/<uuid:reference>/go/", name="go_to_provider")
    def go_to_provider(self, request, reference):
        """The page that sends a payment's form to its provider (eSewa). Once the payment isn't
        waiting any more, the pay page instead: the form would pay again."""
        payment = get_object_or_404(
            Payment.objects.select_related("pledge"), reference=reference, pledge__page=self
        )
        if payment.status != PaymentStatus.WAITING or not payment.provider_form:
            return self.redirect_to(request, "pay", payment.pledge.reference)
        return self.render(
            request,
            template=self.redirect_template,
            context_overrides={
                "provider_name": payment.get_method_display(),
                "form_url": payment.provider_form["url"],
                "fields": payment.provider_form["fields"],
            },
        )

    @path("payment/<uuid:reference>/", name="payment_return")
    def payment_return(self, request, reference):
        """Where a provider sends the payer back, paid or not. Only the provider, asked here,
        says which: what the browser brings back is never read."""
        payment = get_object_or_404(
            Payment.objects.select_related("pledge"), reference=reference, pledge__page=self
        )
        provider = provider_for(payment.method)
        # A provider no longer set up, or set up for the other mode (test or live), can't be
        # asked: its keys are for another system.
        if payment.status != PaymentStatus.PAID and provider and provider.live == payment.live:
            try:
                outcome = provider.check(
                    str(payment.reference), Decimal(payment.amount), payment.provider_id
                )
            except (PaymentError, ValueError) as error:
                logger.warning("%s couldn't check payment %s: %s", provider.name, payment, error)
                tell_pay_page(request, "unreachable")
            else:
                payment.record(outcome.status, outcome.provider_reference)
                if outcome.status == PaymentStatus.WAITING:
                    tell_pay_page(request, "checked")
        return self.redirect_to(request, "pay", payment.pledge.reference)

    def redirect_to(self, request, name, *args):
        """303 to one of this page's routes."""
        url = self.get_url(request) + self.reverse_subpage(name, args=args)
        return HttpResponseRedirect(url, status=303)

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


class PaymentStatus(models.TextChoices):
    """Whether a pledge or a payment has been paid: the payment providers' statuses
    (nepal_payments.Status), with the names the team reads in the admin."""

    WAITING = "waiting", "Waiting"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"


# The statuses a payment may change from, to each status: paid never goes back, and a failed
# attempt may still turn out paid (eSewa sends the payer back to one address, paid or not).
CHANGES_FROM = {
    PaymentStatus.PAID: [PaymentStatus.WAITING, PaymentStatus.FAILED],
    PaymentStatus.FAILED: [PaymentStatus.WAITING],
}


class Pledge(models.Model):
    """A supporter's promise to give, sent from the Donate page, then paid online (a Payment)
    or arranged with the team."""

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
    # Whether it's been paid online (#93): only Payment.record() changes these.
    payment_status = models.CharField(
        "payment", max_length=7, choices=PaymentStatus, default=PaymentStatus.WAITING
    )
    paid_at = models.DateTimeField("paid", null=True, blank=True)
    # The address of its pay page. Not submission_id: whoever holds that can send the form again
    # and change the pledge.
    reference = models.UUIDField(null=True, unique=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.display_amount()} {self.get_frequency_display().lower()}"

    def save(self, *args, **kwargs):
        if self.reference is None:
            self.reference = uuid.uuid4()
        super().save(*args, **kwargs)

    @admin.display(description="Amount")
    def display_amount(self):
        return format_money(self.amount, self.currency)

    @admin.display(description="Payment")
    def payment_display(self):
        """Waiting, paid or failed, with "(test)" after paid when only a provider's test system
        took it: anyone can pay there with the provider's public test account, so it must never
        pass for money received. Reads payments as fetched, so a list can prefetch them."""
        shown = self.get_payment_status_display()
        if self.payment_status != PaymentStatus.PAID:
            return shown
        paid = next((p for p in self.payments.all() if p.status == PaymentStatus.PAID), None)
        return f"{shown} (test)" if paid and not paid.live else shown

    @admin.display(description="Paid with")
    def paid_with(self):
        """The provider and its reference for the payment, e.g. "eSewa 000AWEO", marked "(test)"
        when no money moved. Reads payments as fetched, so a list can prefetch them."""
        paid = next((p for p in self.payments.all() if p.status == PaymentStatus.PAID), None)
        if paid is None:
            return ""
        made = f"{paid.get_method_display()} {paid.provider_reference}".strip()
        return made if paid.live else f"{made} (test)"

    def received_money(self):
        """Whether a payment of it moved real money, not just a provider's test system."""
        return self.payments.filter(status=PaymentStatus.PAID, live=True).exists()

    def start_payment(self, method, live):
        """A new attempt to pay this pledge, with the provider whose code is `method`. After a
        failed attempt, the pledge is waiting for payment again."""
        with transaction.atomic():
            Pledge.objects.filter(pk=self.pk, payment_status=PaymentStatus.FAILED).update(
                payment_status=PaymentStatus.WAITING
            )
            return self.payments.create(
                method=method, amount=self.amount, currency=self.currency, live=live
            )


class Payment(models.Model):
    """One attempt to pay a pledge online, with one provider (nepal_payments). Its status changes
    only through record(), from what the provider says when asked."""

    pledge = models.ForeignKey(Pledge, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField("paid with", max_length=20, choices=method_choices)
    amount = models.PositiveIntegerField(help_text="A whole amount in the payment's currency.")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    status = models.CharField(max_length=7, choices=PaymentStatus, default=PaymentStatus.WAITING)
    # Ours, sent to the provider (eSewa's transaction_uuid, Khalti's purchase_order_id), and the
    # address the payer comes back to.
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider_id = models.CharField(
        max_length=100, blank=True, help_text="The provider's ID for the attempt (Khalti's pidx)."
    )
    # The signed form a provider that takes one (eSewa) is sent, as {"url", "fields"}: the page
    # that sends it is fetched afterwards, with GET.
    provider_form = models.JSONField(default=dict, blank=True, editable=False)
    provider_reference = models.CharField(
        "provider's reference",
        max_length=100,
        blank=True,
        help_text="The provider's transaction ID, to find the payment in its statements.",
    )
    live = models.BooleanField(
        default=False, help_text="Unticked: made in the provider's test system, so no money moved."
    )
    created_at = models.DateTimeField("started", auto_now_add=True)
    updated_at = models.DateTimeField("updated", auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        amount = self.display_amount()
        return f"{self.get_method_display()} {amount}: {self.get_status_display().lower()}"

    def display_amount(self):
        return format_money(self.amount, self.currency)

    def record(self, status, provider_reference=""):
        """Save what the provider says about this payment, and what that means for its pledge.
        Returns whether anything changed.

        A conditional update rather than a read then a save: the payer's return and a later
        check can arrive at once, and SQLite can't lock a row.
        """
        status = PaymentStatus(status)
        now = timezone.now()
        changes = {"status": status, "updated_at": now}
        if provider_reference:
            changes["provider_reference"] = provider_reference
        with transaction.atomic():
            unpaid = Pledge.objects.filter(pk=self.pledge_id).exclude(
                payment_status=PaymentStatus.PAID
            )
            changed = Payment.objects.filter(
                pk=self.pk, status__in=CHANGES_FROM.get(status, [])
            ).update(**changes)
            if not changed:
                return False
            if status == PaymentStatus.PAID:
                # Only for what the pledge says now: one changed since this attempt started (in
                # the admin, say) stays unpaid until a person looks.
                unpaid.filter(amount=self.amount, currency=self.currency).update(
                    payment_status=PaymentStatus.PAID, paid_at=now
                )
            else:
                unpaid.update(payment_status=PaymentStatus.FAILED)
        for name, value in changes.items():
            setattr(self, name, value)
        return True
