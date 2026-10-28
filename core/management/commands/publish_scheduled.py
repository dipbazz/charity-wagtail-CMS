from django.utils import timezone
from wagtail.management.commands import publish_scheduled
from wagtail.models import Page

from core.publishing import refusals_to_unpublish, refuse_expiry


class Command(publish_scheduled.Command):
    """Wagtail's publish_scheduled, but a privacy notice due to expire stays live while forms link
    to it (#175): its expiry is cleared first, so Wagtail's loop leaves it, and the server log and
    its History say why. A dry run only says so. Refused publishing is `PublishGuardMixin`'s."""

    def handle(self, *args, **options):
        expired = list(Page.objects.live().filter(expire_at__lt=timezone.now()))
        for refusal in refusals_to_unpublish(expired):
            if options["dryrun"]:
                reasons = " ".join(refusal.reasons)
                self.stdout.write(f"“{refusal.page.title}” won't be unpublished. {reasons}")
            else:
                refuse_expiry(refusal)
        super().handle(*args, **options)
