"""A stand-in for the providers' servers, so no test calls a real one."""

from dataclasses import dataclass

import pytest

from nepal_payments import ProviderUnavailable, http


@dataclass
class Call:
    url: str
    method: str
    data: object
    headers: dict


class ProviderServer:
    """Answers each `http.request_json()` call with the next answer queued, and records the
    calls. Providers call `http.request_json`, so replacing it here reaches all of them."""

    def __init__(self):
        self.answers = []
        self.calls = []

    def answer(self, status, body):
        self.answers.append((status, body))
        return self

    def fail(self):
        """The next call can't reach the provider."""
        self.answers.append(ProviderUnavailable("The provider couldn't be reached."))
        return self

    def __call__(self, url, *, method="GET", data=None, headers=None):
        self.calls.append(Call(url, method, data, headers or {}))
        if not self.answers:
            raise AssertionError(f"No answer queued for {method} {url}")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def provider_server(monkeypatch):
    server = ProviderServer()
    monkeypatch.setattr(http, "request_json", server)
    return server
