"""Pledges in the admin: listed, filtered and exported; never added, edited or deleted by the team.

Logged in as group members, not superusers, except where only a superuser may act.
"""

import importlib

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from campaigns.models import CampaignPage, Frequency, Pledge

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


def test_a_superuser_can_delete_a_pledge(admin_client, sent_pledge):
    admin_client.post(reverse("pledges:delete", args=[sent_pledge.pk]))

    assert not Pledge.objects.filter(pk=sent_pledge.pk).exists()


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
