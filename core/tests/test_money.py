from decimal import Decimal

import pytest
from django.template import Context, Template
from django.test import RequestFactory

from core.models import SiteSettings
from core.money import format_money

pytestmark = pytest.mark.django_db


class TestFormatMoney:
    def test_rupees_with_thousands_grouping(self):
        assert format_money(1500, "NPR") == "Rs 1,500"

    def test_pounds(self):
        assert format_money(10000, "GBP") == "£10,000"

    def test_whole_amounts_have_no_decimals(self):
        assert format_money(Decimal("2500.00"), "NPR") == "Rs 2,500"

    @pytest.mark.parametrize(
        ("amount", "expected"),
        [
            (999, "Rs 999"),
            (1500, "Rs 1,500"),
            (100000, "Rs 1,00,000"),
            (4687500, "Rs 46,87,500"),
            (12000000, "Rs 1,20,00,000"),
        ],
    )
    def test_rupees_are_grouped_in_lakhs_and_crores(self, amount, expected):
        assert format_money(amount, "NPR") == expected

    def test_pounds_keep_groups_of_three(self):
        assert format_money(4687500, "GBP") == "£4,687,500"

    def test_part_amounts_round_half_up(self):
        assert format_money(Decimal("2500.50"), "NPR") == "Rs 2,501"


class TestMoneyTag:
    def render(self, site, amount):
        request = RequestFactory().get("/", SERVER_NAME=site.hostname, SERVER_PORT=site.port)
        template = Template("{% load money_tags %}{% money amount %}")
        return template.render(Context({"request": request, "amount": amount}))

    def test_new_sites_show_rupees(self, site):
        assert self.render(site, 1500) == "Rs 1,500"

    def test_uses_the_currency_chosen_in_site_settings(self, site):
        settings = SiteSettings.for_site(site)
        settings.currency = "GBP"
        settings.save()

        assert self.render(site, 1500) == "£1,500"
