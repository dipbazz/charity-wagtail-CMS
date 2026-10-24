import secrets

from django.db import migrations, models

# Editors and moderators both read pledges, so either can take a gift's public page down (a
# made-up name, say) and put it back (#100).
GROUP_PERMISSIONS = {
    "Editors": [("stop_showing_gift", "Can stop showing a gift on the website")],
    "Moderators": [("stop_showing_gift", "Can stop showing a gift on the website")],
}


def code_existing_pledges(apps, schema_editor):
    """Give every pledge sent before gift pages a gift code of its own."""
    Pledge = apps.get_model("campaigns", "Pledge")
    taken = set()
    for pledge in Pledge.objects.filter(gift_code__isnull=True).only("pk"):
        code = secrets.token_urlsafe(9)
        while code in taken:
            code = secrets.token_urlsafe(9)
        taken.add(code)
        Pledge.objects.filter(pk=pledge.pk).update(gift_code=code)


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Editors and Moderators groups the permission to stop showing a gift.

    Django creates permissions after every migration has run (post_migrate), so on a new
    database it doesn't exist yet. Create it if it's missing, as that handler would.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(app_label="campaigns", model="pledge")
    for group_name, actions in GROUP_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group is None:  # renamed or deleted on this site
            continue
        for codename, name in actions:
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type, codename=codename, defaults={"name": name}
            )
            group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
        ("campaigns", "0016_payment_word"),
    ]

    operations = [
        # Added empty, filled, then made unique: a unique column can't be added to a table with
        # rows in it until each row has its own value.
        migrations.AddField(
            model_name="pledge",
            name="gift_code",
            field=models.CharField(editable=False, max_length=12, null=True),
        ),
        migrations.RunPython(code_existing_pledges, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pledge",
            name="gift_code",
            field=models.CharField(editable=False, max_length=12, unique=True),
        ),
        migrations.AddField(
            model_name="pledge",
            name="show_on_website_changed_at",
            field=models.DateTimeField(
                blank=True, editable=False, null=True, verbose_name="show on website changed"
            ),
        ),
        migrations.AddField(
            model_name="pledge",
            name="hidden_by_team",
            field=models.BooleanField(
                default=False, editable=False, verbose_name="taken down by the team"
            ),
        ),
        migrations.AlterField(
            model_name="pledge",
            name="show_on_website",
            field=models.BooleanField(
                default=False,
                help_text="Agreed to their name, appeal and date being shown on a page they can "
                "share and in the list of recent supporters once they say they've paid, and the "
                "amount once it's received.",
            ),
        ),
        migrations.AlterModelOptions(
            name="pledge",
            options={
                "ordering": ["-created_at"],
                "permissions": [
                    ("confirm_payment", "Can confirm payments"),
                    ("stop_showing_gift", "Can stop showing a gift on the website"),
                ],
            },
        ),
        migrations.RunPython(grant_permissions, migrations.RunPython.noop),
    ]
