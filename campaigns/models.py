import datetime
import logging
import re
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.translation import gettext, gettext_lazy
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
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

from campaigns.payments import (
    IN_PERSON,
    ONLINE,
    QR,
    QR_CURRENCIES,
    is_team_confirmed,
    method_choices,
    provider_for,
    providers_for,
    ways_to_pay,
)
from core.blocks import BaseStreamBlock
from core.images import UPLOAD_EXTENSIONS, check_upload, clean_image, with_card_images
from core.models import (
    SiteSettings,
    SocialMetaMixin,
    TextInEachLanguage,
    TextInEachLanguageMixin,
)
from core.money import CURRENCY_CHOICES, format_money
from nepal_payments import PaymentError, PaymentRequest, ProviderRefused, UnreadableAnswer

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


# How long a waiting attempt is offered again rather than starting another: well within the
# hour a Khalti payment link lasts.
REUSE_ATTEMPT_FOR = datetime.timedelta(minutes=10)

# What asking a provider just now found, for the pay page to say once: a message with this tag.
# Messages are shared with the admin, so the pay page takes only its own.
PAYMENT_MESSAGE = "payment"


def tell_pay_page(request, result):
    """Leave the online pay page a one-off result: "checked" (the provider hasn't confirmed the
    payment yet), "unreachable" (it couldn't be asked) or "not-started" (it couldn't start one).
    Only that page reads it, so the payer must be sent straight there."""
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


# Not ready to pay yet: offered with the ways to pay, on every pledge's pay page, but not a way
# to pay, so it never counts towards them.
LATER = "later"

# Each way's page, by its route's name.
WAY_ROUTES = {ONLINE: "pay_online", QR: "pay_qr", IN_PERSON: "pay_in_person", LATER: "pay_later"}

# The ways' names, for templates to compare with rather than spell out.
WAY_NAMES = {"ONLINE": ONLINE, "QR": QR, "IN_PERSON": IN_PERSON, "LATER": LATER}

# The way whose page shows what became of paying, for each pay page state it shows. The choices
# send a pledge in one of these states there, and that page shows even once its way isn't
# offered any more.
STATE_WAYS = {
    "check-first": ONLINE,
    "failed": ONLINE,
    "to-confirm": QR,
    "not-found": QR,
}

# The states in which every other way's page goes to that way's: an attempt may already have paid,
# so nothing to pay with shows before checking it.
HELD = ("check-first",)

# The states in which every pay page address says thank you.
THANKED = ("paid", "received")


def either(names):
    """The names as a choice, in the reader's language: "eSewa or Khalti", "eSewa, Khalti or
    IME Pay"."""
    if len(names) < 2:
        return "".join(names)
    return gettext("%(names)s or %(last)s") % {"names": ", ".join(names[:-1]), "last": names[-1]}


