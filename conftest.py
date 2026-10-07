import os
from html import escape
from urllib.parse import urljoin, urlsplit

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from wagtail.models import Locale, Site


@pytest.fixture(autouse=True)
def clear_cache():
    """The test database rolls back after each test but the cache doesn't.

    Wagtail caches Site root URLs there, so a test that changes the Site would leak into the next.
    """
    yield
    cache.clear()


@pytest.fixture
def cold_cache_queries(client):
    """Count the queries a page runs on a server that has just started.

    The first visit creates any image renditions; clearing the cache then makes the counted visit
    look them up in the database, where a missing prefetch shows up as one query per image.
    """

    def count(path):
        client.get(path)
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            client.get(path)
        return len(queries)

    return count


@pytest.fixture
def site(db):
    """The default Site created by the home app's data migration."""
    return Site.objects.get(is_default_site=True)


@pytest.fixture(scope="module")
def demo_content(django_db_setup, django_db_blocker):
    """The `seed_demo` site, built once for a test module instead of once per test.

    It sits in a transaction that's rolled back when the module ends; each test's own transaction
    nests inside it, so tests can read the demo and change it freely. Tests that need an empty
    database (a first run of `seed_demo`) use `site` instead.
    """
    with django_db_blocker.unblock():
        outer = transaction.atomic()
        outer.__enter__()
        try:
            call_command("seed_demo", verbosity=0)
            yield
        finally:
            transaction.set_rollback(True)
            outer.__exit__(None, None, None)
            cache.clear()


@pytest.fixture
def demo_site(db, demo_content):
    """The default Site, holding the whole demo charity."""
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def home_page(site):
    """The HomePage that sits at the root of the default Site."""
    return site.root_page.specific


@pytest.fixture
def nepali_locale(db):
    """Nepali, the site's second language: English is the main language in tests."""
    return Locale.objects.get_or_create(language_code="ne")[0]


@pytest.fixture
def nepali_home_page(home_page, nepali_locale):
    """The home page's published Nepali translation, served at /ne/."""
    page = home_page.copy_for_translation(nepali_locale)
    page.title = "गृहपृष्ठ"
    page.save_revision().publish()
    return page


def _user_in_group(django_user_model, group_name):
    user = django_user_model.objects.create_user(username=group_name.lower(), password="x")
    user.groups.add(Group.objects.get(name=group_name))
    return user


@pytest.fixture
def editor(django_user_model):
    """A user in Wagtail's Editors group, as the charity's editors are: not a superuser."""
    return _user_in_group(django_user_model, "Editors")


@pytest.fixture
def moderator(django_user_model):
    """A user in Wagtail's Moderators group, who approves and publishes editors' work."""
    return _user_in_group(django_user_model, "Moderators")


def _chromium_can_start():
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch().close()
    except Error:
        return False
    return True


def pytest_collection_modifyitems(config, items):
    """Prepare for browser tests, or skip them where Chromium isn't installed (never in CI)."""
    browser_tests = [item for item in items if item.get_closest_marker("browser")]
    if not browser_tests:
        return
    if not os.environ.get("CI") and not _chromium_can_start():
        skip = pytest.mark.skip(
            reason="Chromium isn't installed: run `uv run playwright install chromium` once"
        )
        for item in browser_tests:
            item.add_marker(skip)
        return
    # Playwright's sync API runs an event loop in the main thread for the rest of the session once
    # a browser test starts it, and Django then refuses database calls there, from browser tests
    # (whose requests site_page answers in that thread) and every test after them. This project
    # has no async code, so allow them.
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


SITE = "http://testserver"


@pytest.fixture
def site_page(page, client):
    """A Playwright page whose requests to SITE are answered by Django's test client.

    No live server: each request runs in the test's own thread and database transaction, so
    browser tests use the normal `db` fixture and see the data they create. Static files come
    from the static finders, as in development.
    """
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.db import connections

    # Playwright calls answer() in its own context, where Django would open a second database
    # connection outside the test's transaction. Hand it the test's own, as the live server does.
    test_connections = {alias: connections[alias] for alias in connections}

    def answer(route, request):
        for alias, test_connection in test_connections.items():
            connections[alias] = test_connection
        url = urlsplit(request.url)
        if url.path.startswith(settings.STATIC_URL):
            found = finders.find(url.path.removeprefix(settings.STATIC_URL))
            return route.fulfill(path=found) if found else route.fulfill(status=404)
        path = url.path + (f"?{url.query}" if url.query else "")
        response = client.generic(
            request.method,
            path,
            data=request.post_data_buffer or b"",
            content_type=request.headers.get("content-type", ""),
        )
        if response.has_header("Location"):
            # Chromium follows a redirect from route.fulfill, but its request for the new address
            # skips this handler and goes to the network, where testserver doesn't exist. Move on
            # with an immediate refresh instead, which also replaces the history entry.
            target = escape(urljoin(request.url, response["Location"]))
            body = f'<meta http-equiv="refresh" content="0; url={target}">'
            return route.fulfill(status=200, content_type="text/html", body=body)
        body = b"".join(response.streaming_content) if response.streaming else response.content
        route.fulfill(status=response.status_code, headers=dict(response.items()), body=body)

    page.route(f"{SITE}/**", answer)
    return page
