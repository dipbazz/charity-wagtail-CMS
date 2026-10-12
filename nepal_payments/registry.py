"""Finds the providers in `providers/`, the way Django finds management commands: a file there is
a provider. A project can add its own with `register()`."""

import functools
import importlib
import inspect
import pkgutil
import re

from nepal_payments.base import PaymentProvider

CODE = re.compile(r"[a-z][a-z0-9]*")

_registered = {}


def register(provider):
    """Add a provider class, such as a project's own. Also works as a class decorator."""
    if not CODE.fullmatch(getattr(provider, "code", "")):
        raise ValueError(
            f"{provider.__name__}.code must be lowercase letters and digits, starting with a "
            "letter, such as 'esewa'."
        )
    registered = _registered.setdefault(provider.code, provider)
    if registered is not provider:
        raise ValueError(
            f"{provider.__name__} and {registered.__name__} both use the code "
            f"{provider.code!r}; each provider needs its own."
        )
    return provider


def provider_classes(module):
    """The providers a module defines, leaving out any it imports."""
    return [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, PaymentProvider)
        and value.__module__ == module.__name__
        and not inspect.isabstract(value)
    ]


@functools.cache
def _discover():
    from nepal_payments import providers as package

    for module in pkgutil.iter_modules(package.__path__):
        imported = importlib.import_module(f"{package.__name__}.{module.name}")
        for provider in provider_classes(imported):
            register(provider)


def all_providers():
    """Every provider by its code, in the order they suggest (`order`, then code)."""
    _discover()
    return dict(sorted(_registered.items(), key=lambda item: (item[1].order, item[0])))


def get_provider(code):
    """The provider with this code, or None."""
    return all_providers().get(code)
