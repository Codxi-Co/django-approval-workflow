"""Tests for flow creation and basic workflow operations."""

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.models import ApprovalInstance
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.choices import ApprovalStatus
from approval_workflow.utils import get_current_approval

User = get_user_model()


@pytest.mark.django_db
def test_start_flow_creates_instances(setup_roles_and_users):
    """Test that start_flow creates correct approval instances."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Flow Creation Test", description="Testing flow creation"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    instances = ApprovalInstance.objects.filter(flow=flow).order_by("step_number")
    assert len(instances) == 2

    # First step should be CURRENT
    assert instances[0].step_number == 1
    assert instances[0].assigned_to == employee
    assert instances[0].status == ApprovalStatus.CURRENT

    # Second step should be PENDING
    assert instances[1].step_number == 2
    assert instances[1].assigned_to == manager
    assert instances[1].status == ApprovalStatus.PENDING


@pytest.mark.django_db
def test_start_flow_invalid_input_raises_error(setup_roles_and_users):
    """Test that start_flow raises errors for invalid input."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Error Test", description="Testing")

    # Test invalid steps parameter
    with pytest.raises(ValueError, match="steps must be a list"):
        start_flow(dummy, "invalid")

    # Test missing step key
    with pytest.raises(ValueError, match="Missing 'step' key"):
        start_flow(dummy, [{"assigned_to": employee}])

    # Test invalid step number
    with pytest.raises(ValueError, match="'step' must be a positive integer"):
        start_flow(dummy, [{"step": 0, "assigned_to": employee}])


@pytest.mark.django_db
def test_approve_step(setup_roles_and_users):
    """Test basic step approval functionality."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Approval Test", description="Testing approval"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Approve first step
    first_step = ApprovalInstance.objects.get(flow=flow, step_number=1)
    next_step = advance_flow(
        first_step, action="approved", user=employee, comment="Looks good"
    )

    # Verify first step is approved
    first_step.refresh_from_db()
    assert first_step.status == ApprovalStatus.APPROVED
    assert first_step.action_user == employee
    assert first_step.comment == "Looks good"

    # Verify next step is now current
    assert next_step.step_number == 2
    assert next_step.status == ApprovalStatus.CURRENT
    assert next_step.assigned_to == manager


@pytest.mark.django_db
def test_reject_deletes_future_steps(setup_roles_and_users):
    """Test that rejecting a step deletes remaining steps."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Rejection Test", description="Testing rejection"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # Reject first step
    first_step = get_current_approval(dummy)
    result = advance_flow(
        first_step, action="rejected", user=employee, comment="Not approved"
    )

    # Should return None for rejected flow
    assert result is None

    # Verify first step is rejected
    first_step.refresh_from_db()
    assert first_step.status == ApprovalStatus.REJECTED
    assert first_step.comment == "Not approved"

    # Verify remaining steps are deleted
    remaining_steps = ApprovalInstance.objects.filter(
        flow=flow, step_number__gt=1
    ).count()
    assert remaining_steps == 0


@pytest.mark.django_db
def test_resubmission_creates_new_steps(setup_roles_and_users):
    """Test that resubmission creates new workflow steps."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")
    
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Resubmission Test", description="Testing resubmission"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Request resubmission from first step
    first_step = get_current_approval(dummy)
    new_steps = [
        {"step": 1, "assigned_to": specialist},
        {"step": 2, "assigned_to": manager},
    ]
    
    next_step = advance_flow(
        first_step,
        action="resubmission",
        user=employee,
        comment="Additional review needed",
        resubmission_steps=new_steps,
    )

    # Verify original step is marked for resubmission
    first_step.refresh_from_db()
    assert first_step.status == ApprovalStatus.NEEDS_RESUBMISSION
    assert first_step.comment == "Additional review needed"

    # Verify new steps are created
    assert next_step.step_number == 2  # Next available step number after step 1
    assert next_step.assigned_to == specialist
    assert next_step.status == ApprovalStatus.CURRENT

    # Verify total steps in flow
    total_steps = ApprovalInstance.objects.filter(flow=flow).count()
    assert total_steps == 3  # Original 1 (resubmitted) + 2 new steps


@pytest.mark.django_db
def test_invalid_action_still_raises_error(setup_roles_and_users):
    """Test that invalid actions still raise ValueError."""
    manager, employee = setup_roles_and_users
    
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Invalid Action Test", description="Testing"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)

    # Test invalid action raises error
    with pytest.raises(ValueError, match="Unsupported action: invalid_action"):
        advance_flow(
            instance=current_step,
            action="invalid_action",
            user=employee
        )


@pytest.mark.django_db
def test_extra_fields_functionality(setup_roles_and_users):
    """Test that extra_fields are stored and handled correctly."""
    manager, employee = setup_roles_and_users
    
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Extra Fields Test", description="Testing extra fields"
    )

    # Test flow with extra_fields
    extra_data = {
        "priority": "high",
        "department": "IT",
        "metadata": {
            "custom_approval_type": "expedited",
            "requires_signature": True
        }
    }
    
    flow = start_flow(
        dummy,
        [
            {
                "step": 1, 
                "assigned_to": employee,
                "extra_fields": extra_data
            },
            {
                "step": 2,
                "assigned_to": manager,
                "extra_fields": {"priority": "normal"}
            }
        ]
    )
    
    # Verify extra_fields are stored correctly in step 1
    step1 = ApprovalInstance.objects.filter(flow=flow, step_number=1).first()
    assert step1.extra_fields == extra_data
    
    # Verify extra_fields are stored correctly in step 2
    step2 = ApprovalInstance.objects.filter(flow=flow, step_number=2).first()
    assert step2.extra_fields == {"priority": "normal"}
    
    # Test without extra_fields (should be None)
    flow2 = start_flow(
        MockRequestModel.objects.create(title="No Extra Fields", description="Test"),
        [{"step": 1, "assigned_to": employee}]
    )
    
    instance_no_extra = ApprovalInstance.objects.filter(flow=flow2).first()
    assert instance_no_extra.extra_fields is None