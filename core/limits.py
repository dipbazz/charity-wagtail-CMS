"""How often one internet connection may do something on the public site that writes or calls a
payment provider (#226), so a script can't flood a charity's pledges, merchant account or disk.

Counted in their own cache (CACHES["limits"]), in windows numbered by time. Each count is saved
with the window as its expiry: never cache.incr(), which on a file cache saves the key again with
the default timeout. A broken cache lets every try through, so giving keeps working."""

import ipaddress
import logging
import math
import time

from django.conf import settings
from django.core.cache import caches
from django.utils.cache import add_never_cache_headers

logger = logging.getLogger(__name__)


def client_address(request):
    """The visitor's connection: the address Caddy sends in production (a visitor's own
    X-Forwarded-For is never read), else the one Django sees. An IPv6 address counts as its /56,
    the block a home line is often given whole, so switching between its /64s doesn't make a
    script many; one that can't be read counts as itself. None when
    the proxy's header is missing: the address Django sees is then the proxy's, everyone's."""
    header = settings.LIMITS_ADDRESS_HEADER
    if header and not request.META.get(header):
        return None
    address = request.META.get(header or "REMOTE_ADDR", "")
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return address
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/56", strict=False))
    return str(ip)


def over_limit(request, action):
    """Count this try at `action` and say whether it's one too many for this window. The first
    one too many in a window is logged, without the address, so a flood can't fill the logs."""
    window = settings.LIMITS_WINDOW
    limit = settings.LIMITS[action]
    address = client_address(request)
    window_number = int(time.time() // window)
    cache = caches["limits"]
    key = f"{action}:{address}:{window_number}"
    try:
        if address is None:
            # Counting the proxy's address would let one script stop all giving, so the try goes
            # through, as when the counters break. Said once per window.
            if cache.add(f"no-address:{window_number}", True, timeout=window):
                logger.error(
                    "No %s on the request: nothing is counted until the proxy sends it.",
                    settings.LIMITS_ADDRESS_HEADER,
                )
            return False
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=window)
        if count <= limit:
            return False
        if cache.add(f"{key}:logged", True, timeout=window):
            logger.warning(
                "Too many tries at %s from one connection: over %s in %s seconds.",
                action,
                limit,
                window,
            )
    except Exception:
        logger.exception("Couldn't count a try at %s; it was let through.", action)
        return False
    return True


def wait_minutes():
    """The window, in whole minutes rounded up, as the page says it."""
    return math.ceil(settings.LIMITS_WINDOW / 60)


def too_many(response):
    """Turn a page into the answer to one try too many: 429, when to try again, never cached."""
    response.status_code = 429
    response["Retry-After"] = str(settings.LIMITS_WINDOW)
    add_never_cache_headers(response)
    return response
