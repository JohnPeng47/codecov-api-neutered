import hmac
import json
import uuid
from hashlib import sha256
from unittest.mock import call, patch

import pytest
from freezegun import freeze_time
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.plan.constants import PlanName

from codecov_auth.models import GithubAppInstallation, Owner, Service
from utils.config import get_config
from webhook_handlers.constants import (
    GitHubHTTPHeaders,
    GitHubWebhookEvents,
    WebhookHandlerErrorMessages,
)
from webhook_handlers.tests.test_github import MockedSubscription

WEBHOOK_SECRET = b"testixik8qdauiab1yiffydimvi72ekq"


class GithubEnterpriseWebhookHandlerTests(APITestCase):
    @pytest.fixture(autouse=True)
    def mock_webhook_secret(self, mocker):
        orig_get_config = get_config

        def override(*args, default=None):
            if args[0] == "github" and args[1] == "webhook_secret":
                return WEBHOOK_SECRET

            return orig_get_config(*args, default=default)

        mock_get_config = mocker.patch("webhook_handlers.views.github.get_config")
        mock_get_config.side_effect = override

    def _post_event_data(self, event, data={}):
        return self.client.post(
            reverse("github_enterprise-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: event,
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE_256: "sha256="
                + hmac.new(
                    WEBHOOK_SECRET,
                    json.dumps(data, separators=(",", ":")).encode("utf-8"),
                    digestmod=sha256,
                ).hexdigest(),
            },
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service=Service.GITHUB_ENTERPRISE.value),
            service_id=12345,
            active=True,
        )

    @patch("redis.Redis.sismember", lambda x, y, z: False)
    @patch("redis.Redis.sismember", lambda x, y, z: False)
    @patch("redis.Redis.sismember", lambda x, y, z: True)
    @patch("services.task.TaskService.status_set_pending")
    @patch("redis.Redis.sismember", lambda x, y, z: False)
    @patch("services.task.TaskService.status_set_pending")
    @patch("redis.Redis.sismember", lambda x, y, z: True)
    @patch("services.task.TaskService.status_set_pending")
    @patch("services.task.TaskService.notify")
    @patch("services.task.TaskService.pulls_sync")
    @freeze_time("2024-03-28T00:00:00")
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @freeze_time("2024-03-28T00:00:00")
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch(
        "services.task.TaskService.refresh",
        lambda self, ownerid, username, sync_teams, sync_repos, using_integration, repos_affected: None,
    )
    @patch("services.task.TaskService.refresh")
    @patch("services.task.TaskService.refresh")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.task.TaskService.sync_plans")
    @patch("logging.Logger.warning")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.task.TaskService.sync_plans")
    @patch("webhook_handlers.views.github.get_config")
    def test_repo_not_found_when_owner_has_integration_creates_repo(self):
        owner = OwnerFactory(
            integration_id=4850403,
            service_id=97968493,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": 506003,
                    "name": "testrepo",
                    "private": False,
                    "default_branch": "master",
                    "owner": {"id": owner.service_id},
                },
            },
        )

        assert owner.repository_set.filter(name="testrepo").exists()

    def test_repo_creation_doesnt_crash_for_forked_repo(self):
        owner = OwnerFactory(
            integration_id=4850403,
            service_id=97968493,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": 506003,
                    "name": "testrepo",
                    "private": False,
                    "default_branch": "master",
                    "owner": {"id": owner.service_id},
                    "fork": True,
                    "parent": {
                        "name": "mainrepo",
                        "language": "python",
                        "id": 7940284,
                        "private": False,
                        "default_branch": "master",
                        "owner": {"id": 8495712939, "login": "alogin"},
                    },
                },
            },
        )

        assert owner.repository_set.filter(name="testrepo").exists()
