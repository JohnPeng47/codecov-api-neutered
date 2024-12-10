import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    InvoiceBillingFactory,
    OwnerFactory,
    UserFactory,
)
from shared.plan.constants import PlanName, TrialStatus
from stripe import StripeError

from api.internal.tests.test_utils import GetAdminProviderAdapter
from codecov_auth.models import Service
from utils.test_utils import APIClient

curr_path = os.path.dirname(__file__)


class MockSubscription(object):
    def __init__(self, subscription_params):
        self.items = {"data": [{"id": "abc"}]}
        self.cancel_at_period_end = False
        self.current_period_end = 1633512445
        self.latest_invoice = subscription_params["latest_invoice"]
        self.customer = {
            "invoice_settings": {
                "default_payment_method": subscription_params["default_payment_method"]
            },
            "id": "cus_LK&*Hli8YLIO",
            "discount": None,
            "email": None,
        }
        self.schedule = subscription_params["schedule_id"]
        self.collection_method = subscription_params["collection_method"]
        self.trial_end = subscription_params.get("trial_end")

        customer_coupon = subscription_params.get("customer_coupon")
        if customer_coupon:
            self.customer["discount"] = {"coupon": customer_coupon}

        pending_update = subscription_params.get("pending_update")
        if pending_update:
            self.pending_update = pending_update

    def __getitem__(self, key):
        return getattr(self, key)


class MockMetadata(object):
    def __init__(self):
        self.obo = 2
        self.obo_organization = 3

    def __getitem__(self, key):
        return getattr(self, key)


class MockSchedule(object):
    def __init__(self, schedule_params, phases):
        self.id = schedule_params["id"]
        self.phases = phases
        self.metadata = MockMetadata()

    def __getitem__(self, key):
        return getattr(self, key)


