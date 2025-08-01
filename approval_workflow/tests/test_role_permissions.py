"""Tests for role-based permissions and user authorization."""

import pytest
from django.test import override_settings
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.models import ApprovalInstance
from approval_workflow.services import start_flow
from approval_workflow.utils import can_user_approve

User = get_user_model()


@pytest.mark.django_db
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def test_can_user_approve_with_ancestor_check(django_user_model):
    """Test role-based authorization with ancestor checking."""
    Role = apps.get_model("testapp", "MockRole")
    senior = Role.objects.create(name="Senior")
    junior = Role.objects.create(name="Junior", parent=senior)

    manager = django_user_model.objects.create(username="manager", role=senior)
    employee = django_user_model.objects.create(username="employee", role=junior)

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Role Test", description="Testing role permissions"
    )

    # Create flow with allow_higher_level=True for first test
    flow = start_flow(
        dummy, [{"step": 1, "assigned_to": employee, "allow_higher_level": True}]
    )
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    # Employee should be able to approve (direct assignment)
    assert can_user_approve(instance, employee)

    # Manager should be able to approve since allow_higher_level=True
    assert can_user_approve(instance, manager)

    # Test with allow_higher_level=False
    instance.allow_higher_level = False
    instance.save()

    # Employee should still be able to approve (direct assignment)
    assert can_user_approve(instance, employee)

    # Manager should NOT be able to approve since allow_higher_level=False
    assert not can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_exact_match(setup_roles_and_users):
    """Test authorization for exact user match."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test", description="Testing")

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    assert can_user_approve(instance, employee)
    # Manager cannot approve since allow_higher_level defaults to False
    assert not can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_ancestor(setup_roles_and_users):
    """Test authorization for ancestor roles."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test", description="Testing")

    flow = start_flow(
        dummy, [{"step": 1, "assigned_to": employee, "allow_higher_level": True}]
    )
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    assert can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_with_allow_higher_level_true(setup_roles_and_users):
    """Test authorization with allow_higher_level=True."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test", description="Testing")

    flow = start_flow(
        dummy, [{"step": 1, "assigned_to": employee, "allow_higher_level": True}]
    )
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    assert can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_with_allow_higher_level_false(setup_roles_and_users):
    """Test authorization with allow_higher_level=False."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test", description="Testing")

    # allow_higher_level defaults to False, so no need to specify it
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    assert not can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_without_roles_allow_higher_level_false(django_user_model):
    """Test authorization without role configuration."""
    employee = django_user_model.objects.create(username="employee")
    manager = django_user_model.objects.create(username="manager")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test", description="Testing")

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    # Only exact match should work without roles (allow_higher_level defaults to False)
    assert can_user_approve(instance, employee)
    assert not can_user_approve(instance, manager)
