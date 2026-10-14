"""Providers are found by their files in providers/, like Django finds management commands, and
a project can register its own."""

import importlib
import pkgutil

import pytest

from nepal_payments import (
    Outcome,
    PaymentProvider,
    Redirect,
    Started,
    Status,
    all_providers,
    get_provider,
    register,
    registry,
)
from nepal_payments import providers as providers_package


class ExampleProvider(PaymentProvider):
    """Not in providers/, so only registered when a test asks."""

    code = "example"
    name = "Example Pay"
    keys = ("SECRET_KEY",)

    def start(self, request):
        return Started(Redirect("https://pay.example.com/"))

    def check(self, reference, amount, provider_id=""):
        return Outcome(Status.PAID)


@pytest.fixture
def own_registry(monkeypatch):
    """Registrations made by a test end with it."""
    all_providers()
    monkeypatch.setattr(registry, "_registered", dict(registry._registered))


def provider_modules():
    return [
        importlib.import_module(f"{providers_package.__name__}.{module.name}")
        for module in pkgutil.iter_modules(providers_package.__path__)
    ]


def test_each_file_in_providers_is_one_provider():
    for module in provider_modules():
        assert len(registry.provider_classes(module)) == 1, module.__name__


def test_finds_every_provider_file():
    found = {
        provider for module in provider_modules() for provider in registry.provider_classes(module)
    }

    assert set(all_providers().values()) == found


def test_lists_providers_in_their_suggested_order(own_registry):
    first = register(type("First", (ExampleProvider,), {"code": "first", "order": -1}))
    last = register(type("Last", (ExampleProvider,), {"code": "last", "order": 1000}))

    providers = list(all_providers().values())

    assert providers[0] is first
    assert providers[-1] is last


def test_a_project_can_register_its_own_provider(own_registry):
    register(ExampleProvider)

    assert get_provider("example") is ExampleProvider


def test_register_works_as_a_class_decorator(own_registry):
    @register
    class Decorated(ExampleProvider):
        code = "decorated"

    assert get_provider("decorated") is Decorated


def test_an_unknown_code_has_no_provider():
    assert get_provider("nosuchpay") is None


def test_two_providers_cant_share_a_code(own_registry):
    register(ExampleProvider)

    with pytest.raises(ValueError, match="both use the code 'example'"):
        register(type("Copy", (ExampleProvider,), {}))


def test_registering_the_same_provider_twice_is_harmless(own_registry):
    register(ExampleProvider)

    assert register(ExampleProvider) is ExampleProvider


@pytest.mark.parametrize("code", ["", "ime_pay", "IMEPay", "1pay", "ime-pay"])
def test_a_code_is_lowercase_letters_and_digits(own_registry, code):
    """Codes are stored with payments and used in addresses and setting names."""
    with pytest.raises(ValueError, match="lowercase letters and digits"):
        register(type("Badly", (ExampleProvider,), {"code": code}))
