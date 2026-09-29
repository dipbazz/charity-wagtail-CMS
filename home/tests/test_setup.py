from django.conf import settings

from home.models import HomePage


def test_tests_run_against_test_settings():
    assert settings.SETTINGS_MODULE == "charity.settings.test"


def test_default_site_root_is_a_home_page(home_page):
    assert isinstance(home_page, HomePage)


def test_site_root_serves_home_page(client, home_page):
    response = client.get("/")

    assert response.status_code == 200
    assert response.context["page"] == home_page


def test_wagtail_admin_login_is_available(client, db):
    response = client.get("/admin/login/")

    assert response.status_code == 200
