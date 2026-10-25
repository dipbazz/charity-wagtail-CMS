"""Per-visitor limits on the public pages that write or call a provider (#226)."""

import logging
import threading
import time

import pytest
from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory

from core import limits


@pytest.fixture(autouse=True)
def default_limits(settings, monkeypatch):
    settings.LIMITS_WINDOW = 300
    monkeypatch.setattr(limits, "broken_logged_in", None)
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


def test_without_caddy_s_header_lets_every_try_through_and_says_so_once(settings, caplog):
    """Behind Caddy, the address Django sees is Caddy's, so counting it would count every visitor
    as one, and one script could stop all giving (before `caddy reload`, say)."""
    settings.LIMITS_ADDRESS_HEADER = "HTTP_X_REAL_IP"

    with caplog.at_level(logging.ERROR, logger="core"):
        assert tries("pledge", request_from("172.18.0.3"), 5) == [False] * 5

    assert len(caplog.records) == 1
    assert "X-Real-IP" in caplog.text or "HTTP_X_REAL_IP" in caplog.text
    assert "172.18.0.3" not in caplog.text


def test_never_trusts_a_visitor_s_own_forwarded_for():
    request = request_from("203.0.113.7", HTTP_X_FORWARDED_FOR="198.51.100.99")

    assert limits.client_address(request) == "203.0.113.7"


def test_groups_ipv6_by_its_56_and_reads_mapped_ipv4_as_ipv4():
    """A home line is often given a /56, so a script switching between its /64s is one."""
    one = limits.client_address(request_from("2001:db8:1:2::a"))
    other = limits.client_address(request_from("2001:db8:1:ff:ffff::b"))

    assert one == other == "2001:db8:1::/56"
    assert limits.client_address(request_from("2001:db8:1:100::a")) == "2001:db8:1:100::/56"
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
    monkeypatch.setattr(limits.time, "time", lambda: 1000.0)
    with caplog.at_level(logging.ERROR, logger="core"):
        assert tries("pledge", request_from("203.0.113.7"), 3) == [False, False, False]

    # Once per window in each worker, so a flood can't push errors out of the logs.
    assert [r.levelname for r in caplog.records] == ["ERROR"]
    assert "pledge" in caplog.text and "203.0.113.7" not in caplog.text

    monkeypatch.setattr(limits.time, "time", lambda: 1300.0)
    with caplog.at_level(logging.ERROR, logger="core"):
        tries("start_payment", request_from("203.0.113.7"), 2)

    assert len(caplog.records) == 2


def test_an_action_with_no_limit_set_is_let_through_and_said_so_not_a_server_error(
    settings, caplog
):
    """A LIMITS override that names only some actions must not break the others' pages."""
    settings.LIMITS = {"pledge": 2}

    with caplog.at_level(logging.ERROR, logger="core"):
        assert tries("start_payment", request_from(), 3) == [False] * 3

    assert [r.levelname for r in caplog.records] == ["ERROR"]
    assert "start_payment" in caplog.text


def test_counts_every_try_when_workers_count_at_the_same_moment(settings, tmp_path, monkeypatch):
    """Each worker reads the count, then saves one more a moment later. Without a lock, tries at
    the same moment all read the same count and save the same one more, so a parallel flood
    passes the limit by as many tries as it sends at once."""
    settings.CACHES = {
        **settings.CACHES,
        "limits": {"BACKEND": "core.limits.CounterCache", "LOCATION": str(tmp_path)},
    }
    settings.LIMITS = {"pledge": 100}
    monkeypatch.setattr(limits.time, "time", lambda: 1000.0)
    get = limits.CounterCache.get

    def get_then_get_busy(self, *args, **kwargs):
        value = get(self, *args, **kwargs)
        time.sleep(0.02)  # What a busy worker does between reading the count and saving it.
        return value

    monkeypatch.setattr(limits.CounterCache, "get", get_then_get_busy)
    start = threading.Barrier(8, timeout=5)

    def worker():
        start.wait()
        limits.over_limit(request_from(), "pledge")

    workers = [threading.Thread(target=worker) for _ in range(8)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()

    assert caches["limits"].get("pledge:203.0.113.7:3") == 8


def test_a_full_counter_cache_clears_past_windows_before_forgetting_a_live_count(
    tmp_path, monkeypatch
):
    """A past window's counters are never read again, so Django's file cache would keep them and,
    once full, forget a random third of the files, live counts too."""
    cache = limits.CounterCache(str(tmp_path), {"OPTIONS": {"MAX_ENTRIES": 4}})
    monkeypatch.setattr(limits.time, "time", lambda: 1000.0)
    for n in range(4):
        cache.set(f"pledge:203.0.113.{n}:3", 10, timeout=300)
    monkeypatch.setattr(limits.time, "time", lambda: 1350.0)

    for n in range(3):
        cache.set(f"pledge:203.0.113.{n}:4", n, timeout=300)

    assert len(cache._list_cache_files()) == 3
    assert [cache.get(f"pledge:203.0.113.{n}:4") for n in range(3)] == [0, 1, 2]


def test_a_stopped_response_says_when_to_try_again_and_is_never_cached(monkeypatch):
    monkeypatch.setattr(limits.time, "time", lambda: 1180.5)

    response = limits.too_many(HttpResponse(), limits.wait())

    assert response.status_code == 429
    assert response["Retry-After"] == "20"
    assert "no-cache" in response["Cache-Control"]


@pytest.mark.parametrize(
    ("now", "seconds", "minutes"), [(900.0, 300, 5), (1000.0, 200, 4), (1199.9, 1, 1)]
)
def test_the_wait_is_what_s_left_of_the_window_rounded_up(monkeypatch, now, seconds, minutes):
    """The counts start again when the window ends, so that's when to try again."""
    monkeypatch.setattr(limits.time, "time", lambda: now)

    assert limits.wait_seconds() == seconds
    assert limits.wait() == (minutes, seconds)


def test_the_wait_reads_the_clock_once(monkeypatch):
    """A window ending between two readings must not give 1 minute with about 5 minutes."""
    readings = iter([1199.5, 1200.0])
    monkeypatch.setattr(limits.time, "time", lambda: next(readings))

    assert limits.wait() == (1, 1)
