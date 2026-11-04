from django import template

from core import honeypot as box

register = template.Library()


@register.inclusion_tag("includes/honeypot.html")
def honeypot():
    """The hidden box a script fills and a person never sees (core/honeypot.py)."""
    return {"name": box.NAME}
