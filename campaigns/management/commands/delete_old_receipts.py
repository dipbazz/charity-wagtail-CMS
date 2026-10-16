from django.core.management.base import BaseCommand
from django.utils import timezone

from campaigns.models import RECEIPTS_KEPT_FOR, Payment


class Command(BaseCommand):
    help = (
        "Delete the receipt screenshots supporters sent more than 30 days ago that nobody has "
        "checked, and any screenshot file that old that no payment points at. backup.sh runs it "
        "every night."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - RECEIPTS_KEPT_FOR
        old = Payment.objects.exclude(receipt="").filter(created_at__lt=cutoff)
        deleted = 0
        for payment in old:
            payment.delete_receipt()
            deleted += 1

        # Left behind by a request that broke after saving its file.
        storage = Payment._meta.get_field("receipt").storage
        kept = set(Payment.objects.exclude(receipt="").values_list("receipt", flat=True))
        try:
            _, names = storage.listdir("")
        except FileNotFoundError:  # no screenshot sent yet
            names = []
        for name in set(names) - kept:
            if storage.get_modified_time(name) < cutoff:
                storage.delete(name)
                deleted += 1

        self.stdout.write(f"Deleted {deleted} receipt screenshot(s) older than 30 days.")
