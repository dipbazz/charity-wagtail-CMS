import datetime
import logging
import re
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.core.paginator import Paginator
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone, translation
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

from campaigns import sharing
from campaigns.payments import (
    IN_PERSON,
    ONLINE,
    QR,
    QR_CURRENCIES,
    is_team_confirmed,
    logo_for,
    method_choices,
    provider_for,
    providers_for,
    ways_to_pay,
)
from core import limits
from core.blocks import BaseStreamBlock
from core.images import UPLOAD_EXTENSIONS, check_upload, clean_image, with_card_images
from core.languages import main_language
from core.models import (
    SiteSettings,
    SocialMetaMixin,
    TextInEachLanguage,
    TextInEachLanguageMixin,
)
from core.money import CURRENCY_CHOICES, format_money
from nepal_payments import (
    PaymentError,
    PaymentRequest,
    ProviderRefused,
    UnreadableAnswer,
    get_provider,
)

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

    @property
    def target_reached(self):
        return bool(self.target_amount) and self.amount_raised >= self.target_amount

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


# What saving the thank-you page's Show my gift box did ("shown" or "hidden"), for that page to
# say once.
GIFT_MESSAGE = "gift"


def tell_pay_page(request, result):
    """Leave the online pay page a one-off result: "checked" (the provider hasn't confirmed the
    payment yet), "unreachable" (it couldn't be asked) or "not-started" (it couldn't start one).
    Only that page reads it, so the payer must be sent straight there."""
    messages.info(request, result, extra_tags=PAYMENT_MESSAGE)


def take_message(request, tag):
    """The message with `tag` left for this page, if any. Any other message is kept for the page
    it's for.

    The pay page's messages are all taken on the first call, once per request: reading the
    messages again would bring back the ones already taken, and add the others twice."""
    if not hasattr(request, "pay_page_messages"):
        request.pay_page_messages = {}
        others = []
        for message in messages.get_messages(request):
            tags = (message.extra_tags or "").split()
            mine = next((tag for tag in (PAYMENT_MESSAGE, GIFT_MESSAGE) if tag in tags), None)
            if mine:
                request.pay_page_messages[mine] = message.message
            else:
                others.append(message)
        for message in others:
            messages.add_message(request, message.level, message.message, message.extra_tags)
    return request.pay_page_messages.get(tag)


def pay_page_result(request):
    """The result tell_pay_page() left, if any."""
    return take_message(request, PAYMENT_MESSAGE)


# Not ready to pay yet: offered with the ways to pay, on every pledge's pay page, but not a way
# to pay, so it never counts towards them.
LATER = "later"

# Each way's page, by its route's name.
WAY_ROUTES = {ONLINE: "pay_online", QR: "pay_qr", IN_PERSON: "pay_in_person", LATER: "pay_later"}

# The ways' names, for templates to compare with rather than spell out.
WAY_NAMES = {"ONLINE": ONLINE, "QR": QR, "IN_PERSON": IN_PERSON, "LATER": LATER}

# The page that shows what became of paying, by its route's name, for each pay page state it
# shows: the way's page, or the checking page while the team checks a payment. The choices send
# a pledge in one of these states there, and a way's page shows even once its way isn't offered
# any more.
STATE_ROUTES = {
    "check-first": "pay_online",
    "failed": "pay_online",
    "to-confirm": "checking",
    "not-found": "pay_qr",
}

# The states in which every other pay page goes to that state's page, and nothing else can be
# paid: an online attempt may already have paid, or the team is checking a payment the supporter
# says they made. Only once it's found or not can the pledge be paid another way.
HELD = ("check-first", "to-confirm")

# The states in which every pay page address says thank you.
THANKED = ("paid", "received")


def chosen_code(request, qr_codes):
    """The QR code step 1's Go to step 2 sent (?code=), as the form's initial choice, if it's
    one of the codes on the page."""
    code = request.GET.get("code", "")
    return {"code": code} if code in {str(qr.pk) for qr in qr_codes} else {}


