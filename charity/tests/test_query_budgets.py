"""How many database queries each kind of page may run, on the full demo site.

A change that adds queries (for example one per card in a listing) fails here with the page and
the count. If a change needs more queries on purpose, raise the budget in the same pull request
and say why; if it saves queries, lower the budget.
"""

import pytest

from campaigns.models import Pledge

pytestmark = pytest.mark.django_db

# The card listings (/, /appeals/, /stories/) each spend one query prefetching card image renditions
# (core.images.with_card_images). On a just-started server that one query replaces one per card.
# Public listings (/, /appeals/, /stories/ and its feed) also spend one query reading the page
# privacy restrictions, so pages behind a password or login stay out of them (`.public()`, #47).
# /donate/ spends four more than /about/: its suggested amounts, the open appeals offered in
# the form with their privacy restrictions (#31), and whether the charity has QR codes, which
# changes how the form says paying works (#197). A link naming an appeal costs one more, to check
# that appeal is on offer before preselecting it.
# Every page spends one query on the language being read: Wagtail looks up its Locale to find the
# home page in that language (#113). A page in the second language spends one more, finding that
# home page's translation. The API lists the Nepali flood appeal too, so it spends one more on it.
# Every page and search spend one query on the language switcher and hreflang links: the live home
# page and the live translations of the page being read, in every language (#115).
# Every page with a header spends one query on the pages chosen in settings that it links to (the
# Donate page, the banner's page and the privacy notice) with their translations in the language
# being read, one on the footer's address and one on the banner's message in each language (#117).
# A page with a testimonial spends one finding its translation, and a partners block one finding
# the partners (#117): the home page in both languages.
BUDGETS = {
    "/": 21,
    "/appeals/": 18,
    "/appeals/flood-relief/": 18,
    "/stories/": 21,
    "/stories/feed/": 11,
    "/about/": 14,
    "/volunteer/": 15,
    "/donate/": 18,
    "/donate/?appeal=flood-relief&amount=2500": 19,
    "/search/?query=water": 23,
    "/api/v2/pages/?type=campaigns.CampaignPage&fields=*": 19,
    "/ne/": 21,
    "/ne/appeals/": 19,
    "/ne/appeals/flood-relief/": 19,
    "/ne/stories/": 22,
}


@pytest.mark.parametrize(("path", "budget"), BUDGETS.items())
def test_page_stays_within_its_query_budget(
    client, demo_site, django_assert_max_num_queries, path, budget
):
    # The first visit creates image renditions and fills caches; budget the visits after it.
    assert client.get(path).status_code == 200

    with django_assert_max_num_queries(budget):
        client.get(path)


# The demo's shared gift (#100), whose addresses are random. Both pages spend three more than
# /about/ reading the pledge with its appeal, its payments, and whether the appeal is private (its
# view restrictions, two queries). The thank-you page spends two more on the appeals page it links
# to and that page's restrictions; the gift's page one more on the appeal's photo. A gift paid with
# real money (the demo's is a test) spends one more on the thanks, matching it to a suggested
# amount to say what it does.
GIFT_BUDGETS = {"thanks": 20, "gift": 19}


@pytest.mark.parametrize(("which", "budget"), GIFT_BUDGETS.items())
def test_a_gift_stays_within_its_query_budget(
    client, demo_site, django_assert_max_num_queries, which, budget
):
    gift = Pledge.objects.get(show_on_website=True)
    path = {
        "thanks": f"{gift.page.url}pay/{gift.reference}/",
        "gift": f"{gift.page.url}gifts/{gift.gift_code}/",
    }[which]
    assert client.get(path).status_code == 200

    with django_assert_max_num_queries(budget):
        client.get(path)
