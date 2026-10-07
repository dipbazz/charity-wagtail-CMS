"""`seed_demo` on a site with no demo content yet.

Separate from test_seed_demo.py, whose tests share one seeded demo site for the whole module.
"""

import pytest
from django.core.management import CommandError, call_command

from campaigns.models import CampaignPage

pytestmark = pytest.mark.django_db


def test_explains_how_to_seed_a_site_whose_main_language_is_nepali(
    home_page, nepali_locale, settings
):
    # A new deployment opens in Nepali, so its home page is in the Nepali locale.
    settings.LANGUAGE_CODE = "ne"
    home_page.locale = nepali_locale
    home_page.save()

    with pytest.raises(CommandError, match="DJANGO_LANGUAGE_CODE=en"):
        call_command("seed_demo", verbosity=0)

    assert not CampaignPage.objects.exists()
