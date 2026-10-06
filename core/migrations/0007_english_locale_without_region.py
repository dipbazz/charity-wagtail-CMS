from django.db import migrations


def drop_region_from_english(apps, schema_editor):
    """Rename the en-gb locale to en, the code LANGUAGES now uses for English (#113).

    Sites made before the site had two languages created their locale from LANGUAGE_CODE en-gb.
    Left as it was, it would match no language and English pages would get no URL prefix.
    """
    Locale = apps.get_model("wagtailcore", "Locale")
    if not Locale.objects.filter(language_code="en").exists():
        Locale.objects.filter(language_code="en-gb").update(language_code="en")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_sitesettings_phone_country"),
        ("wagtailcore", "0054_initial_locale"),
    ]

    operations = [migrations.RunPython(drop_region_from_english, migrations.RunPython.noop)]
