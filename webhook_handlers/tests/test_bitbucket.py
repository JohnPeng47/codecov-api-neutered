from unittest.mock import patch

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

from core.models import Branch, Commit, PullStates
from webhook_handlers.constants import (
    BitbucketHTTPHeaders,
    BitbucketWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestBitbucketWebhookHandler(APITestCase):
    def _post_event_data(
        self, event, data={}, hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c"
    ):
        return self.client.post(
            reverse("bitbucket-webhook"),
            **{BitbucketHTTPHeaders.EVENT: event, BitbucketHTTPHeaders.UUID: hookid},
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="bitbucket"),
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
    def test_repo_commit_status_change_commit_skip_processing(self):
        commitid = "9fec847784abb10b2fa567ee63b85bd238955d0e"
        CommitFactory(
            commitid=commitid, repository=self.repo, state=Commit.CommitStates.PENDING
        )
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "SUCCESSFUL",
                    "key": "not_codecov_context",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}"
                        },
                        "self": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    @patch("services.task.TaskService.notify")
    def test_repo_commit_status_change_commit_notifies(self, notify_mock):
        commitid = "9fec847784abb10b2fa567ee63b85bd238955d0e"
        CommitFactory(
            commitid=commitid, repository=self.repo, state=Commit.CommitStates.COMPLETE
        )
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "SUCCESSFUL",
                    "key": "not_codecov_context",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}"
                        },
                        "self": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Notify queued"
        notify_mock.assert_called_once_with(repoid=self.repo.repoid, commitid=commitid)
