from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def create_content_locales(**kwargs):
    """Give every language in WAGTAIL_CONTENT_LANGUAGES a Locale.

    Wagtail creates only the main language's Locale, and editors can translate a page only into a
    language that has one: on a new Nepali-first site, Translate would offer no English. Run after
    every migrate, so a language added to the setting later gets one too.
    """
    from wagtail.models import Locale

    for language_code, _ in settings.WAGTAIL_CONTENT_LANGUAGES:
        Locale.objects.get_or_create(language_code=language_code)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        post_migrate.connect(create_content_locales, sender=self)
