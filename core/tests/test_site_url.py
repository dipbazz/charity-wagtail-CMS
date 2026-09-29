import io

import pytest
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


def update_site_url():
    call_command("update_site_url", stdout=io.StringIO())


@pytest.mark.parametrize(
    ("url", "hostname", "port"),
    [
        ("http://localhost:8000", "localhost", 8000),
        ("http://example.org", "example.org", 80),
        ("https://brightwell.example", "brightwell.example", 443),
        ("https://brightwell.example/", "brightwell.example", 443),
    ],
)
def test_points_the_default_site_at_the_site_url(settings, site, url, hostname, port):
    settings.SITE_URL = url

    update_site_url()

    site.refresh_from_db()
    assert (site.hostname, site.port) == (hostname, port)


@pytest.mark.parametrize(
    "url",
    [
        "brightwell.example",
        "ftp://brightwell.example",
        "https://brightwell.example/charity/",
        # Wagtail treats every port except 443 as http, so it can't store https on another port.
        "https://brightwell.example:8443",
    ],
)
def test_rejects_urls_a_wagtail_site_cannot_represent(settings, site, url):
    settings.SITE_URL = url

    with pytest.raises(CommandError, match="SITE_URL"):
        update_site_url()


def test_full_urls_use_the_site_url(client, settings, home_page):
    settings.SITE_URL = "https://brightwell.example"
    update_site_url()

    assert home_page.full_url == "https://brightwell.example/"
    assert "<loc>https://brightwell.example/</loc>" in client.get("/sitemap.xml").content.decode()
