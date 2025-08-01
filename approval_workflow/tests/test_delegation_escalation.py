"""Tests for delegation and escalation functionality."""

import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from django.apps import apps
from django.contrib.auth import get_user_model

from approval_workflow.services import start_flow, advance_flow
from approval_workflow.choices import ApprovalStatus
from approval_workflow.utils import get_current_approval

User = get_user_model()


@pytest.mark.django_db
def test_delegation_functionality(setup_roles_and_users):
    """Test that delegation creates new step with delegated user."""
    manager, employee = setup_roles_and_users

    # Create a third user to delegate to
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Delegation Test", description="Testing delegation"
    )

    # Create workflow with employee as first step
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Get current step (should be assigned to employee)
    current_step = get_current_approval(dummy)
    assert current_step.assigned_to == employee
    assert current_step.status == ApprovalStatus.CURRENT
    original_step_id = current_step.id

    # Delegate to specialist
    delegated_step = advance_flow(
        instance=current_step,
        action="delegated",
        user=employee,
        delegate_to=specialist,
        comment="Delegating to specialist for review",
    )

    # Verify original step is marked as DELEGATED
    current_step.refresh_from_db()
    assert current_step.status == ApprovalStatus.DELEGATED
    assert current_step.action_user == employee
    assert current_step.comment == "Delegating to specialist for review"

    # Verify new step is created and is CURRENT
    assert delegated_step.id != original_step_id
    assert delegated_step.step_number == current_step.step_number  # Same step number
    assert delegated_step.assigned_to == specialist
    assert delegated_step.status == ApprovalStatus.CURRENT
    assert delegated_step.form == current_step.form  # Form should be copied

    # Verify the new step is the current step for the workflow
    new_current = get_current_approval(dummy)
    assert new_current.id == delegated_step.id


@pytest.mark.django_db
def test_delegation_requires_delegate_to_parameter(setup_roles_and_users):
    """Test that delegation fails without delegate_to parameter."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Delegation Error Test", description="Testing"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)

    # Try to delegate without delegate_to parameter
    with pytest.raises(ValueError, match="delegate_to user must be provided"):
        advance_flow(
            instance=current_step, action="delegated", user=employee, delegate_to=None
        )


@pytest.mark.django_db
@override_settings(
    APPROVAL_HEAD_MANAGER_FIELD="head_manager",
    APPROVAL_ROLE_MODEL="testapp.MockRole",
    APPROVAL_ROLE_FIELD="role",
)
def test_escalation_with_head_manager_field(setup_roles_and_users):
    """Test escalation using APPROVAL_HEAD_MANAGER_FIELD setting."""
    manager, employee = setup_roles_and_users

    # Create head manager and set as employee's head manager
    head_manager = User.objects.create(username="head_manager")
    employee.head_manager = head_manager
    employee.save()

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Escalation Test", description="Testing escalation"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)
    original_step_id = current_step.id

    # Escalate to head manager
    escalated_step = advance_flow(
        instance=current_step,
        action="escalated",
        user=employee,
        comment="Escalating to head manager for approval",
    )

    # Verify original step is marked as ESCALATED
    current_step.refresh_from_db()
    assert current_step.status == ApprovalStatus.ESCALATED
    assert current_step.action_user == employee
    assert current_step.comment == "Escalating to head manager for approval"

    # Verify new step is created and assigned to head manager
    assert escalated_step.id != original_step_id
    assert escalated_step.step_number == current_step.step_number  # Same step number
    assert escalated_step.assigned_to == head_manager
    assert escalated_step.status == ApprovalStatus.CURRENT
    assert escalated_step.form == current_step.form


@pytest.mark.django_db
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def test_escalation_with_role_hierarchy(setup_roles_and_users):
    """Test escalation using role hierarchy when no head manager field."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Role Escalation Test", description="Testing role-based escalation"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)

    # Escalate (should find manager via role hierarchy)
    escalated_step = advance_flow(
        instance=current_step,
        action="escalated",
        user=employee,
        comment="Escalating via role hierarchy",
    )

    # Verify escalation went to manager (parent role)
    assert escalated_step.assigned_to == manager
    assert escalated_step.status == ApprovalStatus.CURRENT

    # Verify original step is escalated
    current_step.refresh_from_db()
    assert current_step.status == ApprovalStatus.ESCALATED


@pytest.mark.django_db
def test_escalation_fails_without_higher_manager():
    """Test that escalation fails when no higher manager is found."""
    # Create user without head manager or role hierarchy
    employee = User.objects.create(username="isolated_employee")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Escalation Fail Test", description="Testing"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)

    # Try to escalate without any higher manager
    with pytest.raises(ValueError, match="No head manager or higher role user found"):
        advance_flow(instance=current_step, action="escalated", user=employee)


