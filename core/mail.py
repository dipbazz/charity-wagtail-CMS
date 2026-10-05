from django.core.mail.backends.smtp import EmailBackend


class SMTPBackend(EmailBackend):
    """Django's SMTP backend, reporting every failure to connect as a ConnectionError.

    Wagtail skips its moderation emails when opening the connection raises TimeoutError or
    ConnectionError, but not the other OSErrors a connection can fail with: no route to the
    host (errno 99 in a container with nothing listening), a host name that doesn't resolve, a
    TLS or login failure. Those reached editors as a server error and their page wasn't
    submitted (#77).
    """

    def open(self):
        try:
            return super().open()
        except (TimeoutError, ConnectionError):
            raise
        except OSError as error:
            message = f"Could not connect to {self.host}:{self.port}: {error}"
            raise ConnectionError(message) from error
