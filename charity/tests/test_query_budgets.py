"""How many database queries each kind of page may run, on the full demo site.

A change that adds queries (for example one per card in a listing) fails here with the page and
the count. If a change needs more queries on purpose, raise the budget in the same pull request
and say why; if it saves queries, lower the budget.
"""

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db

# The card listings (/, /appeals/, /news/) each spend one query prefetching card image renditions
# (core.images.with_card_images). On a just-started server that one query replaces one per card.
# Public listings (/, /appeals/, /news/ and its feed) also spend one query reading the page privacy
# restrictions, so pages behind a password or login stay out of them (`.public()`, #47).
# /donate/ spends three more than /about/: its suggested amounts, and the open appeals offered in
# the form with their privacy restrictions (#31). A link naming an appeal costs one more, to check
# that appeal is on offer before preselecting it.
# Every page spends one query on the language being read: Wagtail looks up its Locale to find the
# home page in that language (#113). A page in the second language spends one more, finding that
# home page's translation. The API lists the Nepali flood appeal too, so it spends one more on it.
# A second-language appeal spends one more looking for the Donate page in its language (#114).
# Every page and search spend one query on the language switcher and hreflang links: the live home
# page and the live translations of the page being read, in every language (#115).
BUDGETS = {
    "/": 19,
    "/appeals/": 17,
    "/appeals/flood-relief/": 17,
    "/news/": 20,
    "/news/feed/": 11,
    "/about/": 13,
    "/volunteer/": 14,
    "/donate/": 16,
    "/donate/?appeal=flood-relief&amount=2500": 17,
    "/search/?query=water": 22,
    "/api/v2/pages/?type=campaigns.CampaignPage&fields=*": 19,
    "/ne/": 17,
    "/ne/appeals/": 18,
    "/ne/appeals/flood-relief/": 19,
    "/ne/news/": 21,
}


@pytest.fixture
def demo_site(site):
    call_command("seed_demo", verbosity=0)


@pytest.mark.parametrize(("path", "budget"), BUDGETS.items())
def test_page_stays_within_its_query_budget(
    client, demo_site, django_assert_max_num_queries, path, budget
):
    # The first visit creates image renditions and fills caches; budget the visits after it.
    assert client.get(path).status_code == 200

    with django_assert_max_num_queries(budget):
        client.get(path)
