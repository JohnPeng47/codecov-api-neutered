import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from core.models import Commit, PullStates
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)


def get_config_mock(*args, **kwargs):
    if args == ("setup", "enterprise_license"):
        return False
    elif args == ("gitlab", "webhook_validation"):
        return False
    else:
        return kwargs.get("default")


class TestGitlabWebhookHandler(APITestCase):
    def _post_event_data(self, event, data):
        return self.client.post(
            reverse("gitlab-webhook"),
            data=data,
            format="json",
            **{
                GitLabHTTPHeaders.EVENT: event,
            },
        )

    def setUp(self):
        self.get_config_patcher = patch("webhook_handlers.views.gitlab.get_config")
        self.get_config_mock = self.get_config_patcher.start()
        self.get_config_mock.side_effect = get_config_mock

        self.repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"), service_id=123, active=True
        )

    def tearDown(self):
        self.get_config_patcher.stop()

    @patch("services.task.TaskService.notify")
    @patch("services.task.TaskService.pulls_sync")
    @patch("services.task.TaskService.pulls_sync")
    @patch("services.task.TaskService.pulls_sync")
    def test_handle_system_hook_when_not_enterprise(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(author=owner)

        system_hook_events = [
            "project_create",
            "project_destroy",
            "project_rename",
            "project_transfer",
            "user_add_to_team",
            "user_remove_from_team",
        ]

        event_data = {
            "event": GitLabWebhookEvents.SYSTEM,
            "data": {
                "event_name": "project_create",
                "project_id": repo.service_id,
            },
        }

        for event in system_hook_events:
            event_data["data"]["event_name"] = event
            response = self._post_event_data(**event_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_secret_validation(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),  # if repo has webhook secret, requires validation
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: "",
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = self.client.post(
            reverse("gitlab-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: repo.webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