class DonatePage(RoutablePageMixin, SocialMetaMixin, Page):
    """The page every Donate button leads to: suggested amounts and a pledge form.

    Each pledge it takes is saved as a `Pledge`, listed under Pledges in the admin. The form
    then redirects to the pledge's pay page when there's a way to pay it here (straight to that
    way's page when there's only one), or to the thank-you page, so reloading any of them can't
    send the form again.
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
    thank_you_text = RichTextField(
        blank=True,
        help_text="Shown after someone sends the form when there's no way to pay on the site yet.",
    )

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
    # The pay page's choices, and each way's page.
    pay_templates = {
        None: "campaigns/pay/choices.html",
        ONLINE: "campaigns/pay/online.html",
        QR: "campaigns/pay/qr.html",
        IN_PERSON: "campaigns/pay/in_person.html",
        LATER: "campaigns/pay/later.html",
    }
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
                _, ways, _ = self.ways_for(pledge, site_settings)
                if len(ways) == 1:
                    return self.redirect_to(request, WAY_ROUTES[ways[0]], pledge.reference)
                if ways:
                    return self.redirect_to(request, "pay", pledge.reference)
                return self.redirect_to(request, "thank_you")
        else:
            form = self.get_form(site_settings=site_settings, link=request.GET)
        # How paying works here, before an amount is chosen: any amount a provider takes.
        providers = providers_for(site_settings.currency)
        qr_codes = self.qr_codes_for(site_settings.currency)
        ways = ways_to_pay(providers, site_settings, qr_codes)
        return self.render(
            request,
            context_overrides={
                "form": form,
                "ways": ways,
                **WAY_NAMES,
                "pay_with": either([provider.name for provider in providers]),
                "how_to_pay": self.how_to_pay(providers, ways),
            },
        )

    def how_to_pay(self, providers, ways):
        """The ways as a phrase after "you can pay": "with eSewa or Khalti, by scanning our QR
        code or in person"."""
        phrases = []
        if ONLINE in ways:
            names = either([provider.name for provider in providers])
            phrases.append(gettext("with %(names)s") % {"names": names})
        if QR in ways:
            phrases.append(gettext("by scanning our QR code"))
        if IN_PERSON in ways:
            phrases.append(gettext("in person"))
        return either(phrases)

    @path("thank-you/", name="thank_you")
    def thank_you(self, request):
        return self.render(request, template=self.landing_page_template)

    def qr_codes_for(self, currency, names=False):
        """The charity's QR codes, when they take this currency: they're offered for rupees only,
        like the providers (the apps they're scanned with are Nepali). Their names are read only
        by the QR page, which asks for them."""
        if currency not in QR_CURRENCIES:
            return []
        return QRCode.for_pay_page(names)

    def ways_for(self, pledge, site_settings, names=False):
        """The providers that take the pledge, the ways to pay it and the QR codes offered,
        worked out once so they can't disagree."""
        providers = providers_for(pledge.currency, Decimal(pledge.amount))
        qr_codes = self.qr_codes_for(pledge.currency, names)
        return providers, ways_to_pay(providers, site_settings, qr_codes), qr_codes

    def get_pledge(self, reference):
        return get_object_or_404(
            Pledge.objects.select_related("appeal").prefetch_related("payments"),
            reference=reference,
            page=self,
        )

    @path("pay/<uuid:reference>/", name="pay")
    def pay(self, request, reference):
        """A pledge's pay page: the ways to pay it, each leading to its own page. Its address is
        the pledge's own reference, so only the person who sent it has it.

        A pledge one way is still dealing with goes to that way's page, and a pledge with only
        one way to pay goes straight to it. Paid, it says thank you, like every pay address.
        """
        pledge = self.get_pledge(reference)
        state = pledge.pay_page_state()
        site_settings = SiteSettings.for_request(request)
        if state in THANKED:
            return self.render_pay_page(request, pledge, state, [], [], [], site_settings)
        if state in STATE_WAYS:
            return self.redirect_to(request, WAY_ROUTES[STATE_WAYS[state]], reference)
        providers, ways, qr_codes = self.ways_for(pledge, site_settings)
        if not ways:
            return self.redirect_to(request, "thank_you")
        if len(ways) == 1:
            return self.redirect_to(request, WAY_ROUTES[ways[0]], reference)
        return self.render_pay_page(
            request, pledge, state, providers, ways, qr_codes, site_settings
        )

    @path("pay/<uuid:reference>/online/", name="pay_online")
    def pay_online(self, request, reference):
        return self.way_page(request, reference, ONLINE)

    @path("pay/<uuid:reference>/qr/", name="pay_qr")
    def pay_qr(self, request, reference):
        return self.way_page(request, reference, QR)

    @path("pay/<uuid:reference>/qr/paid/", name="qr_paid")
    def qr_paid(self, request, reference):
        """The supporter says they paid by scanning a QR code. The pledge becomes To confirm
        once, however many times and tabs this is sent from: only the one that moves it creates
        the payment. The team then looks for it in its statement."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        pledge = self.get_pledge(reference)
        site_settings = SiteSettings.for_request(request)
        qr_codes = self.qr_codes_for(pledge.currency, names=True)
        if not qr_codes or pledge.has_paid_payment():
            return self.redirect_to(request, "pay", reference)
        from campaigns.forms import QRPaidForm  # forms imports this module's Pledge

        form = QRPaidForm(request.POST, codes=qr_codes)
        if not form.is_valid():
            providers, ways, _ = self.ways_for(pledge, site_settings)
            response = self.render_pay_page(
                request,
                pledge,
                pledge.pay_page_state(),
                providers,
                ways,
                qr_codes,
                site_settings,
                QR,
                paid_form=form,
            )
            response.status_code = 422
            return response
        pledge.claim_paid(form.cleaned_data["code"], form.cleaned_data["transaction_id"])
        return self.redirect_to(request, "pay_qr", reference)

    @path("pay/<uuid:reference>/in-person/", name="pay_in_person")
    def pay_in_person(self, request, reference):
        return self.way_page(request, reference, IN_PERSON)

    @path("pay/<uuid:reference>/later/", name="pay_later")
    def pay_later(self, request, reference):
        return self.way_page(request, reference, LATER)

    def way_page(self, request, reference, way):
        """One way's page. A way that isn't offered (any more) goes back to the choices, unless
        it's the one dealing with the pledge: an online payment may have gone through after the
        provider's keys were removed. While that payment may be paid, every other way's page goes
        to its page, so nobody pays twice."""
        # Taken before any redirect: left in the session, it would turn up in the admin, or here
        # later as news that's no longer true.
        result = pay_page_result(request) if way == ONLINE else None
        pledge = self.get_pledge(reference)
        state = pledge.pay_page_state()
        if state in HELD and way != STATE_WAYS[state]:
            return self.redirect_to(request, WAY_ROUTES[STATE_WAYS[state]], reference)
        site_settings = SiteSettings.for_request(request)
        if state in THANKED:
            return self.render_pay_page(request, pledge, state, [], [], [], site_settings, way)
        providers, ways, qr_codes = self.ways_for(pledge, site_settings, names=way == QR)
        if not (way == LATER or way in ways or STATE_WAYS.get(state) == way):
            return self.redirect_to(request, "pay", reference)
        return self.render_pay_page(
            request, pledge, state, providers, ways, qr_codes, site_settings, way, result
        )

    def render_pay_page(
        self,
        request,
        pledge,
        state,
        providers,
        ways,
        qr_codes,
        site_settings,
        way=None,
        result=None,
        paid_form=None,
    ):
        """The choices (way None) or a way's page, or the thanks once paid (with no providers or
        ways: there's nothing left to pay). `result` is what asking a provider found, for the
        online page."""
        # An attempt for another amount (the pledge changed after it started) doesn't pay it,
        # but the money was still received, and isn't asked for again.
        received = pledge.paid_payment() if state in THANKED else None
        context = {
            "pledge": pledge,
            "state": state,
            "received": received,
            "way": way,
            "ways": ways,
            # The choices say it, and a way's page the form went straight to.
            "saved": way is None or ways == [way],
            # Every other way, at the bottom of a way's page, then Not ready to pay yet.
            "other_ways": [other for other in [*ways, LATER] if other != way],
            "site_settings": site_settings,
            "phone_link": "tel:" + re.sub(r"[^\d+]", "", site_settings.phone),
            **WAY_NAMES,
        }
        # Named on the choices, and on the online page.
        context["pay_with"] = either([provider.name for provider in providers])
        if way == ONLINE:
            latest = next(iter(pledge.payments.all()), None)  # newest first
            context |= {
                # Codes and names, not the classes, which templates would try to call.
                "providers": [(provider.code, provider.name) for provider in providers],
                # Before a charity goes live its real supporters can still get here.
                "test_mode": not settings.LIVE_PAYMENTS,
                "latest": latest,
                "result": result,
                # The others to try when the latest attempt's provider couldn't start it.
                "others": either([p.name for p in providers if latest and p.code != latest.method]),
            }
        if way == QR:
            from campaigns.forms import QRPaidForm  # forms imports this module's Pledge

            # The attempt the team is checking (or couldn't find): not an online one that came
            # after it.
            claimed = next((p for p in pledge.payments.all() if is_team_confirmed(p.method)), None)
            context |= {
                "qr_codes": qr_codes,
                "claimed": claimed,
                "paid_form": paid_form or QRPaidForm(codes=qr_codes),
            }
        if way == LATER:
            context["pay_link"] = request.build_absolute_uri(
                self.get_url(request) + self.reverse_subpage("pay", args=[pledge.reference])
            )
        return self.render(request, template=self.pay_templates[way], context_overrides=context)

    # Under online/, so no provider's code can clash with a way's name.
    @path("pay/<uuid:reference>/online/<slug:method>/", name="start_payment")
    def start_payment(self, request, reference, method):
        """Start paying a pledge with a provider, and send the payer there."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        pledge = get_object_or_404(
            Pledge.objects.select_related("appeal"), reference=reference, page=self
        )
        if pledge.has_paid_payment():
            return self.redirect_to(request, "pay_online", pledge.reference)
        provider = provider_for(method)
        if provider is None or type(provider) not in providers_for(
            pledge.currency, Decimal(pledge.amount)
        ):
            raise Http404("No such payment provider here.")
        # A second tap, a second tab or a resent form goes back to the attempt just started, so
        # there aren't two that could both be paid (two at the same instant can still race).
        waiting = pledge.payments.filter(
            method=method,
            status=PaymentStatus.WAITING,
            amount=pledge.amount,
            currency=pledge.currency,
            live=provider.live,
            created_at__gte=timezone.now() - REUSE_ATTEMPT_FOR,
        ).first()
        if waiting and waiting.page_at_provider():
            return self.redirect_to(request, "go_to_provider", waiting.reference)

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
            payment.add_step(step_for_error(error))
            payment.record(PaymentStatus.FAILED)
            tell_pay_page(request, "not-started")
            return self.redirect_to(request, "pay_online", pledge.reference)

        redirect = started.redirect
        # Kept, so a second tap goes back to the same page at the provider.
        Payment.objects.filter(pk=payment.pk).update(
            provider_id=started.provider_id,
            provider_form={
                "url": redirect.url,
                "method": redirect.method,
                "fields": redirect.fields,
                "once": provider.opens_once,
            },
        )
        payment.add_step(StepKind.SENT)
        if redirect.method == "GET":
            return HttpResponseRedirect(redirect.url, status=303)
        # A form to post to the provider: sent from a page fetched with GET, so Back from the
        # provider reloads that page rather than asking to resend this one.
        return self.redirect_to(request, "go_to_provider", payment.reference)

    @path("payment/<uuid:reference>/go/", name="go_to_provider")
    def go_to_provider(self, request, reference):
        """The way back to a payment's page at its provider: the form that sends it there
        (eSewa), or a redirect to its link (Khalti). Once the payment isn't waiting any more, or
        another has paid the pledge, the pay page instead: it would pay again. So too once a form
        the provider takes only once has been shown: the provider would refuse it."""
        payment = get_object_or_404(
            Payment.objects.select_related("pledge"), reference=reference, pledge__page=self
        )
        form = payment.page_at_provider()
        if (
            payment.status != PaymentStatus.WAITING
            or form is None
            or payment.pledge.has_paid_payment()
        ):
            return self.redirect_to(request, "pay_online", payment.pledge.reference)
        # A form kept before links were kept too has no "method": it's posted.
        if form.get("method") == "GET":
            return HttpResponseRedirect(form["url"], status=303)
        if form.get("once"):
            Payment.objects.filter(pk=payment.pk).update(provider_form={**form, "shown": True})
        response = self.render(
            request,
            template=self.redirect_template,
            context_overrides={
                "provider_name": payment.get_method_display(),
                "form_url": form["url"],
                "fields": form["fields"],
                "once": form.get("once"),
            },
        )
        # Back from the provider fetches it again, so this decides whether it's sent again.
        add_never_cache_headers(response)
        return response

    @path("payment/<uuid:reference>/", name="payment_return")
    def payment_return(self, request, reference):
        """Where a provider sends the payer back, paid or not. Only the provider, asked here,
        says which: what the browser brings back is never read."""
        payment = get_object_or_404(
            Payment.objects.select_related("pledge"), reference=reference, pledge__page=self
        )
        if payment.status != PaymentStatus.PAID:
            payment.add_step(StepKind.CAME_BACK)
            failed_before = payment.status == PaymentStatus.FAILED
            outcome = payment.ask()
            if outcome is None:
                # Not when it couldn't be asked at all: there's nothing to try again.
                if payment.provider():
                    tell_pay_page(request, "unreachable")
            elif outcome.status == PaymentStatus.WAITING or (
                failed_before and outcome.status == PaymentStatus.FAILED
            ):
                tell_pay_page(request, "checked")
        return self.redirect_to(request, "pay_online", payment.pledge.reference)

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


