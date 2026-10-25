"""How often one internet connection may do something on the public site that writes or calls a
payment provider (#226), so a script can't flood a charity's pledges, merchant account or disk.

Counted in their own cache (CACHES["limits"]), in windows numbered by time. Each count is saved
with the window as its expiry: never cache.incr(), which on a file cache saves the key again with
the default timeout. A broken cache lets every try through, so giving keeps working."""

import contextlib
import ipaddress
import logging
import math
import os
import time
from typing import NamedTuple

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.filebased import FileBasedCache
from django.core.files import locks
from django.utils.cache import add_never_cache_headers

logger = logging.getLogger(__name__)

# The window this worker last said the counters broke in: the cache can't remember it.
broken_logged_in = None


class CounterCache(FileBasedCache):
    """The counters' cache in production. A past window's counters are never read again, so the
    file cache would keep them until full, then forget a random third of the files, live counts
    too. Full, this deletes the past ones first, and forgets live ones only if still full. Its
    `locked()` makes a count one step across the workers that share the files."""

    @contextlib.contextmanager
    def locked(self):
        self._createdir()
        # Not a .djcache file, so it is never counted, culled or cleared as an entry.
        with open(os.path.join(self._dir, "counting.lock"), "a") as lock_file:
            locks.lock(lock_file, locks.LOCK_EX)  # Held until the file closes.
            yield

    def _cull(self):
        filelist = self._list_cache_files()
        if len(filelist) < self._max_entries:
            return
        for name in filelist:
            try:
                with open(name, "rb") as f:
                    self._is_expired(f)
            except FileNotFoundError:
                pass  # The other worker deleted it first.
        super()._cull()


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
    address = client_address(request)
    window_number = int(time.time() // window)
    cache = caches["limits"]
    key = f"{action}:{address}:{window_number}"
    try:
        limit = settings.LIMITS[action]  # An override may leave an action out.
        if address is None:
            # Counting the proxy's address would let one script stop all giving, so the try goes
            # through, as when the counters break. Said once per window.
            if cache.add(f"no-address:{window_number}", True, timeout=window):
                logger.error(
                    "No %s on the request: nothing is counted until the proxy sends it.",
                    settings.LIMITS_ADDRESS_HEADER,
                )
            return False
        # Read, then saved: tries at the same moment must not all read the same count. Only the
        # file cache has a lock; the in-memory one is for one process, which is development.
        with getattr(cache, "locked", contextlib.nullcontext)():
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
        global broken_logged_in
        if broken_logged_in != window_number:
            broken_logged_in = window_number
            logger.exception(
                "Couldn't count a try at %s; it and others this window are let through.", action
            )
        return False
    return True


def wait_seconds():
    """What's left of this window in whole seconds rounded up: the counts start again after it."""
    window = settings.LIMITS_WINDOW
    return math.ceil(window - time.time() % window)


class Wait(NamedTuple):
    minutes: int
    seconds: int


def wait():
    """What's left of this window, in whole minutes (as the page says it) and seconds, both from
    one reading of the clock: a window ending between two readings would make them disagree."""
    seconds = wait_seconds()
    return Wait(math.ceil(seconds / 60), seconds)


def too_many(response, left):
    """Turn a page into the answer to one try too many: 429, when to try again (`left`, the
    `wait()` the page was made with), never cached."""
    response.status_code = 429
    response["Retry-After"] = str(left.seconds)
    add_never_cache_headers(response)
    return response
