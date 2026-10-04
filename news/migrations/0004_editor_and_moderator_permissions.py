from django.db import migrations

# Editors and moderators both manage news categories (#72).
GROUPS = ["Editors", "Moderators"]
ACTIONS = ["add", "change", "delete"]


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Editors and Moderators groups permissions for news categories.

    Django creates permissions after every migration has run (post_migrate), so on a new
    database they don't exist yet. Create any that are missing, as Django would.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    NewsCategory = apps.get_model("news", "NewsCategory")

    content_type, _ = ContentType.objects.get_or_create(app_label="news", model="newscategory")
    permissions = [
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_newscategory",
            defaults={"name": f"Can {action} {NewsCategory._meta.verbose_name_raw}"},
        )[0]
        for action in ACTIONS
    ]
    for group in Group.objects.filter(name__in=GROUPS):
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0003_highlight_rich_text"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
