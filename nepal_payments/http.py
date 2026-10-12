"""JSON over HTTPS with the standard library, so the package needs nothing else installed.

Providers reach their servers only through `request_json`, so tests can stand in for them by
replacing this one function.
"""

import http.client
import json
import urllib.error
import urllib.request

from nepal_payments.base import ProviderUnavailable

# Seconds to wait for a provider. A payer is waiting too, so don't hang on a slow one.
TIMEOUT = 10
# Some firewalls turn away Python's default User-Agent.
USER_AGENT = "nepal-payments/0.1"


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """A provider's API answers where it's asked. Following a redirect would hand the merchant's
    key, and the say on whether a payment is paid, to whatever address it names, even over plain
    http (as requests did before CVE-2018-18074). Refused, urllib raises HTTPError instead."""

    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(NoRedirects)


def request_json(url, *, method="GET", data=None, headers=None):
    """(status, JSON) from the provider, for a success or a refusal (4xx), which providers
    explain in JSON. Raises ProviderUnavailable when it can't be reached, redirects, has a server
    error (5xx) or answers with something that isn't JSON.
    """
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **({"Content-Type": "application/json"} if body is not None else {}),
            **(headers or {}),
        },
    )
    try:
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:  # urllib raises for 3xx, 4xx and 5xx answers
            with error:
                status, raw = error.code, error.read()
    except (OSError, http.client.HTTPException) as error:  # URLError and timeouts are OSErrors
        raise ProviderUnavailable(f"{method} {url} failed: {error}") from error
    if 300 <= status < 400 or status >= 500:
        raise ProviderUnavailable(f"{method} {url} answered {status}.")
    try:
        return status, json.loads(raw)
    # Nested deeper than Python recurses is RecursionError, not a ValueError.
    except (ValueError, RecursionError) as error:
        raise ProviderUnavailable(f"{method} {url} answered {status}, not in JSON.") from error
