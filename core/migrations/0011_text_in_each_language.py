import django.db.models.deletion
import modelcluster.fields
from django.conf import settings
from django.db import migrations, models
from wagtail.coreutils import get_supported_content_language_variant


def move_text_into_rows(apps, schema_editor):
    """Keep the footer address and the banner's message as the main language's text (#117).

    The banner becomes a setting of each Site. The one banner there was is given to every Site,
    so each keeps showing what it showed before.
    """
    Locale = apps.get_model("wagtailcore", "Locale")
    Site = apps.get_model("wagtailcore", "Site")
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettingsText = apps.get_model("core", "SiteSettingsText")
    AnnouncementBanner = apps.get_model("core", "AnnouncementBanner")
    AnnouncementBannerText = apps.get_model("core", "AnnouncementBannerText")

    def main_locale():
        return Locale.objects.get_or_create(
            language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
        )[0]

    for site_settings in SiteSettings.objects.exclude(address=""):
        SiteSettingsText.objects.create(
            settings=site_settings, locale=main_locale(), address=site_settings.address
        )

    banner = AnnouncementBanner.objects.order_by("pk").first()
    if banner is None:
        return
    AnnouncementBanner.objects.exclude(pk=banner.pk).delete()
    sites = list(Site.objects.order_by("-is_default_site", "pk"))
    if not sites:
        banner.delete()
        return
    for site in sites:
        banner.site = site
        banner.save()
        if banner.message:
            AnnouncementBannerText.objects.create(
                banner=banner, locale=main_locale(), message=banner.message
            )
        banner.pk = None  # the next Site gets a copy


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_translatable_partners_and_testimonials"),
        ("wagtailcore", "0098_apitoken"),
        migrations.swappable_dependency(settings.WAGTAIL_PAGE_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettingsText",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "address",
                    models.TextField(blank=True, help_text="Shown in the footer of every page."),
                ),
                (
                    "locale",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="wagtailcore.locale",
                        verbose_name="language",
                    ),
                ),
                (
                    "settings",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="texts",
                        to="core.sitesettings",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("settings", "locale"), name="one_site_settings_text_per_language"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="AnnouncementBannerText",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("message", models.CharField(max_length=255)),
                (
                    "banner",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="texts",
                        to="core.announcementbanner",
                    ),
                ),
                (
                    "locale",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="wagtailcore.locale",
                        verbose_name="language",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("banner", "locale"), name="one_banner_text_per_language"
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="announcementbanner",
            name="site",
            field=models.OneToOneField(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="wagtailcore.site",
            ),
        ),
        migrations.RunPython(move_text_into_rows, migrations.RunPython.noop),
        migrations.RemoveField(model_name="announcementbanner", name="message"),
        migrations.RemoveField(model_name="sitesettings", name="address"),
        migrations.AlterField(
            model_name="announcementbanner",
            name="site",
            field=models.OneToOneField(
                editable=False,
                on_delete=django.db.models.deletion.CASCADE,
                to="wagtailcore.site",
            ),
        ),
        migrations.AlterField(
            model_name="announcementbanner",
            name="link_page",
            field=models.ForeignKey(
                blank=True,
                help_text="Readers of another language go to its translation, once it's published.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.WAGTAIL_PAGE_MODEL,
            ),
        ),
    ]
