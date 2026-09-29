import datetime
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone
from wagtail.models import WorkflowState

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def campaign(home_page):
    index = CampaignIndexPageFactory(parent=home_page)
    return CampaignPageFactory(parent=index, title="Winter appeal", live=False)


def user_in_group(django_user_model, group_name):
    user = django_user_model.objects.create_user(username=group_name.lower(), password="x")
    user.groups.add(Group.objects.get(name=group_name))
    return user


class TestModerationWorkflow:
    def test_campaigns_go_through_the_default_moderation_workflow(self, campaign):
        workflow = campaign.get_workflow()

        assert workflow is not None
        assert workflow.active

    def test_editors_cannot_publish_directly(self, campaign, django_user_model):
        editor = user_in_group(django_user_model, "Editors")

        permissions = campaign.permissions_for_user(editor)

        assert permissions.can_edit()
        assert not permissions.can_publish()

    def test_submitted_campaign_goes_live_once_a_moderator_approves(
        self, campaign, django_user_model
    ):
        editor = user_in_group(django_user_model, "Editors")
        moderator = user_in_group(django_user_model, "Moderators")
        campaign.save_revision(user=editor)

        workflow_state = campaign.get_workflow().start(campaign, editor)

        campaign.refresh_from_db()
        assert workflow_state.status == WorkflowState.STATUS_IN_PROGRESS
        assert not campaign.live

        task_state = workflow_state.current_task_state
        task_state.task.specific.on_action(task_state, moderator, "approve")

        campaign.refresh_from_db()
        assert campaign.live


def test_scheduled_campaign_is_published_when_its_time_comes(campaign):
    go_live = timezone.now() + datetime.timedelta(days=1)
    campaign.go_live_at = go_live
    campaign.save_revision().publish()

    campaign.refresh_from_db()
    assert not campaign.live

    # Run the cron command as if the scheduled time has passed.
    with mock.patch(
        "django.utils.timezone.now", return_value=go_live + datetime.timedelta(minutes=1)
    ):
        call_command("publish_scheduled")

    campaign.refresh_from_db()
    assert campaign.live
