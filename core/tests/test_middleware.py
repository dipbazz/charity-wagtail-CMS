import pytest
from wagtail.models import Locale

from home.models import StandardPage

pytestmark = pytest.mark.django_db


# Regression: ISSUE-003 — every page sent Vary: Accept-Language, though the URL alone sets its
# language, which pushed /appeals/flood-relief/ over its page-weight budget
# Found by /qa on 2026-10-06
# Report: .gstack/qa-reports/run-20261006T105938Z/qa-report-127.0.0.1-2026-10-06.md
@pytest.mark.parametrize(("path", "language"), [("/", "en"), ("/ne/", "ne")])
def test_pages_name_their_language_without_varying_by_the_browser_s(
    client, nepali_home_page, path, language
):
    response = client.get(path)

    assert response["Content-Language"] == language
    vary = [header.strip().lower() for header in response.get("Vary", "").split(",")]
    assert "accept-language" not in vary


def test_other_vary_headers_are_kept(client, home_page):
    response = client.get("/")

    assert "Cookie" in response["Vary"]


def add_page(parent, title, slug):
    page = StandardPage(title=title, slug=slug)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


class TestFallbackToTheMainLanguage:
    """A second-language address with no page there redirects to the main language's page.

    Found by the user checking PR #120 on a database seeded before Nepali pages existed: /ne/news/
    served the English news page marked as Nepali, with Nepali month names.
    """

    @pytest.mark.parametrize("nepali_locale_exists", [True, False])
    def test_a_language_without_a_home_page_redirects_to_the_main_language(
        self, client, home_page, nepali_locale_exists
    ):
        if nepali_locale_exists:
            Locale.objects.get_or_create(language_code="ne")
        add_page(home_page, "News", "news")

        assert redirect_target(client, "/ne/") == "/"
        assert redirect_target(client, "/ne/news/") == "/news/"

    def test_a_draft_home_page_translation_isnt_served_yet(self, client, home_page, nepali_locale):
        home_page.copy_for_translation(nepali_locale)

        assert redirect_target(client, "/ne/") == "/"

    def test_keeps_the_query_string(self, client, home_page):
        add_page(home_page, "News", "news")

        assert redirect_target(client, "/ne/news/?page=2") == "/news/?page=2"

    def test_an_address_missing_in_both_languages_is_not_found(self, client, nepali_home_page):
        assert client.get("/ne/no-such-page/").status_code == 404

    def test_a_page_that_exists_in_nepali_is_served(self, client, home_page, nepali_home_page):
        assert client.get("/ne/").status_code == 200


def redirect_target(client, path):
    response = client.get(path)
    assert response.status_code == 302, (path, response.status_code)
    return response["Location"]
