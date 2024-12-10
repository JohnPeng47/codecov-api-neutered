import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from codecov.tests.base_test import InternalAPITest
from utils.test_utils import Client

get_permissions_method = (
    "api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions"
)


@patch(get_permissions_method)
class RepoPullList(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(
            pullid=10,
            author=self.org,
            repository=self.repo,
            state="open",
            head=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
            base=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
        )
        PullFactory(pullid=11, author=self.org, repository=self.repo, state="closed")
        PullFactory(pullid=12, author=other_org, repository=other_repo)
        self.correct_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "testRepoName",
        }
        self.incorrect_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "otherRepoName",
        }

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_get_pulls_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == 403

    def test_list_pulls_comparedto_not_base(self, mock_provider):
        repo = RepositoryFactory.create(
            author=self.org, name="test_list_pulls_comparedto_not_base", active=True
        )
        repo.save()
        user = OwnerFactory.create(
            username="test_list_pulls_comparedto_not_base",
            service="github",
            organizations=[self.org.ownerid],
            permission=[repo.repoid],
        )
        user.save()
        mock_provider.return_value = True, True
        pull = PullFactory.create(
            pullid=101,
            author=self.org,
            repository=repo,
            state="open",
            head=CommitFactory(repository=repo, author=user, pullid=None).commitid,
            base=CommitFactory(
                repository=repo, pullid=None, author=user, totals=None
            ).commitid,
            compared_to=CommitFactory(
                pullid=None,
                repository=repo,
                author=user,
                totals={
                    "C": 0,
                    "M": 0,
                    "N": 0,
                    "b": 0,
                    "c": "30.00000",
                    "d": 0,
                    "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                    "f": 3,
                    "h": 6,
                    "m": 10,
                    "n": 20,
                    "p": 4,
                    "s": 1,
                },
            ).commitid,
        )
        response = self.client.get(
            reverse(
                "pulls-list",
                kwargs={
                    "service": "github",
                    "owner_username": "codecov",
                    "repo_name": "test_list_pulls_comparedto_not_base",
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        expected_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": 101,
                    "title": pull.title,
                    "most_recent_commiter": "test_list_pulls_comparedto_not_base",
                    "base_totals": {
                        "files": 3,
                        "lines": 20,
                        "hits": 6,
                        "misses": 10,
                        "partials": 4,
                        "coverage": 30.0,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 1,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "head_totals": {
                        "files": 3,
                        "lines": 20,
                        "hits": 17,
                        "misses": 3,
                        "partials": 0,
                        "coverage": 85.0,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 1,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    # This whole TZ settings is messing things up a bit
                    "updatestamp": pull.updatestamp.replace(tzinfo=None).isoformat()
                    + "Z",
                    "state": "open",
                    "ci_passed": True,
                }
            ],
            "total_pages": 1,
        }
        assert content["results"][0] == expected_content["results"][0]
        assert content == expected_content


@patch(get_permissions_method)
class RepoPullDetail(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        RepositoryFactory(author=other_org, name="otherRepoName", active=True)
        repo_with_permission = [repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(pullid=10, author=self.org, repository=repo, state="open")
        PullFactory(pullid=11, author=self.org, repository=repo, state="closed")

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_get_pull_no_permissions(self, mock_provider):
        self.current_owner.permission = []
        self.current_owner.save()
        mock_provider.return_value = False, False
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 404)

    def test_get_pull_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        assert response.status_code == 403


@patch(get_permissions_method)
class RepoCommitList(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / commits
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        self.first_test_commit = CommitFactory(
            author=self.org,
            repository=self.repo,
            totals={
                "C": 2,
                "M": 0,
                "N": 5,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )
        self.second_test_commit = CommitFactory(
            author=self.org,
            repository=self.repo,
            totals={
                "C": 3,
                "M": 0,
                "N": 5,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )
        self.third_test_commit = CommitFactory(
            author=other_org,
            repository=other_repo,
            totals={
                "C": 3,
                "M": 0,
                "N": 6,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    # TODO: Improve this test to not assert the pagination data

    def test_fetch_commits_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.current_owner.permission = []
        self.current_owner.save()

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 404

    def test_fetch_commits_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 403


@patch(get_permissions_method)
class BranchViewSetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.other_user = OwnerFactory(permission=[self.repo.repoid])

        self.branches = [
            BranchFactory(repository=self.repo, name="foo"),
            BranchFactory(repository=self.repo, name="bar"),
        ]

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def _get_branches(self, kwargs={}, query={}):
        if not kwargs:
            kwargs = {
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            }
        return self.client.get(reverse("branches-list", kwargs=kwargs), data=query)

    def test_branch_data_includes_most_recent_commiter_of_each_branch(
        self, mock_provider
    ):
        self.branches[0].head = CommitFactory(
            repository=self.repo,
            author=self.current_owner,
            branch=self.branches[0].name,
        ).commitid
        self.branches[0].save()
        self.branches[1].head = CommitFactory(
            repository=self.repo, author=self.other_user, branch=self.branches[1].name
        ).commitid
        self.branches[1].save()

        response = self._get_branches()

        assert (
            response.data["results"][0]["most_recent_commiter"]
            == self.other_user.username
        )
        assert (
            response.data["results"][1]["most_recent_commiter"]
            == self.current_owner.username
        )

    def test_list_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappy"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self._get_branches()

        assert response.status_code == 403
