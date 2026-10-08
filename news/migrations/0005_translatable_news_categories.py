import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from wagtail.coreutils import get_supported_content_language_variant


def put_in_main_language(apps, schema_editor):
    """Categories made before they could be translated are in the main language (#117)."""
    Locale = apps.get_model("wagtailcore", "Locale")
    NewsCategory = apps.get_model("news", "NewsCategory")
    categories = NewsCategory.objects.filter(translation_key__isnull=True)
    if not categories.exists():
        return
    locale, _ = Locale.objects.get_or_create(
        language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
    )
    for category in categories:
        category.translation_key = uuid.uuid4()
        category.locale = locale
        category.save(update_fields=["translation_key", "locale"])


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0004_editor_and_moderator_permissions"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="newscategory",
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
            model_name="newscategory",
            name="translation_key",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(put_in_main_language, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="newscategory",
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
            model_name="newscategory",
            name="translation_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AlterUniqueTogether(
            name="newscategory",
            unique_together={("translation_key", "locale")},
        ),
        # A translation keeps its category's slug, so a slug is unique in each language.
        migrations.AlterField(
            model_name="newscategory",
            name="slug",
            field=models.SlugField(),
        ),
        migrations.AddConstraint(
            model_name="newscategory",
            constraint=models.UniqueConstraint(
                fields=("slug", "locale"), name="unique_category_slug_per_language"
            ),
        ),
    ]
