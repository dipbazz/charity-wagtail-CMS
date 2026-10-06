"""What the charity's editors and moderators can do in the admin (#72).

Editors draft and moderators publish, as with pages. Every test logs in as a group member, not a
superuser, because a superuser can do everything and would hide a missing permission.
"""

import importlib

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

# Imported via the module: names starting with "Test" would be collected by pytest.
from core import models
from core.models import AnnouncementBanner, Partner

pytestmark = pytest.mark.django_db

TESTIMONIAL = {
    "quote": "The new well means my daughter is back at school.",
    "name": "Grace",
    "role": "",
    "photo": "",
    "action-publish": "action-publish",
}


def assert_denied(response):
    """Wagtail sends a user without permission back to the dashboard."""
    assert response.status_code == 302
    assert response.url == reverse("wagtailadmin_home")


@pytest.mark.parametrize(
    ("permission", "editors", "moderators"),
    [
        ("core.change_announcementbanner", True, True),
        ("core.add_partner", True, True),
        ("core.change_partner", True, True),
        ("core.delete_partner", True, True),
        ("core.add_testimonial", True, True),
        ("core.change_testimonial", True, True),
        ("core.delete_testimonial", True, True),
        ("core.publish_testimonial", False, True),
        ("core.lock_testimonial", False, True),
        ("core.unlock_testimonial", False, True),
        ("core.change_sitesettings", False, True),
        ("simple_translation.submit_translation", True, True),
    ],
)
def test_groups_have_the_agreed_permissions(editor, moderator, permission, editors, moderators):
    assert editor.has_perm(permission) is editors
    assert moderator.has_perm(permission) is moderators


def test_editor_can_switch_on_the_announcement_banner(client, editor):
    banner = AnnouncementBanner.load()
    client.force_login(editor)
    url = reverse("wagtailsettings:edit", args=["core", "announcementbanner", banner.pk])

    client.post(url, {"enabled": "on", "message": "Flood appeal: give now", "link_page": ""})

    banner.refresh_from_db()
    assert banner.enabled
    assert banner.message == "Flood appeal: give now"


def test_editor_cannot_open_site_settings(client, site, editor):
    client.force_login(editor)

    response = client.get(reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk]))

    assert_denied(response)


def test_moderator_can_open_site_settings(client, site, moderator):
    client.force_login(moderator)

    response = client.get(reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk]))

    assert response.status_code == 200


@pytest.mark.parametrize("url_name", ["wagtailusers_users:index", "wagtailsites:index"])
@pytest.mark.parametrize("group_member", ["editor", "moderator"])
def test_editors_and_moderators_cannot_manage_users_or_sites(
    client, request, group_member, url_name
):
    client.force_login(request.getfixturevalue(group_member))

    assert_denied(client.get(reverse(url_name)))


def test_editor_can_add_a_partner(client, editor):
    client.force_login(editor)

    client.post(
        reverse("wagtailsnippets_core_partner:add"),
        {"name": "Water Foundation", "url": "", "logo": ""},
    )

    assert Partner.objects.filter(name="Water Foundation").exists()


def test_editor_can_delete_a_partner(client, editor):
    partner = Partner.objects.create(name="Local Council")
    client.force_login(editor)

    client.post(reverse("wagtailsnippets_core_partner:delete", args=[partner.pk]))

    assert not Partner.objects.filter(pk=partner.pk).exists()


def test_editor_testimonial_stays_a_draft_even_if_they_press_publish(client, editor):
    client.force_login(editor)

    client.post(reverse("wagtailsnippets_core_testimonial:add"), TESTIMONIAL)

    testimonial = models.Testimonial.objects.get(name="Grace")
    assert not testimonial.live


def test_moderator_can_publish_a_testimonial(client, moderator):
    client.force_login(moderator)

    client.post(reverse("wagtailsnippets_core_testimonial:add"), TESTIMONIAL)

    assert models.Testimonial.objects.get(name="Grace").live


def test_migration_reuses_the_permissions_an_existing_database_already_has(
    django_user_model, editor
):
    """The live site's database has every permission row already; the migration must not
    create duplicates, only give them to the groups."""
    migration = importlib.import_module("core.migrations.0004_editor_and_moderator_permissions")
    Group.objects.get(name="Editors").permissions.clear()
    permission_count = Permission.objects.count()

    migration.grant_permissions(apps, schema_editor=None)

    assert Permission.objects.count() == permission_count
    # A fresh copy of the user: has_perm caches permissions on the instance.
    editor = django_user_model.objects.get(pk=editor.pk)
    assert editor.has_perm("core.change_announcementbanner")


def test_translation_migration_reuses_the_permission_an_existing_database_already_has(
    django_user_model, editor
):
    migration = importlib.import_module("core.migrations.0008_translation_permissions")
    Group.objects.get(name="Editors").permissions.clear()
    permission_count = Permission.objects.count()

    migration.grant_permissions(apps, schema_editor=None)

    assert Permission.objects.count() == permission_count
    editor = django_user_model.objects.get(pk=editor.pk)
    assert editor.has_perm("simple_translation.submit_translation")
