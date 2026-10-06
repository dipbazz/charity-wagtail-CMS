from django.db import migrations

# Editors and moderators copy a page into the other language with simple_translation's Translate
# action (#114). The copy is a draft, so editors still need a moderator to publish it.
GROUPS = ["Editors", "Moderators"]


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Editors and Moderators groups simple_translation's one permission.

    Django creates permissions after every migration has run (post_migrate), so on a new database
    it doesn't exist yet. Create it if it's missing, as that handler would.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="simple_translation", model="simpletranslation"
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename="submit_translation",
        defaults={"name": "Can submit translations"},
    )
    for group in Group.objects.filter(name__in=GROUPS):  # skips a renamed or deleted group
        group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_english_locale_without_region"),
        ("simple_translation", "0001_initial"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