# The longest side of a QR card as saved: the larger one is for saving and scanning, the smaller
# is what the page shows (both in the upload's own format).
QR_IMAGE_WIDTHS = (1600, 800)


class QRCode(TextInEachLanguageMixin, ClusterableModel, Orderable):
    """One QR code a supporter can scan to pay: a wallet's or a bank's, as an image to show and
    save (#197).

    A record of its own in the admin, listed under QR codes, so only the people given its
    permissions can add, change or remove one (moderators). The image is stored on the code, not
    in the image library: an editor can replace a library image, which would send gifts to
    another account. Wagtail logs who added, changed or removed each code, in its history.
    """

    image = models.ImageField(
        upload_to="qr-codes",
        width_field="image_width",
        height_field="image_height",
        validators=[FileExtensionValidator(UPLOAD_EXTENSIONS), check_upload],
        help_text="The QR card as your wallet or bank gives it: it's shown as it is, so keep its "
        "name and logo. A JPEG, PNG or WebP of up to 5 MB.",
    )
    # The same card at a smaller size, for phones to show. Made from `image` when it's uploaded.
    image_small = models.ImageField(
        upload_to="qr-codes", editable=False, width_field="small_width", blank=True
    )
    image_width = models.PositiveIntegerField(null=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, editable=False)
    small_width = models.PositiveIntegerField(null=True, editable=False)
    account_name = models.CharField(
        max_length=255,
        help_text="Exactly as the app shows it after scanning the QR code. Supporters are asked "
        "to check it before they pay.",
    )
    account_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="The account or wallet number, for supporters who can't scan.",
    )

    panels = [
        InlinePanel(
            "texts",
            heading="Name in each language",
            label="Language",
            help_text="What supporters pick it by, such as eSewa or Fonepay (bank). A language "
            "with no name of its own shows the main language's.",
        ),
        FieldPanel("image"),
        FieldPanel("account_name"),
        FieldPanel("account_number"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "QR code"
        # A code never given a place (made in code, say) goes after those that were, oldest first.
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.name or self.account_name

    @classmethod
    def for_pay_page(cls, names=True):
        """The codes supporters can pay to, in order, with their names in each language: one
        query when there are none, two otherwise. Without `names` (to know only whether there are
        any, and how many), one query, and the codes can't be named. The names are attached by
        hand: Prefetch gave every code of a cluster the last one's."""
        codes = list(cls.objects.all())
        if codes and names:
            by_code = {code.pk: {} for code in codes}
            for text in QRCodeName.objects.filter(code__in=codes).select_related("locale"):
                by_code[text.code_id][text.locale.language_code] = text
            for code in codes:
                code._texts_by_language = by_code[code.pk]
        return codes

    @property
    def name(self):
        return self.text_in_reading_language("name")

    def save(self, *args, **kwargs):
        """Saves a new image's two sizes in place of the upload, and removes the files it
        replaces. The names are our own: nothing from the upload's name is kept."""
        previous = set()
        if self.pk:
            was = QRCode.objects.filter(pk=self.pk).values_list("image", "image_small").first()
            previous = set(was or ()) - {""}
        if self.image and not self.image._committed:
            extension, (large, small) = clean_image(self.image.file, QR_IMAGE_WIDTHS)
            name = uuid.uuid4().hex
            self.image.save(f"{name}.{extension}", large, save=False)
            self.image_small.save(f"{name}-small.{extension}", small, save=False)
        super().save(*args, **kwargs)
        for name in previous - {self.image.name, self.image_small.name}:
            self.image.storage.delete(name)


@receiver(post_delete, sender=QRCode)
def delete_qr_code_images(sender, instance, **kwargs):
    """A removed QR leaves nothing behind that could still be fetched."""
    for field in (instance.image, instance.image_small):
        if field.name:
            field.storage.delete(field.name)


class QRCodeName(TextInEachLanguage):
    code = ParentalKey(QRCode, on_delete=models.CASCADE, related_name="texts")
    name = models.CharField(max_length=100)

    panels = [FieldPanel("locale"), FieldPanel("name")]

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "locale"], name="one_qr_name_per_language")
        ]


