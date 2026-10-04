from django.db import migrations

# Editors draft and moderators publish, as with pages (#72). The banner is direct for editors
# because an emergency message can't wait for approval; testimonials quote real people, so a
# moderator signs them off. Site settings (charity number, donate page) are moderators' only.
GROUP_PERMISSIONS = {
    "Editors": {
        "announcementbanner": ["change"],
        "partner": ["add", "change", "delete"],
        "testimonial": ["add", "change", "delete"],
    },
    "Moderators": {
        "announcementbanner": ["change"],
        "partner": ["add", "change", "delete"],
        "testimonial": ["add", "change", "delete", "publish", "lock", "unlock"],
        "sitesettings": ["change"],
    },
}


def grant_permissions(apps, schema_editor):
    """Give Wagtail's Editors and Moderators groups permissions for core's content.

    Django and Wagtail create permissions after every migration has run (post_migrate), so on a
    new database they don't exist yet. Create any that are missing, as those handlers would.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, models in GROUP_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group is None:  # renamed or deleted on this site
            continue
        for model_name, actions in models.items():
            model = apps.get_model("core", model_name)
            content_type, _ = ContentType.objects.get_or_create(
                app_label="core", model=model_name
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
        ("core", "0003_partner_and_testimonial_snippets"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
