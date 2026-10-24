"""Per-visitor limits on the public pages that write or call a provider (#226)."""

import logging

import pytest
from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory

from core import limits


@pytest.fixture(autouse=True)
def default_limits(settings):
    settings.LIMITS_WINDOW = 300
    settings.LIMITS = {"pledge": 2, "start_payment": 2}
    settings.LIMITS_ADDRESS_HEADER = None


def request_from(address="203.0.113.7", **headers):
    return RequestFactory().post("/", REMOTE_ADDR=address, **headers)


def tries(action, request, times):
    return [limits.over_limit(request, action) for _ in range(times)]


def test_counts_the_connection_s_own_address_without_a_header():
    assert limits.client_address(request_from("203.0.113.7")) == "203.0.113.7"


def test_reads_the_address_caddy_sends_when_production_names_its_header(settings):
    settings.LIMITS_ADDRESS_HEADER = "HTTP_X_REAL_IP"
    request = request_from("172.18.0.3", HTTP_X_REAL_IP="198.51.100.20")

    assert limits.client_address(request) == "198.51.100.20"


def test_never_trusts_a_visitor_s_own_forwarded_for():
    request = request_from("203.0.113.7", HTTP_X_FORWARDED_FOR="198.51.100.99")

    assert limits.client_address(request) == "203.0.113.7"


def test_groups_ipv6_by_its_64_and_reads_mapped_ipv4_as_ipv4():
    one = limits.client_address(request_from("2001:db8:1:2::a"))
    other = limits.client_address(request_from("2001:db8:1:2:ffff::b"))

    assert one == other == "2001:db8:1:2::/64"
    assert limits.client_address(request_from("::ffff:203.0.113.7")) == "203.0.113.7"


def test_an_address_it_cant_read_counts_as_itself():
    assert limits.client_address(request_from("not-an-address")) == "not-an-address"


def test_lets_tries_through_up_to_the_limit_then_stops_them():
    assert tries("pledge", request_from(), 3) == [False, False, True]


def test_a_limit_of_zero_stops_every_try(settings):
    settings.LIMITS = {"pledge": 0}

    assert tries("pledge", request_from(), 1) == [True]


def test_starts_again_in_the_next_window(monkeypatch):
    monkeypatch.setattr(limits.time, "time", lambda: 1000.0)
    tries("pledge", request_from(), 3)
    monkeypatch.setattr(limits.time, "time", lambda: 1300.0)

    assert tries("pledge", request_from(), 1) == [False]


def test_counts_actions_and_connections_apart():
    tries("pledge", request_from("203.0.113.7"), 2)

    assert tries("start_payment", request_from("203.0.113.7"), 1) == [False]
    assert tries("pledge", request_from("203.0.113.8"), 1) == [False]


def test_logs_once_per_window_without_the_address(caplog):
    with caplog.at_level(logging.WARNING, logger="core"):
        tries("pledge", request_from("203.0.113.7"), 5)

    assert len(caplog.records) == 1
    assert "pledge" in caplog.text and "2" in caplog.text and "300" in caplog.text
    assert "203.0.113.7" not in caplog.text


def test_lets_the_try_through_when_the_counters_break(monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(caches["limits"], "get", broken)
    with caplog.at_level(logging.ERROR, logger="core"):
        assert tries("pledge", request_from("203.0.113.7"), 3) == [False, False, False]

    assert [r.levelname for r in caplog.records] == ["ERROR"] * 3
    assert "pledge" in caplog.text and "203.0.113.7" not in caplog.text


def test_a_stopped_response_says_when_to_try_again_and_is_never_cached():
    response = limits.too_many(HttpResponse())

    assert response.status_code == 429
    assert response["Retry-After"] == "300"
    assert "no-cache" in response["Cache-Control"]


@pytest.mark.parametrize(("window", "minutes"), [(300, 5), (301, 6), (30, 1)])
def test_the_wait_is_the_window_in_whole_minutes_rounded_up(settings, window, minutes):
    settings.LIMITS_WINDOW = window

    assert limits.wait_minutes() == minutes
