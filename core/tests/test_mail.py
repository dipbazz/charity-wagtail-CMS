"""Editors can still submit pages for moderation when the mail server can't be reached (#77).

Submitting emails the moderators. Wagtail skips that email on a TimeoutError or ConnectionError,
but other connection failures (no route to the host, a name that doesn't resolve) used to reach
the editor as a server error, and the page wasn't submitted.
"""

import errno
import runpy
import socket
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from wagtail.models import WorkflowState

from home.models import StandardPage

pytestmark = pytest.mark.django_db

CONNECTION_FAILURES = {
    # What the live container raises for an SMTP host of localhost with nothing listening.
    "address not available": OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address"),
    "host name not resolved": socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
}


@pytest.fixture
def production_mailers(monkeypatch, settings):
    """Send mail with the live site's mailer, pointed at a mail server that isn't set up."""
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "brightwell.example")
    monkeypatch.setenv("DJANGO_SITE_URL", "https://brightwell.example")
    monkeypatch.delenv("DJANGO_EMAIL_HOST", raising=False)
    settings.MAILERS = runpy.run_module("charity.settings.production")["MAILERS"]


@pytest.fixture
def moderator_with_email(django_user_model):
    """A moderator who would be emailed about the submission."""
    user = django_user_model.objects.create_user(
        username="moderator", email="moderator@brightwell.example", password="x"
    )
    user.groups.add(Group.objects.get(name="Moderators"))
    return user


@pytest.mark.parametrize("failure", CONNECTION_FAILURES.values(), ids=CONNECTION_FAILURES.keys())
def test_editor_can_submit_a_page_while_mail_is_down(
    client, home_page, editor, moderator_with_email, production_mailers, failure
):
    page = StandardPage(title="About us", slug="about")
    home_page.add_child(instance=page)
    client.force_login(editor)
    data = {"title": "About us", "slug": "about", "body-count": "0", "action-submit": "submit"}

    with mock.patch("socket.create_connection", side_effect=failure):
        response = client.post(reverse("wagtailadmin_pages:edit", args=[page.pk]), data)

    assert response.status_code == 302
    page.refresh_from_db()
    assert page.current_workflow_state.status == WorkflowState.STATUS_IN_PROGRESS


@pytest.mark.parametrize("failure", CONNECTION_FAILURES.values(), ids=CONNECTION_FAILURES.keys())
def test_moderator_can_approve_a_page_while_mail_is_down(
    client, home_page, editor, moderator_with_email, production_mailers, failure
):
    # Approving emails the editor who submitted the page.
    editor.email = "editor@brightwell.example"
    editor.save()
    page = StandardPage(title="About us", slug="about")
    home_page.add_child(instance=page)
    page.save_revision(user=editor)
    # A refused connection is one Wagtail already skips, so the submission works on its own.
    with mock.patch("socket.create_connection", side_effect=ConnectionRefusedError):
        task_state = page.get_workflow().start(page, editor).current_task_state
    client.force_login(moderator_with_email)
    url = reverse("wagtailadmin_pages:workflow_action", args=[page.pk, "approve", task_state.pk])

    with mock.patch("socket.create_connection", side_effect=failure):
        response = client.post(url, {"comment": ""})

    assert response.status_code == 302
    page.refresh_from_db()
    assert page.live
