"""request_json() against a small local server: what it sends, and which answers it passes on."""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nepal_payments import ProviderUnavailable, http


class Answers(BaseHTTPRequestHandler):
    """Answers /<status>/<kind>, and keeps what it was sent."""

    received = []

    def do_GET(self):
        self.reply()

    def do_POST(self):
        self.reply()

    def reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        Answers.received.append((self.command, dict(self.headers), self.rfile.read(length)))
        _, status, kind = self.path.split("/")
        if kind == "slow":
            time.sleep(1)
        body = b"<html>Busy</html>" if kind == "text" else b'{"status": "Completed"}'
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html" if kind == "text" else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep test output quiet


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # the slow answer's client has hung up by the time it's written


@pytest.fixture(scope="module")
def server():
    httpd = QuietServer(("127.0.0.1", 0), Answers)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def received():
    Answers.received.clear()
    return Answers.received


@pytest.mark.parametrize("status", [200, 400, 401, 404])
def test_passes_on_the_json_of_a_success_or_a_refusal(server, status):
    """Providers explain a refusal (an expired payment, a wrong key) in JSON."""
    assert http.request_json(f"{server}/{status}/json") == (status, {"status": "Completed"})


@pytest.mark.parametrize("path", ["/500/json", "/503/json", "/200/text"])
def test_an_error_or_an_answer_that_isnt_json_means_unavailable(server, path):
    with pytest.raises(ProviderUnavailable):
        http.request_json(server + path)


def test_a_provider_that_cant_be_reached_is_unavailable():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]  # nothing listens once the socket closes

    with pytest.raises(ProviderUnavailable):
        http.request_json(f"http://127.0.0.1:{closed_port}/")


def test_a_slow_provider_is_unavailable_after_the_timeout(server, monkeypatch):
    monkeypatch.setattr(http, "TIMEOUT", 0.2)

    with pytest.raises(ProviderUnavailable):
        http.request_json(f"{server}/200/slow")


def test_posts_json_with_the_headers_given(server, received):
    http.request_json(
        f"{server}/200/json",
        method="POST",
        data={"pidx": "abc"},
        headers={"Authorization": "Key s3cret"},
    )

    method, headers, body = received[0]
    assert method == "POST"
    assert json.loads(body) == {"pidx": "abc"}
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Key s3cret"


def test_says_who_is_asking(server, received):
    """Some firewalls turn away Python's default User-Agent."""
    http.request_json(f"{server}/200/json")

    assert received[0][1]["User-Agent"].startswith("nepal-payments/")
