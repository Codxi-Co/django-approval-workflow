"""Tests for SLA duration and new database fields."""

import pytest
from datetime import timedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.services import start_flow
from approval_workflow.models import ApprovalInstance

User = get_user_model()


@pytest.mark.django_db
def test_sla_duration_creation(setup_roles_and_users):
    """Test that SLA duration is properly stored in database."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="SLA Test", description="Testing SLA duration"
    )

    # Create workflow with SLA duration
    sla_duration = timedelta(days=2, hours=4)
    flow = start_flow(
        dummy,
        [
            {
                "step": 1,
                "assigned_to": employee,
                "sla_duration": sla_duration,
                "allow_higher_level": True,
            },
            {
                "step": 2,
                "assigned_to": manager,
                "sla_duration": timedelta(hours=8),
                "allow_higher_level": False,
            },
        ],
    )

    # Verify SLA duration is stored correctly
    instances = ApprovalInstance.objects.filter(flow=flow).order_by("step_number")

    assert instances[0].sla_duration == sla_duration
    assert instances[0].allow_higher_level is True

    assert instances[1].sla_duration == timedelta(hours=8)
    assert instances[1].allow_higher_level is False


@pytest.mark.django_db
def test_sla_duration_optional(setup_roles_and_users):
    """Test that SLA duration is optional."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="SLA Optional Test", description="Testing optional SLA"
    )

    # Create workflow without SLA duration
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager, "allow_higher_level": True},
        ],
    )

    # Verify SLA duration is None and allow_higher_level defaults work
    instances = ApprovalInstance.objects.filter(flow=flow).order_by("step_number")

    assert instances[0].sla_duration is None
    assert instances[0].allow_higher_level is False  # Default value

    assert instances[1].sla_duration is None
    assert instances[1].allow_higher_level is True


@pytest.mark.django_db
def test_allow_higher_level_database_field(setup_roles_and_users):
    """Test that allow_higher_level is read from database."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Database Field Test", description="Testing database field"
    )

    # Create workflow with allow_higher_level=True
    flow = start_flow(
        dummy, [{"step": 1, "assigned_to": employee, "allow_higher_level": True}]
    )

    instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    # Verify the field is stored in database
    assert instance.allow_higher_level is True

    # Change the field and verify it's persisted
    instance.allow_higher_level = False
    instance.save()

    # Reload from database
    instance.refresh_from_db()
    assert instance.allow_higher_level is False


@pytest.mark.django_db
def test_sla_duration_inheritance_in_delegation(setup_roles_and_users):
    """Test that SLA duration is inherited during delegation."""
    from approval_workflow.services import advance_flow

    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Delegation SLA Test", description="Testing SLA inheritance"
    )

    # Create workflow with SLA duration
    sla_duration = timedelta(days=1, hours=12)
    flow = start_flow(
        dummy,
        [
            {
                "step": 1,
                "assigned_to": employee,
                "sla_duration": sla_duration,
                "allow_higher_level": True,
            }
        ],
    )

    original_instance = ApprovalInstance.objects.get(flow=flow, step_number=1)

    # Delegate the step
    delegated_instance = advance_flow(
        original_instance,
        action="delegated",
        user=employee,
        delegate_to=specialist,
        comment="Delegating for specialized review",
    )

    # Verify SLA duration and allow_higher_level are inherited
    assert delegated_instance.sla_duration == sla_duration
    assert delegated_instance.allow_higher_level is True
    assert delegated_instance.assigned_to == specialist
