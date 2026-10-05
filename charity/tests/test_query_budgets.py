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
BUDGETS = {
    "/": 17,
    "/appeals/": 15,
    "/appeals/flood-relief/": 15,
    "/news/": 18,
    "/news/feed/": 10,
    "/about/": 11,
    "/volunteer/": 12,
    "/donate/": 14,
    "/donate/?appeal=flood-relief&amount=2500": 15,
    "/search/?query=water": 21,
    "/api/v2/pages/?type=campaigns.CampaignPage&fields=*": 18,
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
