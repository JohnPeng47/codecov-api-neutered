from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import APIException
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from api.internal.tests.test_utils import (
    GetAdminErrorProviderAdapter,
    GetAdminProviderAdapter,
)
from api.shared.permissions import RepositoryPermissionsService, UserIsAdminPermissions


class MockedPermissionsAdapter:
    async def get_authenticated(self):
        return True, True


class TestRepositoryPermissionsService(TestCase):
    def setUp(self):
        self.permissions_service = RepositoryPermissionsService()

    @patch(
        "api.shared.permissions.RepositoryPermissionsService._fetch_provider_permissions"
    )
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @patch("services.self_hosted.license_seats")
    @override_settings(IS_ENTERPRISE=True)
    def test_user_is_activated_when_self_hosted(self, license_seats):
        license_seats.return_value = 5

        user = OwnerFactory()
        owner = OwnerFactory(plan_auto_activate=True)
        user.organizations = [owner.ownerid]
        user.save()

        assert self.permissions_service.user_is_activated(user, owner) is True

        owner.refresh_from_db()
        assert user.ownerid in owner.plan_activated_users

    def test_user_is_activated_returns_false_if_cant_auto_activate(self):
        owner = OwnerFactory(plan="users-inappy", plan_user_count=10)
        user = OwnerFactory(organizations=[owner.ownerid])

        with self.subTest("auto activate set to false"):
            owner.plan_auto_activate = False
            owner.save()
            assert self.permissions_service.user_is_activated(user, owner) is False

        with self.subTest("auto activate true but not enough seats"):
            owner.plan_auto_activate = True
            owner.plan_user_count = 0
            owner.save()
            assert self.permissions_service.user_is_activated(user, owner) is False


class TestUserIsAdminPermissions(TestCase):
    def setUp(self):
        self.permissions_class = UserIsAdminPermissions()

    @patch("api.shared.permissions.get_provider")
    def test_is_admin_on_provider_invokes_torngit_adapter_when_user_not_in_admin_array(
        self, mocked_get_adapter
    ):
        org = OwnerFactory()
        user = OwnerFactory()

        mocked_get_adapter.return_value = GetAdminProviderAdapter()
        self.permissions_class._is_admin_on_provider(user, org)
        assert mocked_get_adapter.return_value.last_call_args == {
            "username": user.username,
            "service_id": user.service_id,
        }

    @patch("api.shared.permissions.get_provider")
    def test_is_admin_on_provider_handles_torngit_exception(self, mock_get_provider):
        code, message = 404, "uh oh"
        mock_get_provider.return_value = GetAdminErrorProviderAdapter(code, message)
        org = OwnerFactory()
        user = OwnerFactory()

        with self.assertRaises(APIException):
            self.permissions_class._is_admin_on_provider(user, org)