@pytest.mark.django_db
def test_delegation_with_form_data(setup_roles_and_users):
    """Test that delegation preserves form data from original step."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Form Delegation Test", description="Testing"
    )

    # Create form if dynamic form model is configured
    try:
        from django.conf import settings

        form_model_path = getattr(settings, "APPROVAL_DYNAMIC_FORM_MODEL", None)
        if form_model_path:
            form_model = apps.get_model(form_model_path)
            test_form = form_model.objects.create(
                name="Test Form", schema={"fields": ["name", "email"]}
            )
            steps = [{"step": 1, "assigned_to": employee, "form": test_form}]
        else:
            steps = [{"step": 1, "assigned_to": employee}]
    except:
        steps = [{"step": 1, "assigned_to": employee}]

    flow = start_flow(dummy, steps)
    current_step = get_current_approval(dummy)

    # Delegate the step
    delegated_step = advance_flow(
        instance=current_step,
        action="delegated",
        user=employee,
        delegate_to=specialist,
        comment="Delegating with form",
    )

    # Verify form is preserved
    assert delegated_step.form == current_step.form


@pytest.mark.django_db
def test_handler_integration_for_delegation_and_escalation(setup_roles_and_users):
    """Test that on_delegate and on_escalate handlers are called."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Handler Test", description="Testing handlers"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Mock the handler to verify methods are called
    with patch(
        "approval_workflow.services.get_handler_for_instance"
    ) as mock_get_handler:
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        # Test delegation handler
        current_step = get_current_approval(dummy)
        advance_flow(
            instance=current_step,
            action="delegated",
            user=employee,
            delegate_to=specialist,
        )

        # Verify on_delegate was called
        mock_handler.on_delegate.assert_called_once_with(current_step)

        # Reset mock for escalation test
        mock_handler.reset_mock()

        # Create new flow for escalation test
        dummy2 = MockRequestModel.objects.create(
            title="Handler Test 2", description="Testing escalation handler"
        )
        flow2 = start_flow(dummy2, [{"step": 1, "assigned_to": employee}])
        current_step2 = get_current_approval(dummy2)

        # Set up head manager for escalation
        employee.head_manager = manager
        employee.save()

        with override_settings(APPROVAL_HEAD_MANAGER_FIELD="head_manager"):
            advance_flow(instance=current_step2, action="escalated", user=employee)

        # Verify on_escalate was called
        mock_handler.on_escalate.assert_called_once_with(current_step2)


@pytest.mark.django_db
def test_delegation_and_escalation_workflow_continues(setup_roles_and_users):
    """Test that workflow continues normally after delegation/escalation."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Workflow Continuation Test", description="Testing"
    )

    # Create 3-step workflow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": specialist},
        ],
    )

    # Step 1: Delegate to specialist
    step1 = get_current_approval(dummy)
    delegated_step = advance_flow(
        instance=step1, action="delegated", user=employee, delegate_to=specialist
    )

    # Specialist approves the delegated step
    advance_flow(instance=delegated_step, action="approved", user=specialist)

    # Verify workflow moves to step 2
    current_step = get_current_approval(dummy)
    assert current_step.step_number == 2
    assert current_step.assigned_to == manager

    # Step 2: Escalate to head manager (set manager's head manager)
    head_manager = User.objects.create(username="head_manager")
    manager.head_manager = head_manager
    manager.save()

    with override_settings(APPROVAL_HEAD_MANAGER_FIELD="head_manager"):
        escalated_step = advance_flow(
            instance=current_step, action="escalated", user=manager
        )

    # Head manager approves escalated step
    advance_flow(instance=escalated_step, action="approved", user=head_manager)

    # Verify workflow moves to step 3
    current_step = get_current_approval(dummy)
    assert current_step.step_number == 3
    assert current_step.assigned_to == specialist

    # Complete workflow
    advance_flow(instance=current_step, action="approved", user=specialist)

    # Verify workflow is complete
    assert get_current_approval(dummy) is None


@pytest.mark.django_db
def test_advance_flow_supports_new_actions(setup_roles_and_users):
    """Test that advance_flow properly supports delegated and escalated actions."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Action Support Test", description="Testing"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    current_step = get_current_approval(dummy)

    # Test that delegated action is supported
    result = advance_flow(
        instance=current_step, action="delegated", user=employee, delegate_to=specialist
    )
    assert result is not None
    assert result.assigned_to == specialist

    # Create new flow for escalation test
    dummy2 = MockRequestModel.objects.create(
        title="Escalation Action Test", description="Testing"
    )
    flow2 = start_flow(dummy2, [{"step": 1, "assigned_to": employee}])
    current_step2 = get_current_approval(dummy2)

    # Set up escalation
    employee.head_manager = manager
    employee.save()

    with override_settings(APPROVAL_HEAD_MANAGER_FIELD="head_manager"):
        # Test that escalated action is supported
        result = advance_flow(instance=current_step2, action="escalated", user=employee)
        assert result is not None
        assert result.assigned_to == manager
