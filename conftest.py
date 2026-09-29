import pytest
from django.core.cache import cache
from wagtail.models import Site


@pytest.fixture(autouse=True)
def clear_cache():
    """The test database rolls back after each test but the cache doesn't.

    Wagtail caches Site root URLs there, so a test that changes the Site would leak into the next.
    """
    yield
    cache.clear()


@pytest.fixture
def site(db):
    """The default Site created by the home app's data migration."""
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def home_page(site):
    """The HomePage that sits at the root of the default Site."""
    return site.root_page.specific
