import pytest
from wagtail.models import Site


@pytest.fixture
def site(db):
    """The default Site created by the home app's data migration."""
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def home_page(site):
    """The HomePage that sits at the root of the default Site."""
    return site.root_page.specific
