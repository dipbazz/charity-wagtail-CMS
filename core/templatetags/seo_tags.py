from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_url(context, url):
    """Make a URL absolute for the current request; absolute URLs (e.g. a CDN) pass through."""
    return context["request"].build_absolute_uri(url)
