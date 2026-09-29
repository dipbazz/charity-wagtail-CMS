from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site

DEFAULT_PORTS = {"http": 80, "https": 443}


class Command(BaseCommand):
    help = "Point the default Wagtail Site at settings.SITE_URL. Safe to run on every deploy."

    def handle(self, *args, **options):
        hostname, port = self.parse(settings.SITE_URL)

        site = Site.objects.get(is_default_site=True)
        site.hostname = hostname
        site.port = port
        site.save()

        self.stdout.write(f"Default site now builds full URLs from {site.root_url}")

    def parse(self, url):
        """Split SITE_URL into the hostname and port a Wagtail Site stores."""
        parts = urlsplit(url)
        try:
            port = parts.port or DEFAULT_PORTS.get(parts.scheme)
        except ValueError:
            port = None

        # A Site has no scheme field: Wagtail uses https for port 443 and http for anything else.
        if (
            parts.scheme not in DEFAULT_PORTS
            or not parts.hostname
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
            or (port == 443) != (parts.scheme == "https")
        ):
            raise CommandError(
                f"SITE_URL must be http(s)://hostname with an optional port and no path, "
                f"and https only on port 443; got {url!r}."
            )
        return parts.hostname, port
