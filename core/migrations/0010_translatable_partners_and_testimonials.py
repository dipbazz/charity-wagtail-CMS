import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from wagtail.coreutils import get_supported_content_language_variant

MODELS = ["Partner", "Testimonial"]


def put_in_main_language(apps, schema_editor):
    """Partners and testimonials written before they could be translated are in the main language.

    Each gets its own translation key, so each can be translated on its own (#117).
    """
    Locale = apps.get_model("wagtailcore", "Locale")
    for name in MODELS:
        model = apps.get_model("core", name)
        rows = model.objects.filter(translation_key__isnull=True)
        if not rows.exists():
            continue
        locale, _ = Locale.objects.get_or_create(
            language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
        )
        for row in rows:
            row.translation_key = uuid.uuid4()
            row.locale = locale
            row.save(update_fields=["translation_key", "locale"])


def add_nullable_fields(model_name):
    return [
        migrations.AddField(
            model_name=model_name,
            name="locale",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="translation_key",
            field=models.UUIDField(editable=False, null=True),
        ),
    ]


def require_fields(model_name):
    return [
        migrations.AlterField(
            model_name=model_name,
            name="locale",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        migrations.AlterField(
            model_name=model_name,
            name="translation_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AlterUniqueTogether(
            name=model_name,
            unique_together={("translation_key", "locale")},
        ),
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_sitesettings_privacy_page"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        *add_nullable_fields("partner"),
        *add_nullable_fields("testimonial"),
        migrations.RunPython(put_in_main_language, migrations.RunPython.noop),
        *require_fields("partner"),
        *require_fields("testimonial"),
    ]
