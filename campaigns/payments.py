"""The payment providers this installation offers, set up with its own keys.

The providers themselves are in `nepal_payments`, which knows nothing of Django or this site. Each
is offered once all its keys are in PAYMENT_KEYS (from DJANGO_PAYMENT_<PROVIDER>_<KEY>), and takes
real money only when LIVE_PAYMENTS is on.
"""

from django.conf import settings
from django.core import checks

# The prefix the settings read keys with, so the checks' hints name the variables they read.
from charity.settings.payments import PREFIX
from nepal_payments import all_providers, get_provider


def setting_name(provider, key):
    """The name a provider's key has in PAYMENT_KEYS, e.g. "KHALTI_SECRET_KEY"."""
    return f"{provider.code.upper()}_{key}"


def keys_for(provider):
    """This installation's keys for a provider, as it asks for them."""
    given = settings.PAYMENT_KEYS
    return {key: given.get(setting_name(provider, key), "") for key in provider.keys}


def is_set_up(provider):
    return all(keys_for(provider).values())


def providers_for(currency, amount=None):
    """The providers offered here that take this currency (and amount), in their order."""
    return [
        provider
        for provider in all_providers().values()
        if is_set_up(provider)
        and currency in provider.currencies
        and (amount is None or provider.accepts(currency, amount))
    ]


def provider_for(code):
    """The provider with this code, ready to use with this installation's keys; None if it isn't
    offered here."""
    provider = get_provider(code)
    if provider is None or not is_set_up(provider):
        return None
    return provider(live=settings.LIVE_PAYMENTS, **keys_for(provider))


# The ways to pay a pledge, each with its own page after the pay page's choices.
ONLINE = "online"
IN_PERSON = "in-person"


def ways_to_pay(providers, site_settings):
    """The ways a pledge can be paid here, in the order they're offered: online with any of
    `providers` (from providers_for(), so the pay buttons come from the same list), and in person
    when Site settings say the charity takes gifts at its office and give an address or phone to
    find it. "Not ready to pay yet" isn't one: it's always offered."""
    ways = []
    if providers:
        ways.append(ONLINE)
    if site_settings.takes_gifts_in_person and (site_settings.address or site_settings.phone):
        ways.append(IN_PERSON)
    return ways


def method_choices():
    """Every provider, for a payment's `method`. A function, so migrations name it rather than
    copy its list, and a new provider needs no migration."""
    return [(code, provider.name) for code, provider in all_providers().items()]


@checks.register()
def check_payment_keys(app_configs, **kwargs):
    """A provider with only some of its keys stops the site, rather than quietly not being
    offered; a key no provider uses (a typo, say) is a warning."""
    messages = []
    known = set()
    for provider in all_providers().values():
        names = {key: setting_name(provider, key) for key in provider.keys}
        known.update(names.values())
        missing = [PREFIX + name for name in names.values() if not settings.PAYMENT_KEYS.get(name)]
        if missing and len(missing) < len(names):
            messages.append(
                checks.Error(
                    f"{provider.name} has only some of its keys, so it can't take payments.",
                    hint=f"Set {', '.join(missing)}, or remove its other keys.",
                    id="campaigns.E001",
                )
            )
    for name in sorted(set(settings.PAYMENT_KEYS) - known):
        messages.append(
            checks.Warning(
                f"{PREFIX}{name} isn't a key of any payment provider.",
                hint="Check its spelling against docs/hosting.md.",
                id="campaigns.W001",
            )
        )
    return messages
