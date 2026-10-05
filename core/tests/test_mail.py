"""The live site's SMTP backend reports every failure to connect as a ConnectionError (#77).

Code that sends mail can then catch one error type for "the mail server can't be reached",
whatever went wrong: the address, the name lookup, TLS or the login.
"""

import errno
import smtplib
import socket
import ssl
from unittest import mock

import pytest
from django.core.mail import EmailMessage

from core.mail import SMTPBackend

CONNECTION_FAILURES = {
    # What the live container raises for an SMTP host of localhost with nothing listening.
    "address not available": (
        "connect",
        OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address"),
    ),
    "host name not resolved": (
        "connect",
        socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
    ),
    "tls handshake failed": ("starttls", ssl.SSLError("WRONG_VERSION_NUMBER")),
    "login refused": (
        "login",
        smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid"),
    ),
}


@pytest.fixture
def smtp(monkeypatch):
    """Stands in for smtplib.SMTP; its return value is the connected server."""
    connect = mock.Mock()
    monkeypatch.setattr(smtplib, "SMTP", connect)
    return connect


def make_backend(**options):
    return SMTPBackend(
        alias="default",
        host="smtp.brightwell.example",
        port=587,
        username="website",
        password="secret",
        use_tls=True,
        **options,
    )


def fail_at(smtp, step, error):
    if step == "connect":
        smtp.side_effect = error
    else:
        getattr(smtp.return_value, step).side_effect = error


@pytest.mark.parametrize(
    ("step", "failure"), CONNECTION_FAILURES.values(), ids=CONNECTION_FAILURES.keys()
)
def test_a_failure_to_connect_is_a_connection_error(smtp, step, failure):
    fail_at(smtp, step, failure)

    with pytest.raises(ConnectionError, match="smtp.brightwell.example:587") as raised:
        make_backend().open()

    assert raised.value.__cause__ is failure


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("timed out"), ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")],
    ids=["timeout", "connection refused"],
)
def test_timeouts_and_connection_errors_are_raised_unchanged(smtp, failure):
    smtp.side_effect = failure

    with pytest.raises(type(failure)) as raised:
        make_backend().open()

    assert raised.value is failure


@pytest.mark.parametrize(
    ("step", "failure"), CONNECTION_FAILURES.values(), ids=CONNECTION_FAILURES.keys()
)
def test_failing_silently_still_raises_nothing(smtp, step, failure):
    fail_at(smtp, step, failure)

    assert make_backend(fail_silently=True).open() is None


def test_sends_through_a_reachable_server(smtp):
    message = EmailMessage(
        "New volunteer sign-up",
        "Your name: Sam",
        "website@brightwell.example",
        ["volunteers@brightwell.example"],
    )

    sent = make_backend().send_messages([message])

    assert sent == 1
    server = smtp.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("website", "secret")
    server.sendmail.assert_called_once()
