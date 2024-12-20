import uuid
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.utils.test_utils import mock_config_helper

from core.models import Commit, PullStates, Repository
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestGitlabEnterpriseWebhookHandler(APITestCase):
    @pytest.fixture(scope="function", autouse=True)
    def inject_mocker(request, mocker):
        request.mocker = mocker

    @pytest.fixture(autouse=True)
    def mock_config(self, mocker):
        mock_config_helper(
            mocker,
            configs={
                "setup.enterprise_license": True,
                "gitlab_enterprise.webhook_validation": False,
            },
        )

    def _post_event_data(self, event, data, token=None):
        return self.client.post(
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: event,
                GitLabHTTPHeaders.TOKEN: token,
            },
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab_enterprise"),
            service_id=123,
            active=True,
        )

    @patch("services.task.TaskService.notify")
    @patch("services.task.TaskService.pulls_sync")
    @patch("services.task.TaskService.pulls_sync")
    @patch("services.task.TaskService.pulls_sync")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_secret_validation(self):
        owner = OwnerFactory(service="gitlab_enterprise")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),  # if repo has webhook secret, requires validation
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
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
            reverse("gitlab_enterprise-webhook"),
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

    def test_secret_validation_required_by_config(self):
        webhook_secret = uuid.uuid4()
        # if repo has webhook_validation config set to True, requires validation
        mock_config_helper(
            self.mocker,
            configs={
                "gitlab_enterprise.webhook_validation": True,
            },
        )
        owner = OwnerFactory(service="gitlab_enterprise")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=None,
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
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
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        repo.webhook_secret = webhook_secret
        repo.save()
        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