class Frequency(models.TextChoices):
    """How often a supporter gives. Shared by pledges, the pledge form and anything that acts on
    them (such as monthly reminders), so compare with Frequency.MONTHLY, never the string."""

    ONE_OFF = "one-off", "One-off"
    MONTHLY = "monthly", "Monthly"


class PaymentStatus(models.TextChoices):
    """Whether a pledge or a payment has been paid: the payment providers' statuses
    (nepal_payments.Status), with the names the team reads in the admin."""

    WAITING = "waiting", "Waiting"
    # Said paid by the supporter, and waiting for the team to find it in its statement.
    TO_CONFIRM = "to-confirm", "To confirm"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"


# The statuses a payment may change from, to each status: paid never goes back, and a failed
# attempt may still turn out paid (eSewa sends the payer back to one address, paid or not; the
# team may find a QR payment it first couldn't).
CHANGES_FROM = {
    PaymentStatus.PAID: [PaymentStatus.WAITING, PaymentStatus.TO_CONFIRM, PaymentStatus.FAILED],
    PaymentStatus.FAILED: [PaymentStatus.WAITING, PaymentStatus.TO_CONFIRM],
}

# The statuses of a payment that may still turn out paid, so nothing else marks its pledge failed.
MAY_STILL_PAY = [PaymentStatus.WAITING, PaymentStatus.TO_CONFIRM, PaymentStatus.PAID]


