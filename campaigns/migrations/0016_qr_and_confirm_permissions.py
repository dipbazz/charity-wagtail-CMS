from django.db import migrations

# Moderators publish and look after the money, as they do for site settings: only they add,
# change and remove the QR codes supporters pay to (an editor's change would send gifts to another
# account), and only they mark a QR payment paid, or not found. Editors still only read pledges.
GROUP_PERMISSIONS = {
    "Moderators": {
        "qrcode": [
            ("add_qrcode", "Can add QR code"),
            ("change_qrcode", "Can change QR code"),
            ("delete_qrcode", "Can delete QR code"),
            ("view_qrcode", "Can view QR code"),
        ],
        "pledge": [("confirm_payment", "Can confirm payments")],
    },
}


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Moderators group its permissions for QR codes and confirming payments.

    Django creates permissions after every migration has run (post_migrate), so on a new
    database they don't exist yet. Create any that are missing, as that handler would.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, models in GROUP_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group is None:  # renamed or deleted on this site
            continue
        for model_name, actions in models.items():
            content_type, _ = ContentType.objects.get_or_create(
                app_label="campaigns", model=model_name
            )
            for codename, name in actions:
                permission, _ = Permission.objects.get_or_create(
                    content_type=content_type, codename=codename, defaults={"name": name}
                )
                group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0015_qr_codes"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
