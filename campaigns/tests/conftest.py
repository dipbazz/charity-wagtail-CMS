"""Fixtures shared by the Donate page's tests and its browser tests."""

import datetime
from decimal import Decimal

import pytest
from wagtail.models import PageViewRestriction

from campaigns.tests.factories import (
    CampaignIndexPageFactory,
    CampaignPageFactory,
    DonatePageFactory,
)
from nepal_payments import (
    Outcome,
    PaymentProvider,
    Redirect,
    Started,
    Status,
    all_providers,
    register,
    registry,
)

TODAY = datetime.date.today()


class FakePay(PaymentProvider):
    """A payment provider that does what a test tells it, and remembers what it was asked, so
    the pay flow is tested apart from any real provider. Set up by the `fake_provider` fixture."""

    code = "fakepay"
    name = "Fake Pay"
    keys = ("SECRET_KEY",)
    min_amount = Decimal(10)
    statuses = {
        "DONE": (Status.PAID, "Fake Pay says it's paid."),
        "PENDING": (Status.WAITING, "Fake Pay hasn't finished the payment yet."),
        "CANCELLED": (Status.FAILED, "The payer cancelled at Fake Pay. Nothing was taken."),
    }

    @classmethod
    def reset(cls):
        cls.redirect = Redirect("https://pay.example.com/fakepay/")
        cls.outcome = Outcome(Status.PAID, "FAKE-123", word="DONE")
        cls.failure = None  # an error start() and check() raise instead
        cls.started = []  # the PaymentRequests start() was given
        cls.checked = []  # what check() was asked

    def start(self, request):
        FakePay.started.append(request)
        if FakePay.failure:
            raise FakePay.failure
        return Started(FakePay.redirect, provider_id="fake-id")

    def check(self, reference, amount, provider_id=""):
        FakePay.checked.append((reference, amount, provider_id))
        if FakePay.failure:
            raise FakePay.failure
        return FakePay.outcome


@pytest.fixture
def fake_provider(settings, monkeypatch):
    """FakePay as the only provider set up here, in its test system."""
    all_providers()  # finds the real ones first, so they're kept after this test
    monkeypatch.setattr(registry, "_registered", dict(registry._registered))
    register(FakePay)
    settings.PAYMENT_KEYS = {"FAKEPAY_SECRET_KEY": "test-secret"}
    settings.LIVE_PAYMENTS = False
    FakePay.reset()
    return FakePay


@pytest.fixture
def appeals(home_page):
    index = CampaignIndexPageFactory(parent=home_page, title="Appeals", slug="appeals")
    CampaignPageFactory(parent=index, title="Flood relief", slug="flood-relief")
    CampaignPageFactory(
        parent=index,
        title="Last year's appeal",
        slug="last-year",
        start_date=TODAY - datetime.timedelta(days=400),
        end_date=TODAY - datetime.timedelta(days=30),
    )
    private = CampaignPageFactory(parent=index, title="Trustees' appeal", slug="trustees")
    PageViewRestriction.objects.create(
        page=private, restriction_type=PageViewRestriction.PASSWORD, password="trustees"
    )
    return index


@pytest.fixture
def donate_page(home_page, appeals):
    page = DonatePageFactory(
        parent=home_page,
        body=[("paragraph", "<p>Where every Rs 100 goes</p>")],
    )
    page.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
    page.donation_amounts.create(amount=10000, impact="Water purification for a month")
    page.save_revision().publish()
    return page