def new_pledge_number():
    """A random six-digit pledge number, 100000 to 999999."""
    return str(100000 + secrets.randbelow(900000))


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
        "payment", max_length=10, choices=PaymentStatus, default=PaymentStatus.WAITING
    )
    paid_at = models.DateTimeField("paid", null=True, blank=True)
    # The address of its pay page. Not submission_id: whoever holds that can send the form again
    # and change the pledge.
    reference = models.UUIDField(null=True, unique=True, editable=False)
    # Short enough to read out at the office or write in a payment's remarks, so the team finds
    # the pledge without guessing between two people with the same name. Never a way in: the pay
    # page is at the reference.
    number = models.CharField("pledge number", max_length=6, unique=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        # Whoever finds a payment in the team's statement and marks it paid, or says it isn't
        # there: moderators have it, editors only read pledges.
        permissions = [("confirm_payment", "Can confirm payments")]

    def __str__(self):
        return f"{self.name}: {self.display_amount()} {self.get_frequency_display().lower()}"

    def save(self, *args, **kwargs):
        if self.reference is None:
            self.reference = uuid.uuid4()
        if self.number:
            return super().save(*args, **kwargs)
        # Pick the number here, not in the form, so pledges made in the admin, in tests or in the
        # demo get one too. A number already taken (one in 900,000 per pledge) is tried again;
        # any other clash, such as the form's double click, is passed on.
        for attempt in range(10):
            self.number = new_pledge_number()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                taken = Pledge.objects.filter(number=self.number).exists()
                if not taken or attempt == 9:
                    self.number = ""
                    raise

    @admin.display(description="Pledge number")
    def display_number(self):
        """In two groups of three, "482 913", easier to read out than "482913"."""
        return f"{self.number[:3]} {self.number[3:]}"

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
        paid = self.paid_payment()
        return f"{shown} (test)" if paid and not paid.live else shown

    @admin.display(description="Paid with")
    def paid_with(self):
        """The provider and its reference for the payment, e.g. "eSewa 000AWEO", marked "(test)"
        when no money moved. Reads payments as fetched, so a list can prefetch them."""
        paid = self.paid_payment()
        if paid is None:
            return ""
        made = f"{paid.get_method_display()} {paid.provider_reference}".strip()
        return made if paid.live else f"{made} (test)"

    def paid_payment(self):
        """The attempt that paid it, if any, even one for an amount it no longer asks for (the
        money was still received). Reads payments as fetched, so a list can prefetch them."""
        return next((p for p in self.payments.all() if p.status == PaymentStatus.PAID), None)

    def pay_page_state(self):
        """What its pay page shows, from what became of paying it:

        - "paid": an attempt paid it, for what the pledge asks.
        - "received": an attempt paid another amount (the team received less or more than the
          pledge, or the pledge was changed after the attempt started); a person sorts it out.
        - "check-first": the latest attempt is waiting, so it may already be paid.
        - "to-confirm": the supporter says they paid by QR, and the team hasn't found it yet.
        - "not-found": the team couldn't find the supporter's QR payment.
        - "failed": the latest attempt failed after reaching its provider, so it may still turn
          out paid: checking comes before paying again.
        - "not-started": the latest attempt failed before reaching its provider: no money taken.
        - "ready": nothing started yet.

        Reads payments as fetched, so the pay page can prefetch them.
        """
        paid = self.paid_payment()
        if paid:
            same_gift = paid.amount == self.amount and paid.currency == self.currency
            return "paid" if self.payment_status == PaymentStatus.PAID and same_gift else "received"
        payments = list(self.payments.all())  # newest first
        latest = payments[0] if payments else None
        if latest and latest.status == PaymentStatus.WAITING:
            return "check-first"
        # Still to confirm even when a later online attempt has failed.
        if any(p.status == PaymentStatus.TO_CONFIRM for p in payments):
            return "to-confirm"
        if self.payment_status == PaymentStatus.FAILED:
            if latest and is_team_confirmed(latest.method):
                return "not-found"
            return "failed" if latest and latest.reached_provider() else "not-started"
        return "ready"

    def has_paid_payment(self):
        """Whether any attempt has paid it, live or test, at any amount: it's never asked for
        again, even when the pledge isn't marked paid because it was changed since."""
        return self.payments.filter(status=PaymentStatus.PAID).exists()

    def received_money(self):
        """Whether a payment of it moved real money, not just a provider's test system."""
        return self.payments.filter(status=PaymentStatus.PAID, live=True).exists()

    def claim_paid(self, code, transaction_id):
        """The supporter says they paid by scanning `code`: a payment for the team to confirm,
        and the pledge To confirm. Returns the payment, or None when the pledge wasn't waiting or
        failed any more (a second tap, another tab, or paid since), so only one claim makes one.

        A conditional update, not a read then a save: two sends at once can't both change it.
        """
        with transaction.atomic():
            changed = Pledge.objects.filter(
                pk=self.pk, payment_status__in=[PaymentStatus.WAITING, PaymentStatus.FAILED]
            ).update(payment_status=PaymentStatus.TO_CONFIRM)
            if not changed:
                return None
            payment = self.payments.create(
                method=QR,
                amount=self.amount,
                currency=self.currency,
                status=PaymentStatus.TO_CONFIRM,
                # Real money, whatever the site's mode: it's never shown as a test, and it can't
                # be deleted.
                live=True,
                qr_code=code,
                qr_name=code.name,
                supporters_reference=transaction_id,
            )
            payment.add_step(StepKind.CLAIMED)
        self.payment_status = PaymentStatus.TO_CONFIRM
        return payment

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
    status = models.CharField(max_length=10, choices=PaymentStatus, default=PaymentStatus.WAITING)
    # Ours, sent to the provider (eSewa's transaction_uuid, Khalti's purchase_order_id), and the
    # address the payer comes back to.
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider_id = models.CharField(
        max_length=100, blank=True, help_text="The provider's ID for the attempt (Khalti's pidx)."
    )
    # Where the provider takes the payer, as {"url", "method", "fields", "once"}: a signed form to
    # post (eSewa), sent from a page fetched afterwards with GET, or a link (Khalti). Kept so a
    # second tap goes back there, unless "once" (the provider's page takes the payer only once)
    # and "shown" (the form has been sent).
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
    # A QR payment: the code the supporter says they scanned, and its name as it was then, so "by
    # eSewa QR" is still said once the code is removed or renamed.
    qr_code = models.ForeignKey(
        QRCode, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    qr_name = models.CharField("QR code", max_length=100, blank=True)
    # The transaction ID the supporter read from their app's receipt: what to look for in the
    # statement, and what the team's reference starts as when it marks the payment paid.
    supporters_reference = models.CharField(
        "transaction ID from the supporter", max_length=100, blank=True
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

    def page_at_provider(self):
        """Its kept form or link, to send the payer to its page at the provider; None once it
        can't be used again: a form the provider takes only once, already shown, would be refused
        as a duplicate (eSewa's "Duplicate transaction UUID")."""
        form = self.provider_form
        if not form or (form.get("once") and form.get("shown")):
            return None
        return form

    def reached_provider(self):
        """Whether the provider started it, so the payer may have paid even after it's said to
        have failed (eSewa can say "not found" before "complete"). One that never started can't
        have taken money."""
        return bool(self.provider_id or self.provider_form)

    def provider(self):
        """Its provider, ready to ask about it; None when the provider isn't set up here any
        more, or is set up for the other system (test or live), whose keys can't look it up."""
        provider = provider_for(self.method)
        return provider if provider and provider.live == self.live else None

    def ask(self, by=None):
        """Ask the provider what became of this payment, record what it says, and add a step for
        every outcome: the answer, or why there wasn't one. The return page, the team's check and
        a scheduled check all ask here. `by` is the person who asked, if one did.

        Returns the provider's Outcome, or None when it couldn't be asked or didn't answer.
        Only known values are stored: an error's text, which can quote the provider's reply,
        goes to the log, and the provider's word only if it's one of its `statuses`.
        """
        if is_team_confirmed(self.method):
            return None  # no provider to ask: the team looks in its statement
        provider = self.provider()
        if provider is None:
            self.add_step(StepKind.NOT_ASKED, by=by)
            return None
        try:
            outcome = provider.check(str(self.reference), Decimal(self.amount), self.provider_id)
        except (PaymentError, ValueError) as error:
            logger.warning("%s couldn't check payment %s: %s", provider.name, self, error)
            self.add_step(step_for_error(error), by=by)
            return None
        word = outcome.word if outcome.word in provider.statuses else ""
        self.add_step(StepKind.ASKED, word=word, by=by)
        self.record(outcome.status, outcome.provider_reference)
        return outcome

    def mark_paid(self, by, received_on, amount, reference):
        """The team found this payment in its statement: paid, for the `amount` received (whole
        rupees, which may differ from the pledge's) on `received_on`, with the statement's
        `reference`. Set once: a paid payment is never changed, like any other. Returns whether
        it changed anything: not for a payment no provider answers for, one already paid, or one
        whose pledge another payment has paid.
        """
        if not is_team_confirmed(self.method):
            return False
        now = timezone.now()
        paid_at = (
            now
            if received_on == timezone.localdate()
            else timezone.make_aware(datetime.datetime.combine(received_on, datetime.time(12)))
        )
        with transaction.atomic():
            if self.pledge.payments.filter(status=PaymentStatus.PAID).exists():
                return False
            changed = Payment.objects.filter(
                pk=self.pk, status__in=[PaymentStatus.TO_CONFIRM, PaymentStatus.FAILED]
            ).update(
                status=PaymentStatus.PAID,
                amount=amount,
                provider_reference=reference,
                updated_at=now,
            )
            if not changed:
                return False
            # Whatever the team received: it's looked at the statement, so the pledge is paid,
            # and the pay page says "received" when it was another amount.
            Pledge.objects.filter(pk=self.pledge_id).update(
                payment_status=PaymentStatus.PAID, paid_at=paid_at
            )
            self.add_step(StepKind.MARKED_PAID, by=by)
        self.status, self.amount, self.provider_reference = (
            PaymentStatus.PAID,
            amount,
            reference,
        )
        return True

    def mark_not_found(self, by):
        """The team couldn't find this payment in its statement: it failed (it may still be
        marked paid later, if it turns up). Returns whether it changed anything."""
        if not is_team_confirmed(self.method) or self.status != PaymentStatus.TO_CONFIRM:
            return False
        if not self.record(PaymentStatus.FAILED):
            return False
        self.add_step(StepKind.NOT_FOUND, by=by)
        return True

    def add_step(self, kind, word="", by=None):
        """Add a step to its history. Pass only known values, never a provider's reply."""
        return self.steps.create(kind=kind, word=word, by=by)

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
                # Only for what the pledge says now: one changed since this attempt started
                # (which the admin no longer allows) stays unpaid until a person looks.
                unpaid.filter(amount=self.amount, currency=self.currency).update(
                    payment_status=PaymentStatus.PAID, paid_at=now
                )
            else:
                # Not while another attempt may still pay it: the pay page would say this one
                # failed and hide the check for that one.
                unpaid.exclude(payments__status__in=MAY_STILL_PAY).update(
                    payment_status=PaymentStatus.FAILED
                )
        for name, value in changes.items():
            setattr(self, name, value)
        return True


class StepKind(models.TextChoices):
    """What happened to a payment. A fixed list, so nothing a provider sends is stored as text."""

    SENT = "sent", "Sent to the provider"
    CAME_BACK = "came-back", "Came back to the site"
    ASKED = "asked", "The provider answered"
    UNREACHABLE = "unreachable", "Couldn't reach the provider"
    UNREADABLE = "unreadable", "Answer not understood"
    REFUSED = "refused", "The provider refused"
    NOT_ASKED = "not-asked", "Couldn't ask the provider"
    # What happens to a payment the team confirms, which no provider is asked about.
    CLAIMED = "claimed", "The supporter said they paid"
    MARKED_PAID = "marked-paid", "Marked paid by the team"
    NOT_FOUND = "not-found", "Marked not found by the team"


def step_for_error(error):
    """The step for an error starting or checking a payment."""
    if isinstance(error, UnreadableAnswer):
        return StepKind.UNREADABLE
    if isinstance(error, ProviderRefused):
        return StepKind.REFUSED
    if isinstance(error, PaymentError):
        return StepKind.UNREACHABLE
    return StepKind.NOT_ASKED  # it couldn't be asked, such as Khalti's with no pidx


class PaymentStep(models.Model):
    """One thing that happened to a payment, so the team can follow it up without the
    provider's portal. Only known values: a provider's reply or error text can hold the payer's
    details, so it's never stored."""

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="steps")
    kind = models.CharField(max_length=12, choices=StepKind)
    # The provider's own word for its answer (eSewa's "CANCELED"), only one in its `statuses`.
    word = models.CharField("provider's word", max_length=50, blank=True)
    # The person who did it, such as a team member asking the provider; blank for the payer or
    # the site.
    by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    at = models.DateTimeField("when", default=timezone.now)

    class Meta:
        ordering = ["at", "pk"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.word}".strip()
