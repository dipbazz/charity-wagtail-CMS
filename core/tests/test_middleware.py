import pytest

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
