from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from core.models import Branch, PullStates
from webhook_handlers.constants import (
    BitbucketServerHTTPHeaders,
    BitbucketServerWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestBitbucketServerWebhookHandler(APITestCase):
    def _post_event_data(
        self, event, data={}, hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c"
    ):
        return self.client.post(
            reverse("bitbucket-server-webhook"),
            **{
                BitbucketServerHTTPHeaders.EVENT: event,
                BitbucketServerHTTPHeaders.UUID: hookid,
            },
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="bitbucket_server"),
            service_id="673a6070-3421-46c9-9d48-90745f7bfe8e",
            active=True,
            hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c",
        )
        self.pull = PullFactory(
            author=self.repo.author,
            repository=self.repo,
            pullid=1,
            state=PullStates.OPEN,
        )

    @patch("services.task.TaskService.pulls_sync")
    def test_repo_push_new_branch_sync_yaml_skipped(self):
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.REPO_REFS_CHANGED,
            data={
                "repository": {"id": "673a6070-3421-46c9-9d48-90745f7bfe8e"},
                "push": {
                    "changes": {
                        "new": {
                            "type": "branch",
                            "name": "name-of-branch",
                            "target": {},
                        },
                        "old": {
                            "type": "branch",
                            "name": "name-of-branch",
                            "target": {},
                        },
                        "links": {},
                        "created": False,
                        "forced": False,
                        "closed": False,
                        "commits": [
                            {
                                "hash": "03f4a7270240708834de475bcf21532d6134777e",
                                "type": "commit",
                                "message": "commit message\n",
                                "author": {},
                                "links": {},
                            }
                        ],
                        "truncated": False,
                    }
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml skipped"

    def test_repo_push_new_branch_sync_yaml(self):
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.REPO_REFS_CHANGED,
            data={
                "repository": {"id": "673a6070-3421-46c9-9d48-90745f7bfe8e"},
                "push": {
                    "changes": {
                        "new": {
                            "type": "branch",
                            "name": "name-of-branch",
                            "target": {},
                        },
                        "old": {
                            "type": "branch",
                            "name": "name-of-branch",
                            "target": {},
                        },
                        "links": {},
                        "created": False,
                        "forced": False,
                        "closed": False,
                        "commits": [
                            {
                                "hash": "03f4a7270240708834de475bcf21532d6134777e",
                                "type": "commit",
                                "message": "commit message\n",
                                "author": {},
                                "links": {},
                            }
                        ],
                        "truncated": False,
                    }
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml skipped"
