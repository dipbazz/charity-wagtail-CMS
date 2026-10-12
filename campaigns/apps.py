from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "campaigns"

    def ready(self):
        # Registers the check that stops the site when a payment provider is half set up.
        from campaigns import payments  # noqa: F401
