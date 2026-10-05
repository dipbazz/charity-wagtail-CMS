from django import template

from core.models import SiteSettings
from core.money import format_money

register = template.Library()


@register.simple_tag(takes_context=True)
def money(context, amount):
    """An amount in the currency chosen in Site settings, e.g. "Rs 1,500"."""
    currency = SiteSettings.for_request(context["request"]).currency
    return format_money(amount, currency)
