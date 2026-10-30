"""A new charity's day-one home page at the six widths, in both languages (#175).

In its own module because the layout check's demo site has pages, so `new_site` would refuse it.
"""

import pytest
from django.core.management import call_command

from charity.tests.test_demo_layout_browser import layout_problems

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


@pytest.mark.parametrize("path", ["/", "/ne/"])
def test_the_day_one_home_page_fits_and_can_be_tapped_at_every_width(site_page, site, path):
    call_command(
        "new_site",
        name_en="Bright Future",
        name_ne="उज्यालो भविष्य",
        email="hello@brightfuture.example",
        phone="+977 1 400 0000",
    )

    problems = layout_problems(site_page, path)

    assert not problems, f"{path}\n" + "\n".join(problems)
