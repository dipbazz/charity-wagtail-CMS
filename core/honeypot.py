"""A box on the public forms that people never see and simple scripts fill in (#104): a send with
it filled is answered as a success, and nothing is saved or emailed. It stops scripts that fill
every box, not a careful bot (docs/contributing/security.md).

The box is in the templates with `{% honeypot %}`; the Donate page checks it in `pledge_form`,
and every form page by listing HoneypotFormMixin first."""

import logging
import time

from django.conf import settings
from django.core.cache import caches

logger = logging.getLogger(__name__)

# The hyphen keeps it apart from every editor's field (Wagtail's names never have one), and no
# word in it is one a password manager fills by name.
NAME = "hp-leave-blank"


def filled(data):
    """Whether a send has the box filled. A missing box is empty: a page cached from before it."""
    return bool(data.get(NAME))


def dropped(page):
    """Say a send to `page` was dropped, once per window, never with what was typed or from where,
    so a flood can't fill the logs. A broken cache only loses the line."""
    window = settings.LIMITS_WINDOW
    try:
        first = caches["limits"].add(
            f"honeypot:{page.pk}:{int(time.time() // window)}", True, timeout=window
        )
    except Exception:
        return
    if first:
        logger.warning(
            "Dropped a send with the hidden box filled on %s %s; no more are said this window.",
            page._meta.verbose_name,
            page.pk,
        )


class HoneypotFormMixin:
    """For a form page: listed before Wagtail's AbstractForm, so a filled box is caught first."""

    def serve(self, request, *args, **kwargs):
        if request.method == "POST" and filled(request.POST):
            dropped(self)
            return self.render_landing_page(request, None, *args, **kwargs)
        return super().serve(request, *args, **kwargs)