@pytest.mark.usefixtures("codecov_vcr")
class AccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(
            reverse("account_details-detail", kwargs=kwargs), data=data, format="json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "gitlab"
        self.current_owner = OwnerFactory(
            stripe_customer_id=1000,
            service=Service.GITHUB.value,
            service_id="10238974029348",
        )
        self.expected_invoice = {
            "number": "EF0A41E-0001",
            "status": "paid",
            "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
            "created": 1489789429,
            "period_start": 1487370220,
            "period_end": 1489789420,
            "due_date": None,
            "customer_name": "Peer Company",
            "customer_address": "6639 Boulevard Dr, Westwood FL 34202 USA",
            "currency": "usd",
            "amount_paid": 999,
            "amount_due": 999,
            "amount_remaining": 0,
            "total": 999,
            "subtotal": 999,
            "invoice_pdf": "https://pay.stripe.com/invoice/acct_1032D82eZvKYlo2C/invst_a7KV10HpLw2QxrihgVyuOkOjMZ/pdf",
            "line_items": [
                {
                    "description": "(10) users-pr-inappm",
                    "amount": 120,
                    "currency": "usd",
                    "plan_name": "users-pr-inappm",
                    "quantity": 1,
                    "period": {"end": 1521326190, "start": 1518906990},
                }
            ],
            "footer": None,
            "customer_email": "olivia.williams.03@example.com",
            "customer_shipping": None,
        }

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    @patch("services.billing.stripe.SubscriptionSchedule.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.checkout.Session.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.checkout.Session.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.StripeService.update_payment_method")
    @patch("services.billing.StripeService.update_email_address")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.StripeService.update_billing_address")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.PaymentMethod.modify")
    @patch("services.billing.stripe.Customer.modify")
    @patch("api.shared.permissions.get_provider")
    def test_update_can_change_name_and_email(self):
        expected_name, expected_email = "Scooby Doo", "scoob@snack.com"
        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"name": expected_name, "email": expected_email},
        )

        assert response.data["name"] == expected_name
        assert response.data["email"] == expected_email
        self.current_owner.refresh_from_db()
        assert self.current_owner.name == expected_name
        assert self.current_owner.email == expected_email

    @patch("services.billing.StripeService.modify_subscription")
    def test_update_handles_stripe_error(self, modify_sub_mock):
        code, message = 402, "Not right, wrong in fact"
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        modify_sub_mock.side_effect = StripeError(message=message, http_status=code)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_monthly(self, modify_sub_mock, send_sentry_webhook):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.save()

        self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(
            self.current_owner, self.current_owner
        )

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_monthly_with_users_org(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 12}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )

        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(self.current_owner, org)

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_annual(self, modify_sub_mock, send_sentry_webhook):
        desired_plan = {"value": "users-sentryy", "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.save()

        self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(
            self.current_owner, self.current_owner
        )

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_annual_with_users_org(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": "users-sentryy", "quantity": 12}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(self.current_owner, org)

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_non_sentry_user(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 5}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = None
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        res = self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )

        # cannot upgrade to Sentry plan
        assert res.status_code == 400
        assert res.json() == {
            "plan": {
                "value": [
                    "Invalid value for plan: users-sentrym; must be one of ['users-basic', 'users-pr-inappm', 'users-pr-inappy', 'users-teamm', 'users-teamy']"
                ]
            }
        }

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_apply_cancellation_discount(
        self, modify_customer_mock, retrieve_subscription_mock, coupon_create_mock
    ):
        coupon_create_mock.return_value = MagicMock(id="test-coupon-id")

        self.current_owner.plan = "users-pr-inappm"
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "customer_coupon": {
                "name": "30% off for 6 months",
                "percent_off": 30.0,
                "duration_in_months": 6,
                "created": int(datetime(2023, 1, 1, 0, 0, 0).timestamp()),
            },
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"apply_cancellation_discount": True},
        )

        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id,
            coupon="test-coupon-id",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["subscription_detail"]["customer"]["discount"] == {
            "name": "30% off for 6 months",
            "percent_off": 30.0,
            "duration_in_months": 6,
            "expires": int(datetime(2023, 7, 1, 0, 0, 0).timestamp()),
        }

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_apply_cancellation_discount_yearly(
        self, modify_customer_mock, retrieve_subscription_mock, coupon_create_mock
    ):
        coupon_create_mock.return_value = MagicMock(id="test-coupon-id")

        self.current_owner.plan = PlanName.CODECOV_PRO_YEARLY_LEGACY.value
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"apply_cancellation_discount": True},
        )

        assert not modify_customer_mock.called
        assert not coupon_create_mock.called
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["subscription_detail"]["customer"]["discount"] is None

    @patch("services.task.TaskService.delete_owner")
    def test_destroy_triggers_delete_owner_task(self, delete_owner_mock):
        response = self._destroy(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_owner_mock.assert_called_once_with(self.current_owner.ownerid)

    def test_destroy_not_own_account_returns_404(self):
        owner = OwnerFactory(admins=[self.current_owner.ownerid])
        response = self._destroy(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_org_with_account(self):
        account = AccountFactory(
            name="Hello World",
            plan_seat_count=5,
            free_seat_count=3,
            plan="users-enterprisey",
            is_delinquent=False,
        )
        InvoiceBillingFactory(is_active=True, account=account)
        org_1 = OwnerFactory(
            account=account,
            service=Service.GITHUB.value,
            username="Test",
            delinquent=True,
            uses_invoice=False,
        )
        org_2 = OwnerFactory(
            account=account,
            service=Service.GITHUB.value,
        )
        activated_owner = OwnerFactory(
            user=UserFactory(), organizations=[org_1.ownerid, org_2.ownerid]
        )
        account.users.add(activated_owner.user)
        student_owner = OwnerFactory(
            user=UserFactory(),
            student=True,
            organizations=[org_1.ownerid, org_2.ownerid],
        )
        account.users.add(student_owner.user)
        other_activated_owner = OwnerFactory(
            user=UserFactory(), organizations=[org_2.ownerid]
        )
        account.users.add(other_activated_owner.user)
        other_student_owner = OwnerFactory(
            user=UserFactory(),
            student=True,
            organizations=[org_2.ownerid],
        )
        account.users.add(other_student_owner.user)
        org_1.plan_activated_users = [activated_owner.ownerid, student_owner.ownerid]
        org_1.admins = [activated_owner.ownerid]
        org_1.save()
        org_2.plan_activated_users = [
            activated_owner.ownerid,
            student_owner.ownerid,
            other_activated_owner.ownerid,
            other_student_owner.ownerid,
        ]
        org_2.save()

        self.client.force_login_owner(activated_owner)
        response = self._retrieve(
            kwargs={"service": Service.GITHUB.value, "owner_username": org_1.username}
        )
        assert response.status_code == status.HTTP_200_OK
        # these fields are all overridden by account fields if the org has an account
        self.assertEqual(org_1.activated_user_count, 1)
        self.assertEqual(org_1.activated_student_count, 1)
        self.assertTrue(org_1.delinquent)
        self.assertFalse(org_1.uses_invoice)
        self.assertEqual(org_1.plan_user_count, 1)
        expected_response = {
            "activated_user_count": 2,
            "activated_student_count": 2,
            "delinquent": False,
            "uses_invoice": True,
            "plan": {
                "marketing_name": "Enterprise Cloud",
                "value": PlanName.ENTERPRISE_CLOUD_YEARLY.value,
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "quantity": 5,
            },
            "root_organization": None,
            "integration_id": org_1.integration_id,
            "plan_auto_activate": org_1.plan_auto_activate,
            "inactive_user_count": 0,
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": org_1.name,
            "email": org_1.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": org_1.plan_provider,
            "student_count": 1,
            "schedule_detail": None,
        }
        self.assertDictEqual(response.data["plan"], expected_response["plan"])
        self.assertDictEqual(response.data, expected_response)


@override_settings(IS_ENTERPRISE=True)
class EnterpriseAccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(
            reverse("account_details-detail", kwargs=kwargs), data=data, format="json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "gitlab"
        self.current_owner = OwnerFactory(
            stripe_customer_id=1000,
            service=Service.GITHUB.value,
            service_id="10238974029348",
        )
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_retrieve_own_account_give_200(self):
        response = self._retrieve(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        )
        assert response.status_code == status.HTTP_200_OK
