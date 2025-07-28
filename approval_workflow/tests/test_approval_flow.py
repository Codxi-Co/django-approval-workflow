"""Test suite for the approval_workflow package.

This module contains comprehensive tests for:
- Flow creation via start_flow()
- Role-based permission checks via can_user_approve()
- Action handling via advance_flow()
- Integration with Django models and permissions
"""

import pytest
from django.test import override_settings
from django.apps import apps
from approval_workflow.models import ApprovalInstance
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.choices import ApprovalStatus
from approval_workflow.utils import can_user_approve
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def setup_roles_and_users(django_user_model):
    Role = apps.get_model("testapp", "MockRole")
    senior = Role.objects.create(name="Senior")
    junior = Role.objects.create(name="Junior", parent=senior)

    manager = django_user_model.objects.create(username="manager", role=senior)
    employee = django_user_model.objects.create(username="employee", role=junior)

    return manager, employee


@pytest.mark.django_db
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def test_can_user_approve_with_ancestor_check(django_user_model):
    Role = apps.get_model("testapp", "MockRole")
    senior = Role.objects.create(name="Senior")
    junior = Role.objects.create(name="Junior", parent=senior)

    senior_user = django_user_model.objects.create(username="manager", role=senior)
    junior_user = django_user_model.objects.create(username="employee", role=junior)

    instance = ApprovalInstance(assigned_to=junior_user)
    assert can_user_approve(instance, senior_user)
    assert can_user_approve(instance, junior_user)
    outsider = django_user_model.objects.create(username="outsider")
    assert not can_user_approve(instance, outsider)


@pytest.mark.django_db
def test_start_flow_creates_instances(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    dummy = MockRequestModel.objects.create(title="Test Request", description="Testing")
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    assert flow.instances.count() == 2
    assert flow.instances.get(step_number=1).assigned_to == employee


@pytest.mark.django_db
def test_start_flow_invalid_input_raises_error(setup_roles_and_users):
    manager, _ = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test Request", description="Testing")

    with pytest.raises(ValueError, match="Missing 'assigned_to'"):
        start_flow(dummy, [{"step": 1}])

    with pytest.raises(ValueError, match="'step' must be a positive integer"):
        start_flow(dummy, [{"step": "one", "assigned_to": manager}])


@pytest.mark.django_db
def test_can_user_approve_exact_match(setup_roles_and_users):
    manager, _ = setup_roles_and_users
    instance = ApprovalInstance(assigned_to=manager)
    assert can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_ancestor(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    instance = ApprovalInstance(assigned_to=employee)
    assert can_user_approve(instance, manager)


@pytest.mark.django_db
def test_can_user_approve_with_allow_higher_level_true(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    instance = ApprovalInstance(assigned_to=employee)
    assert can_user_approve(instance, manager, allow_higher_level=True)
    assert can_user_approve(instance, employee, allow_higher_level=True)


@pytest.mark.django_db
def test_can_user_approve_with_allow_higher_level_false(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    instance = ApprovalInstance(assigned_to=employee)
    assert not can_user_approve(instance, manager, allow_higher_level=False)
    assert can_user_approve(instance, employee, allow_higher_level=False)


@pytest.mark.django_db
def test_can_user_approve_without_roles_allow_higher_level_false(django_user_model):
    user1 = django_user_model.objects.create(username="user1")
    user2 = django_user_model.objects.create(username="user2")
    instance = ApprovalInstance(assigned_to=user1)
    
    assert can_user_approve(instance, user1, allow_higher_level=False)
    assert not can_user_approve(instance, user2, allow_higher_level=False)


@pytest.mark.django_db
def test_approve_step(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test Request", description="Testing")

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )
    step = flow.instances.get(step_number=1)
    result = advance_flow(step, action="approved", user=employee)

    step.refresh_from_db()
    assert step.status == ApprovalStatus.APPROVED
    assert result.step_number == 2


@pytest.mark.django_db
def test_reject_deletes_future_steps(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test Request", description="Testing")

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )
    step = flow.instances.get(step_number=1)
    result = advance_flow(step, action="rejected", user=employee)

    step.refresh_from_db()
    assert step.status == ApprovalStatus.REJECTED
    assert ApprovalInstance.objects.filter(step_number=2).count() == 0
    assert result is None


@pytest.mark.django_db
def test_resubmission_creates_new_steps(setup_roles_and_users):
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Test Request", description="Testing")

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
        ],
    )
    step = flow.instances.get(step_number=1)

    result = advance_flow(
        step,
        action="resubmission",
        user=employee,
        resubmission_steps=[{"step": 2, "assigned_to": manager}],
    )

    assert step.status == ApprovalStatus.NEEDS_RESUBMISSION
    assert result.step_number == 2
    assert result.assigned_to == manager
