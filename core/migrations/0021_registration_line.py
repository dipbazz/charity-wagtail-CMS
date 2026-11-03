from django.conf import settings
from django.db import migrations, models

# The footer's words before #172, in each language, as its readers saw them, frozen here so a
# later change to the translations can't change what this migration writes.
REGISTERED_CHARITY_NUMBER = {
    "en": "Registered charity number {number}.",
    "ne": "दर्ता भएको परोपकारी संस्था नम्बर {number}।",
}


def move_number_into_rows(apps, schema_editor):
    """Keep each site's charity number in its footer, now as the registration line (#172).

    Each language's row gets the number in that language's words, so the footer reads as before
    in every language, and a moderator's next save is accepted. A site without a number gets
    nothing: its registration line is asked for at its next save.
    """
    Locale = apps.get_model("wagtailcore", "Locale")
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettingsText = apps.get_model("core", "SiteSettingsText")

    for site_settings in SiteSettings.objects.all():
        number = site_settings.charity_number.strip()
        if not number:
            continue
        for code, _name in settings.WAGTAIL_CONTENT_LANGUAGES:
            # `core` gives every language a Locale after each migrate; until then one added to
            # the setting since the last migrate may have none.
            locale = Locale.objects.get_or_create(language_code=code)[0]
            # Only English and Nepali exist; a language added later starts from the English.
            words = REGISTERED_CHARITY_NUMBER.get(code, REGISTERED_CHARITY_NUMBER["en"])
            SiteSettingsText.objects.update_or_create(
                settings=site_settings,
                locale=locale,
                defaults={"registration_line": words.format(number=number)},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0020_sitesettingstext_every_language_help"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettingstext",
            name="registration_line",
            field=models.TextField(
                blank=True,
                help_text="Shown under your charity's name at the bottom of every page, so donors "
                "can check it's registered. Copy the numbers from your registration certificates, "
                "each on its own line, and leave out any you don't have. In Nepal, for example: "
                "“Registered with the District Administration Office, Kathmandu, no. 1234”, then "
                "“Social Welfare Council affiliation no. 5678”, then “PAN 301234567”; in Nepali, "
                "the first line could read “जिल्ला प्रशासन कार्यालय, काठमाडौंमा दर्ता नं. 1234”. "
                "It must be written for every language before these settings can be saved. Don't "
                "type a placeholder such as “TBC”: every page shows it.",
                max_length=500,
            ),
        ),
        # Going back is the previous release and the backup (docs/hosting.md).
        migrations.RunPython(move_number_into_rows, migrations.RunPython.noop),
        migrations.RemoveField(model_name="sitesettings", name="charity_number"),
    ]