def phone_link(site_settings):
    return "tel:" + re.sub(r"[^\d+]", "", site_settings.phone)


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
    # Paying by QR is two pages: scanning (the way's page), then telling us it's paid.
    qr_paid_template = "campaigns/pay/qr_paid.html"
    checking_template = "campaigns/pay/checking.html"
    wait_template = "campaigns/pay/wait.html"
    redirect_template = "campaigns/donate_page_redirect.html"
    gift_template = "campaigns/gift_page.html"
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
        waiting = False
        if request.method == "POST":
            form = self.get_form(request.POST, site_settings=site_settings)
            # Only a new pledge counts (#226): sending the same copy again updates the pledge it
            # saved, so "hasn't been sent yet" is always true.
            if form.is_valid() and not (
                waiting := form.instance.pk is None and limits.over_limit(request, "pledge")
            ):
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
        response = self.render(
            request,
            context_overrides={
                "form": form,
                "ways": ways,
                **WAY_NAMES,
                "pay_with": either([provider.name for provider in providers]),
                "how_to_pay": self.how_to_pay(providers, ways),
                "wait_minutes": waiting and limits.wait_minutes(),
            },
        )
        return limits.too_many(response) if waiting else response

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

    def get_pledge(self, in_any_language=False, **lookup):
        """One of this page's pledges, by its reference (its pay page) or gift code (its gift's
        page), with its appeal and payments. `in_any_language`: sent from this page in any
        language, as a gift's page reads in each."""
        if in_any_language:
            lookup["page__translation_key"] = self.translation_key
        else:
            lookup["page"] = self
        pledge = get_object_or_404(
            Pledge.objects.select_related("appeal").prefetch_related("payments"), **lookup
        )
        pledge.page = self  # it's this page: sharing reads it without fetching it again
        return pledge

    @path("pay/<uuid:reference>/", name="pay")
    def pay(self, request, reference):
        """A pledge's pay page: the ways to pay it, each leading to its own page. Its address is
        the pledge's own reference, so only the person who sent it has it.

        A pledge one way is still dealing with goes to that way's page, and a pledge with only
        one way to pay goes straight to it. Paid, it says thank you, like every pay address.
        """
        pledge = self.get_pledge(reference=reference)
        state = pledge.pay_page_state()
        site_settings = SiteSettings.for_request(request)
        if state in THANKED:
            return self.render_pay_page(request, pledge, state, [], [], [], site_settings)
        if state in STATE_ROUTES:
            return self.redirect_to(request, STATE_ROUTES[state], reference)
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
        """Step 2 of paying by QR: the supporter tells us they paid, with the transaction ID, a
        screenshot of the receipt, or both. Opened, it's the form (or the checking page, once
        they've told us); sent, the pledge becomes To confirm once, however
        many times and tabs it's sent from: only the one that moves it creates the payment. The
        team then looks for it in its statement."""
        if request.method == "GET":
            return self.way_page(request, reference, QR, step=2)
        if request.method != "POST":
            return HttpResponseNotAllowed(["GET", "POST"])
        pledge = self.get_pledge(reference=reference)
        # Sent again, or from a tab opened before an online attempt started (that attempt may be
        # paid): the page dealing with the pledge.
        state = pledge.pay_page_state()
        if state in HELD:
            return self.redirect_to(request, STATE_ROUTES[state], reference)
        site_settings = SiteSettings.for_request(request)
        qr_codes = self.qr_codes_for(pledge.currency, names=True)
        if not qr_codes or pledge.has_paid_payment():
            return self.redirect_to(request, "pay", reference)
        from campaigns.forms import QRPaidForm  # forms imports this module's Pledge

        form = QRPaidForm(request.POST, request.FILES, codes=qr_codes)
        # Only a claim that would be saved counts (#226); over the limit, nothing is saved.
        valid = form.is_valid()
        if valid and limits.over_limit(request, "qr_paid"):
            providers, ways, _ = self.ways_for(pledge, site_settings)
            return limits.too_many(
                self.render_pay_page(
                    request,
                    pledge,
                    pledge.pay_page_state(),
                    providers,
                    ways,
                    qr_codes,
                    site_settings,
                    QR,
                    paid_form=form,
                    template=self.qr_paid_template,
                    wait_minutes=limits.wait_minutes(),
                )
            )
        if not valid:
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
                template=self.qr_paid_template,
            )
            response.status_code = 422
            return response
        pledge.claim_paid(
            form.cleaned_data["code"],
            form.cleaned_data["transaction_id"],
            form.cleaned_data["receipt"],
        )
        return self.redirect_to(request, "checking", reference)

    @path("pay/<uuid:reference>/checking/", name="checking")
    def checking(self, request, reference):
        """While the team checks a payment the supporter says they made (by QR): thanks, what they
        told us, and the pledge number to call about it. Every pay address of the pledge comes
        here meanwhile, as nothing else can be paid. Once it's found or not, this goes to the pay
        page, which says which."""
        pledge = self.get_pledge(reference=reference)
        if pledge.pay_page_state() != "to-confirm":
            return self.redirect_to(request, "pay", reference)
        claimed = next(p for p in pledge.payments.all() if p.status == PaymentStatus.TO_CONFIRM)
        site_settings = SiteSettings.for_request(request)
        return self.render(
            request,
            template=self.checking_template,
            context_overrides={
                "pledge": pledge,
                "state": "to-confirm",
                "claimed": claimed,
                "paid_by": claimed.paid_by(),
                "site_settings": site_settings,
                "phone_link": phone_link(site_settings),
                **self.sharing_context(request, pledge, site_settings),
            },
        )

    def sharing_context(self, request, pledge, site_settings):
        """The share section (#100), for the thank-you and checking pages: what to say, where a
        share sends friends, and the Show my gift box."""
        from campaigns.forms import ShowGiftForm  # forms imports this module's Pledge

        appeal = sharing.appeal_shown(pledge)
        charity = site_settings.name
        url = sharing.share_url(pledge, appeal, request)
        text = sharing.share_text(pledge, appeal, charity)
        if sharing.gift_view(pledge) != sharing.HIDDEN:
            title = sharing.gift_title(pledge, appeal, charity)
        else:
            title = appeal.title if appeal else charity
        return {
            "share": {
                "appeal": appeal,
                "needs_help": appeal is not None and sharing.needs_help(appeal),
                "url": url,
                "text": text,
                "title": title,
                "whatsapp": sharing.whatsapp_link(text, url),
                "facebook": sharing.facebook_link(url),
                # Just saved: the page says so, and focus moves to the section.
                "saved": take_message(request, GIFT_MESSAGE),
            },
            # Ticked while it's shown: not for a QR payment being checked, agreed in the old words.
            "show_gift_form": ShowGiftForm(
                initial={"show_on_website": sharing.gift_view(pledge) != sharing.HIDDEN}
            ),
        }

    @path("pay/<uuid:reference>/show-gift/", name="show_gift")
    def show_gift(self, request, reference):
        """The Show my gift box on the thank-you and checking pages: shows the gift on its page
        for friends, or takes it down, and says which once back there, only if the page did go
        up or down. Only once the supporter has told us they've paid, and never while the team
        has taken it down."""
        from campaigns.forms import ShowGiftForm  # forms imports this module's Pledge

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        pledge = self.get_pledge(reference=reference)
        state = pledge.pay_page_state()
        form = ShowGiftForm(request.POST)
        if sharing.offers_sharing(pledge) and not pledge.hidden_by_team and form.is_valid():
            was_shown = sharing.gift_view(pledge) != sharing.HIDDEN
            # Not changed if the team took it down meanwhile, so it says nothing.
            if pledge.set_show_on_website(form.cleaned_data["show_on_website"]):
                shown = sharing.gift_view(pledge) != sharing.HIDDEN
                if shown != was_shown:
                    messages.info(request, "shown" if shown else "hidden", extra_tags=GIFT_MESSAGE)
        route = STATE_ROUTES.get(state, "pay")
        return self.redirect_to(request, route, reference, fragment="share")

    @path("gifts/<slug:code>/", name="gift")
    def gift(self, request, code):
        """A gift's public page, which its supporter shares with friends (#100): their name, the
        appeal and what they gave, and a way for friends to give too. Its address is the
        pledge's gift code, never its reference, which pays it. It shows only what
        campaigns/sharing.py allows. Otherwise it goes where a share would now send friends (the
        appeal, else this page), so a link shared before still leads somewhere to give: not for
        good, as it may be shown again. It reads in each language, the appeal too, so a friend
        who switches language keeps the gift."""
        pledge = self.get_pledge(in_any_language=True, gift_code=code)
        if pledge.appeal and pledge.appeal.locale_id != self.locale_id:
            pledge.appeal = pledge.appeal.localized  # its live translation, else as it is
        view = sharing.gift_view(pledge)
        appeal = sharing.appeal_shown(pledge)
        if view == sharing.HIDDEN:
            return HttpResponseRedirect((appeal or self).get_url(request))
        paid = pledge.paid_payment()
        if paid:
            given_on = pledge.paid_at or paid.updated_at
        else:  # the day they told us they paid, while the team checks it
            payments = pledge.payments.all()
            given_on = next(p for p in payments if p.status == PaymentStatus.TO_CONFIRM).created_at
        title = sharing.gift_title(pledge, appeal, SiteSettings.for_request(request).name)
        return self.render(
            request,
            template=self.gift_template,
            context_overrides={
                "pledge": pledge,
                "view": view,
                "appeal": appeal,
                "gift_title": title,
                "summary": appeal.summary if appeal else self.introduction,
                "gift_amount": format_money(*sharing.gift_amount(pledge)),
                "given_on": given_on,
                "test_gift": sharing.is_test(pledge),
                "gift_url": sharing.gift_url(pledge, request),
                # The language switcher and hreflang links go to the gift in each language.
                "language_subpath": self.reverse_subpage("gift", args=[code]),
                # The appeal's preview picture, else the Donate page's.
                "social_image": (appeal and appeal.get_social_image()) or self.get_social_image(),
                # A closed appeal points friends to the open ones, if there are any.
                "open_appeals": bool(appeal)
                and not appeal.is_active
                and self.get_appeals().exists(),
            },
        )

    @path("pay/<uuid:reference>/in-person/", name="pay_in_person")
    def pay_in_person(self, request, reference):
        return self.way_page(request, reference, IN_PERSON)

    @path("pay/<uuid:reference>/later/", name="pay_later")
    def pay_later(self, request, reference):
        return self.way_page(request, reference, LATER)

    def way_page(self, request, reference, way, step=1):
        """One way's page. A way that isn't offered (any more) goes back to the choices, unless
        it's the one dealing with the pledge: an online payment may have gone through after the
        provider's keys were removed. While that payment may be paid, every other way's page goes
        to its page, so nobody pays twice. `step` 2 is the QR way's second page."""
        # Taken before any redirect: left in the session, it would turn up in the admin, or here
        # later as news that's no longer true.
        result = pay_page_result(request) if way == ONLINE else None
        pledge = self.get_pledge(reference=reference)
        state = pledge.pay_page_state()
        if state in HELD and STATE_ROUTES[state] != WAY_ROUTES[way]:
            return self.redirect_to(request, STATE_ROUTES[state], reference)
        site_settings = SiteSettings.for_request(request)
        if state in THANKED:
            return self.render_pay_page(request, pledge, state, [], [], [], site_settings, way)
        providers, ways, qr_codes = self.ways_for(pledge, site_settings, names=way == QR)
        if not (way == LATER or way in ways or STATE_ROUTES.get(state) == WAY_ROUTES[way]):
            return self.redirect_to(request, "pay", reference)
        return self.render_pay_page(
            request,
            pledge,
            state,
            providers,
            ways,
            qr_codes,
            site_settings,
            way,
            result,
            template=self.qr_paid_template if step == 2 else None,
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
        template=None,
        wait_minutes=None,
    ):
        """The choices (way None) or a way's page, or the thanks once paid (with no providers or
        ways: there's nothing left to pay). `result` is what asking a provider found, for the
        online page. `template` is a way's other page (QR's step 2). `wait_minutes`: how long to
        wait before sending its form again, over the limit (#226)."""
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
            "phone_link": phone_link(site_settings),
            "wait_minutes": wait_minutes,
            **WAY_NAMES,
        }
        # Named on the choices, and on the online page.
        context["pay_with"] = either([provider.name for provider in providers])
        if state in THANKED:
            context |= self.sharing_context(request, pledge, site_settings)
            # What the gift does, unless only a test system took it: then it does nothing.
            if received.live:
                appeal = context["share"]["appeal"]
                context["impact_line"] = sharing.impact_line(pledge, appeal, site_settings.currency)
        if way == ONLINE:
            latest = next(iter(pledge.payments.all()), None)  # newest first
            context |= {
                # Codes, names and logos, not the classes, which templates would try to call.
                "providers": [
                    (provider.code, provider.name, logo_for(provider)) for provider in providers
                ],
                # Before a charity goes live its real supporters can still get here.
                "test_mode": not settings.LIVE_PAYMENTS,
                "latest": latest,
                "result": result,
                # The others to try when the latest attempt's provider couldn't start it.
                "others": either([p.name for p in providers if latest and p.code != latest.method]),
            }
        if way == QR:
            from campaigns.forms import QRPaidForm  # forms imports this module's Pledge

            context |= {
                "qr_codes": qr_codes,
                # Step 1's Go to step 2 says which code they chose, if it's one on the page.
                "paid_form": paid_form
                or QRPaidForm(codes=qr_codes, initial=chosen_code(request, qr_codes)),
            }
        if way == LATER:
            context["pay_link"] = request.build_absolute_uri(
                self.get_url(request) + self.reverse_subpage("pay", args=[pledge.reference])
            )
        return self.render(
            request, template=template or self.pay_templates[way], context_overrides=context
        )

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
        state = pledge.pay_page_state()
        if state in HELD and STATE_ROUTES[state] != WAY_ROUTES[ONLINE]:
            return self.redirect_to(request, STATE_ROUTES[state], reference)
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
        # Only a new attempt counts (#226).
        if limits.over_limit(request, "start_payment"):
            return self.wait_page(request, pledge)

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
            # Only when the provider would be asked, and never the first time back (#226): each
            # payment has only one, starting one is counted, and others on the payer's
            # connection could otherwise leave a real payment unconfirmed.
            came_back = payment.steps.filter(kind=StepKind.CAME_BACK).exists()
            if came_back and limits.over_limit(request, "payment_return"):
                return self.wait_page(request, payment.pledge)
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

    def wait_page(self, request, pledge):
        """Starting a payment or coming back from one, over the limit (#226): how long to wait,
        and the way back to the pledge's pay page, which is never limited and opens on what
        became of paying, so it can't loop or offer paying twice."""
        site_settings = SiteSettings.for_request(request)
        return limits.too_many(
            self.render(
                request,
                template=self.wait_template,
                context_overrides={
                    "pledge": pledge,
                    "site_settings": site_settings,
                    "phone_link": phone_link(site_settings),
                    "wait_minutes": limits.wait_minutes(),
                },
            )
        )

    def redirect_to(self, request, name, *args, fragment=""):
        """303 to one of this page's routes, at `fragment` if given (a section's id)."""
        url = self.get_url(request) + self.reverse_subpage(name, args=args)
        return HttpResponseRedirect(f"{url}#{fragment}" if fragment else url, status=303)

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
        return cls.with_names(codes) if names else codes

    @staticmethod
    def with_names(codes):
        """The codes, each with its names in every language: one query, none when there are no
        codes, so a list of them costs the same however long it is."""
        codes = list(codes)
        if codes:
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
        delete_files_once_saved(
            self.image.storage, previous - {self.image.name, self.image_small.name}
        )


