import runpy

from django.conf import settings


def test_debug_toolbar_runs_in_development():
    dev = runpy.run_module("charity.settings.dev")

    assert "debug_toolbar" in dev["INSTALLED_APPS"]
    assert dev["MIDDLEWARE"][0] == "debug_toolbar.middleware.DebugToolbarMiddleware"
    assert "127.0.0.1" in dev["INTERNAL_IPS"]


def test_debug_toolbar_is_left_out_of_tests():
    # Production gets the same guarantee in test_production_settings.py.
    assert "debug_toolbar" not in settings.INSTALLED_APPS
    assert not any("debug_toolbar" in m for m in settings.MIDDLEWARE)
