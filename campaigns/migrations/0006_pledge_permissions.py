from django.db import migrations

# Pledges come from the site and hold supporters' personal details. The team can read and export
# them, but nobody adds or edits them, and only a superuser can delete one: a deleted pledge
# loses the record of a donation.
GROUP_PERMISSIONS = {
    "Editors": {"pledge": ["view"]},
    "Moderators": {"pledge": ["view"]},
}


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Editors and Moderators groups permission to view pledges.

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
            model = apps.get_model("campaigns", model_name)
            content_type, _ = ContentType.objects.get_or_create(
                app_label="campaigns", model=model_name
            )
            for action in actions:
                permission, _ = Permission.objects.get_or_create(
                    content_type=content_type,
                    codename=f"{action}_{model_name}",
                    defaults={"name": f"Can {action} {model._meta.verbose_name_raw}"},
                )
                group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0005_donate_page_and_pledges"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