def delete_files_once_saved(storage, names):
    """Deletes the files once the change that left them behind is saved for good: undone, the
    code still points at them, and the pay page would show a broken QR."""
    if names:
        transaction.on_commit(lambda: [storage.delete(name) for name in names])


@receiver(post_delete, sender=QRCode)
def delete_qr_code_images(sender, instance, **kwargs):
    """A removed QR leaves nothing behind that could still be fetched."""
    names = {field.name for field in (instance.image, instance.image_small) if field.name}
    delete_files_once_saved(instance.image.storage, names)


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


def new_gift_code():
    """A random code for a gift's public page: 72 bits as 12 URL-safe characters."""
    return secrets.token_urlsafe(9)


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
        help_text="Agreed to their name, appeal and date being shown on a page they can share and "
        "in the list of recent supporters once they say they've paid, and the amount once it's "
        "received.",
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
    # The address of the gift's public page, which the supporter shares (#100). Random, so
    # nobody can guess one or count up to the next, and never the reference, which pays it.
    gift_code = models.CharField(max_length=12, unique=True, editable=False)
    # When the supporter last ticked or unticked show_on_website: on the form, or on the
    # thank-you page. Empty when they agreed before gift pages, in the old words: "Once your gift
    # reaches us" (campaigns/sharing.py).
    show_on_website_changed_at = models.DateTimeField(
        "show on website changed", null=True, blank=True, editable=False
    )
    # The team's Stop showing on the website: the gift isn't shown, whatever the supporter
    # ticks, until the team shows it again.
    hidden_by_team = models.BooleanField("taken down by the team", default=False, editable=False)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            # Whoever finds a payment in the team's statement and marks it paid, or says it isn't
            # there: moderators have it, editors only read pledges.
            ("confirm_payment", "Can confirm payments"),
            # Whoever takes a gift's public page down (a made-up name, say) and puts it back:
            # editors and moderators.
            ("stop_showing_gift", "Can stop showing a gift on the website"),
        ]

    def __str__(self):
        return f"{self.name}: {self.display_amount()} {self.get_frequency_display().lower()}"

    def save(self, *args, **kwargs):
        if self.reference is None:
            self.reference = uuid.uuid4()
        # Made with the box ticked (in the admin, tests or the demo too): agreed in today's words.
        if self._state.adding and self.show_on_website and not self.show_on_website_changed_at:
            self.show_on_website_changed_at = timezone.now()
        if self.number and self.gift_code:
            return super().save(*args, **kwargs)
        # Pick the number and gift code here, not in the form, so pledges made in the admin, in
        # tests or in the demo get them too. One picked already taken (a number is one in 900,000
        # per pledge) is tried again; any other clash, such as the form's double click or a
        # number given already taken, is passed on.
        number, gift_code = self.number, self.gift_code
        for attempt in range(10):
            self.number = number or new_pledge_number()
            self.gift_code = gift_code or new_gift_code()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                picked_taken = Q()
                if not number:
                    picked_taken |= Q(number=self.number)
                if not gift_code:
                    picked_taken |= Q(gift_code=self.gift_code)
                taken = Pledge.objects.filter(picked_taken).exists()
                if not taken or attempt == 9:
                    self.number, self.gift_code = number, gift_code
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
        """Waiting, to confirm, paid or failed, with "(test)" after paid when only a provider's
        test system took it: anyone can pay there with the provider's public test account, so it
        must never pass for money received. "Needs checking" when a person must look
        (needs_checking()). The list, the export and the pledge's page all say this. Reads
        payments as fetched, so a list can prefetch them."""
        if self.needs_checking():
            return "Needs checking"
        shown = self.get_payment_status_display()
        if self.payment_status != PaymentStatus.PAID:
            return shown
        paid = self.paid_payment()
        return f"{shown} (test)" if paid and not paid.live else shown

    def needs_checking(self):
        """Why a person must look at what was paid, or "": money received for an amount the
        pledge doesn't ask for (the team received another amount, or the pledge was changed after
        the payment started), or a provider saying it refunded part of a payment. Reads payments
        as fetched, so a list can prefetch them."""
        paid = self.paid_payment()
        if paid and (
            self.payment_status != PaymentStatus.PAID
            or (paid.amount, paid.currency) != (self.amount, self.currency)
        ):
            return (
                f"{paid.display_amount()} was received, but the pledge is for "
                f"{self.display_amount()}."
            )
        for payment in self.payments.all():
            if payment.needs_checking():
                return payment.word_sentence()
        return ""

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

    def set_show_on_website(self, shown):
        """The supporter's choice from the thank-you page's box, and when they made it. Not while
        the team has taken the gift down. Returns whether it changed anything. Ticked again after
        agreeing in the old words, it records that they agree in today's."""
        now = timezone.now()
        changed = (
            Pledge.objects.filter(pk=self.pk, hidden_by_team=False)
            .exclude(show_on_website=shown, show_on_website_changed_at__isnull=False)
            .update(show_on_website=shown, show_on_website_changed_at=now)
        )
        if changed:
            self.show_on_website, self.show_on_website_changed_at = shown, now
        return bool(changed)

    def has_paid_payment(self):
        """Whether any attempt has paid it, live or test, at any amount: it's never asked for
        again, even when the pledge isn't marked paid because it was changed since."""
        return self.payments.filter(status=PaymentStatus.PAID).exists()

    def received_money(self):
        """Whether a payment of it moved real money, not just a provider's test system."""
        return self.payments.filter(status=PaymentStatus.PAID, live=True).exists()

    def claim_paid(self, code, transaction_id, receipt=None):
        """The supporter says they paid by scanning `code`: a payment for the team to confirm,
        and the pledge To confirm. Returns the payment, or None when the pledge wasn't waiting or
        failed any more (a second tap, another tab, or paid since), so only one claim makes one.
        `receipt` is their screenshot of the receipt, already saved afresh by clean_image() and
        named (QRPaidForm), if they sent one.

        A conditional update, not a read then a save: two sends at once can't both change it.
        The code's name is kept in the site's main language, which the team reads, whichever
        language the supporter read in (or theirs, if it has no name in the main one).
        """
        with translation.override(main_language()):
            qr_name = code.name
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
                qr_name=qr_name or code.name,
                supporters_reference=transaction_id,
                receipt=receipt,
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


# A receipt screenshot's longest side as saved: a phone's whole screen, its small print still
# readable.
RECEIPT_WIDTH = 2000
# The most a receipt may decode to: any phone's screenshot. A photo from any phone camera passes
# too, as a JPEG is decoded straight to about RECEIPT_WIDTH. Anyone can send one, so a bigger
# picture (about 4 MB of memory per million pixels while it's re-saved) could run the server out
# of memory.
RECEIPT_MAX_PIXELS = 13_000_000
# The longest a screenshot is kept when nobody has checked its payment (delete_old_receipts).
RECEIPTS_KEPT_FOR = datetime.timedelta(days=30)
# How soon the team's check may ask a provider about a payment again: each ask can wait up to
# nepal_payments.http.TIMEOUT (10 seconds) for an answer.
ASK_AGAIN_AFTER = datetime.timedelta(seconds=30)


def receipts_storage():
    """Where receipt screenshots are kept: STORAGES["receipts"], which no address serves."""
    return storages["receipts"]


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
    # The provider's own word from its latest answer, only one in its `statuses` (as on the
    # steps), so the list of pledges can say one needs checking without reading every step.
    word = models.CharField("provider's latest word", max_length=50, blank=True, editable=False)
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
    # A screenshot of that receipt, if the supporter sent one, as clean_image() saved it afresh.
    # Only people who can confirm payments see it, and it's deleted once the payment is marked
    # paid or not found, or after RECEIPTS_KEPT_FOR at most.
    receipt = models.FileField(
        "screenshot of the receipt", storage=receipts_storage, blank=True, editable=False
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

    def paid_by(self):
        """What the supporter says they paid by, in the language they read: the QR code's name
        while the code is still there, or the name it had then (in the site's main language)."""
        if self.qr_code_id:
            name = QRCode.with_names([self.qr_code])[0].name
            if name:
                return name
        return self.qr_name or self.get_method_display()

    @property
    def team_confirms(self):
        """Whether the team, not a provider, says if it's paid: for templates, which can't call
        is_team_confirmed()."""
        return is_team_confirmed(self.method)

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

    def needs_checking(self):
        """Whether its provider's latest word means a person must look, such as a partial
        refund."""
        provider = get_provider(self.method)
        return bool(provider and self.word in provider.needs_checking)

    def word_sentence(self, word=None):
        """The provider's sentence for its latest word (or `word`), for the team; "" without
        one."""
        provider = get_provider(self.method)
        return provider.describe(self.word if word is None else word) if provider else ""

    def can_be_checked(self):
        """Whether the team can ask its provider about it now: it's waiting, or failed after
        reaching the provider (so it may still turn out paid), and its provider is set up here
        for the system it was made in. Never a payment the team confirms."""
        if self.team_confirms:
            return False
        may_change = self.status == PaymentStatus.WAITING or (
            self.status == PaymentStatus.FAILED and self.reached_provider()
        )
        return may_change and self.provider() is not None

    def asked_recently(self):
        """Whether its provider was asked about it in the last ASK_AGAIN_AFTER, by anyone: each
        ask can wait for the provider, so the team's check isn't pressed again and again."""
        since = timezone.now() - ASK_AGAIN_AFTER
        return self.steps.filter(kind__in=ASKS, at__gt=since).exists()

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
        Payment.objects.filter(pk=self.pk).update(word=word)
        self.word = word
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
            self.delete_receipt()
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
        self.delete_receipt()
        return True

    def delete_receipt(self):
        """Deletes the supporter's screenshot of the receipt, once its payment is checked or it's
        been kept as long as it may be. The file goes once the change is saved for good."""
        if not self.receipt:
            return
        name = self.receipt.name
        Payment.objects.filter(pk=self.pk).update(receipt="")
        delete_files_once_saved(self.receipt.storage, {name})
        self.receipt = None

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


@receiver(post_delete, sender=Payment)
def delete_payment_receipt(sender, instance, **kwargs):
    """A payment removed with its pledge leaves no screenshot behind."""
    if instance.receipt:
        delete_files_once_saved(instance.receipt.storage, {instance.receipt.name})


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


# The steps that asked a provider, whatever it answered.
ASKS = [
    StepKind.ASKED,
    StepKind.UNREACHABLE,
    StepKind.UNREADABLE,
    StepKind.REFUSED,
    StepKind.NOT_ASKED,
]

# What each step says on the pledge's page, naming the payment's provider. An answer with one of
# the provider's own words says that word's sentence instead.
STEP_SENTENCES = {
    StepKind.SENT: "Sent to {provider}.",
    StepKind.CAME_BACK: "Came back to the site.",
    StepKind.ASKED: "{provider} answered.",
    StepKind.UNREACHABLE: "Couldn't reach {provider}.",
    StepKind.UNREADABLE: "{provider} answered, but the answer wasn't understood.",
    StepKind.REFUSED: "{provider} refused to answer.",
    StepKind.NOT_ASKED: "Couldn't ask {provider}.",
    StepKind.CLAIMED: "The supporter said they paid.",
    StepKind.MARKED_PAID: "Marked paid.",
    StepKind.NOT_FOUND: "Marked not found.",
}


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

    def sentence(self):
        """What happened, in plain words for the team: "Sent to eSewa.", or for an answer the
        provider's sentence for its word ("The payer cancelled at eSewa. Nothing was taken.")."""
        if self.kind == StepKind.ASKED and (said := self.payment.word_sentence(self.word)):
            return said
        return STEP_SENTENCES[self.kind].format(provider=self.payment.get_method_display())
