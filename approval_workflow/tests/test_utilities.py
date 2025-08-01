"""Tests for utility functions and helper methods."""

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.utils import (
    get_current_approval,
    get_next_approval,
    get_full_approvals,
    get_approval_flow,
    get_approval_summary,
    get_user_approval_step_ids,
    get_user_approval_steps,
    get_user_approval_summary,
)

User = get_user_model()


@pytest.mark.django_db
def test_get_current_approval(setup_roles_and_users):
    """Test get_current_approval utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Current Approval Test", description="Testing get_current_approval"
    )

    # No approval flow exists yet
    assert get_current_approval(dummy) is None

    # Create approval flow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Should return first step
    current = get_current_approval(dummy)
    assert current is not None
    assert current.step_number == 1
    assert current.assigned_to == employee

    # Approve first step
    advance_flow(current, action="approved", user=employee)

    # Should now return second step
    current = get_current_approval(dummy)
    assert current is not None
    assert current.step_number == 2
    assert current.assigned_to == manager

    # Approve final step
    advance_flow(current, action="approved", user=manager)

    # Should return None when complete
    current = get_current_approval(dummy)
    assert current is None


@pytest.mark.django_db
def test_get_next_approval(setup_roles_and_users):
    """Test get_next_approval utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Next Approval Test", description="Testing get_next_approval"
    )

    # Create approval flow
    start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # Should return second step
    next_step = get_next_approval(dummy)
    assert next_step is not None
    assert next_step.step_number == 2
    assert next_step.assigned_to == manager

    # Approve first step
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=employee)

    # Should now return third step
    next_step = get_next_approval(dummy)
    assert next_step is not None
    assert next_step.step_number == 3
    assert next_step.assigned_to == employee

    # Approve second step
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=manager)

    # Should return None when at final step
    next_step = get_next_approval(dummy)
    assert next_step is None


@pytest.mark.django_db
def test_get_full_approvals(setup_roles_and_users):
    """Test get_full_approvals utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Full Approvals Test", description="Testing get_full_approvals"
    )

    # No approvals initially
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 0

    # Create approval flow
    start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # Should return all approval instances
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 3

    # Verify order and content
    assert approvals[0].step_number == 1
    assert approvals[1].step_number == 2
    assert approvals[2].step_number == 3

    # Approve first step
    advance_flow(approvals[0], action="approved", user=employee)

    # Should still return all instances (including completed ones)
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 3


@pytest.mark.django_db
def test_get_approval_flow(setup_roles_and_users):
    """Test get_approval_flow utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Approval Flow Test", description="Testing get_approval_flow"
    )

    # No flow initially
    flow = get_approval_flow(dummy)
    assert flow is None

    # Create approval flow
    created_flow = start_flow(
        dummy,
        [{"step": 1, "assigned_to": employee}, {"step": 2, "assigned_to": manager}],
    )

    # Should return the flow
    retrieved_flow = get_approval_flow(dummy)
    assert retrieved_flow is not None
    assert retrieved_flow.id == created_flow.id


@pytest.mark.django_db
def test_get_full_approvals_with_resubmission(setup_roles_and_users):
    """Test get_full_approvals includes resubmission steps."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Resubmission Approvals Test", description="Testing with resubmission"
    )

    # Create initial flow
    start_flow(
        dummy,
        [{"step": 1, "assigned_to": employee}, {"step": 2, "assigned_to": manager}],
    )

    # Initial approvals
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2

    # Request resubmission with explicit step number to avoid conflicts
    current = get_current_approval(dummy)
    advance_flow(
        current,
        action="resubmission",
        user=employee,
        resubmission_steps=[
            {"step": 3, "assigned_to": specialist}
        ],  # Step 3 to avoid conflict with existing steps 1,2
    )

    # Should now include resubmission step
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2  # Original current + new step (second was deleted)


@pytest.mark.django_db
def test_utility_functions_with_different_objects(setup_roles_and_users):
    """Test utility functions work correctly with different object instances."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    # Create two different objects
    dummy1 = MockRequestModel.objects.create(title="Object 1", description="First")
    dummy2 = MockRequestModel.objects.create(title="Object 2", description="Second")

    # Create flows for both
    start_flow(dummy1, [{"step": 1, "assigned_to": employee}])
    start_flow(dummy2, [{"step": 1, "assigned_to": manager}])

    # Verify utilities return correct data for each object
    current1 = get_current_approval(dummy1)
    current2 = get_current_approval(dummy2)

    assert current1.assigned_to == employee
    assert current2.assigned_to == manager

    approvals1 = get_full_approvals(dummy1)
    approvals2 = get_full_approvals(dummy2)

    assert len(approvals1) == 1
    assert len(approvals2) == 1
    assert approvals1[0].assigned_to == employee
    assert approvals2[0].assigned_to == manager


@pytest.mark.django_db
def test_get_approval_summary_comprehensive(setup_roles_and_users):
    """Test get_approval_summary with various workflow states."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Summary Test", description="Testing approval summary"
    )

    # Create multi-step workflow
    start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # Initial summary
    summary = get_approval_summary(dummy)
    assert summary["total_steps"] == 3
    assert summary["completed_steps"] == 0
    assert summary["current_step"].step_number == 1  # current_step is an instance
    assert summary["is_complete"] is False

    # Approve first step
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=employee)

    # Updated summary
    summary = get_approval_summary(dummy)
    assert summary["completed_steps"] == 1
    assert summary["current_step"].step_number == 2

    # Complete workflow
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=manager)
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=employee)

    # Final summary
    summary = get_approval_summary(dummy)
    assert summary["completed_steps"] == 3
    assert summary["current_step"] is None
    assert summary["is_complete"] is True


@pytest.mark.django_db
def test_get_user_approval_step_ids(setup_roles_and_users):
    """Test get_user_approval_step_ids utility function."""
    manager, employee = setup_roles_and_users
    third_user = User.objects.create(username="third_user")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    # Create multiple documents with workflows
    doc1 = MockRequestModel.objects.create(title="Doc 1", description="Test")
    doc2 = MockRequestModel.objects.create(title="Doc 2", description="Test")

    # Create workflows with different user assignments
    flow1 = start_flow(
        doc1,
        [
            {"step": 1, "assigned_to": employee},  # current
            {"step": 2, "assigned_to": manager},  # pending
            {"step": 3, "assigned_to": employee},  # pending
        ],
    )

    flow2 = start_flow(
        doc2,
        [
            {"step": 1, "assigned_to": manager},  # current
            {"step": 2, "assigned_to": employee},  # pending
        ],
    )

    # Test get all step IDs for employee (should get 3 steps: step 1 and 3 from flow1, step 2 from flow2)
    employee_step_ids = get_user_approval_step_ids(employee)
    assert len(employee_step_ids) == 3  # Step 1 and 3 from flow1, Step 2 from flow2

    # Test get current step IDs for employee (should get 1 step)
    current_step_ids = get_user_approval_step_ids(employee, status="current")
    assert len(current_step_ids) == 1

    # Test get pending step IDs for employee (should get 2 steps)
    pending_step_ids = get_user_approval_step_ids(employee, status="pending")
    assert len(pending_step_ids) == 2

    # Test get all step IDs for manager (should get 2 steps)
    manager_step_ids = get_user_approval_step_ids(manager)
    assert len(manager_step_ids) == 2

    # Test user with no assignments
    third_user_step_ids = get_user_approval_step_ids(third_user)
    assert len(third_user_step_ids) == 0


@pytest.mark.django_db
def test_get_user_approval_steps(setup_roles_and_users):
    """Test get_user_approval_steps utility function."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    doc = MockRequestModel.objects.create(title="Test Doc", description="Test")

    # Create workflow
    flow = start_flow(
        doc,
        [
            {"step": 1, "assigned_to": employee, "extra_fields": {"priority": "high"}},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test get all steps for employee
    employee_steps = get_user_approval_steps(employee)
    assert len(employee_steps) == 1
    assert employee_steps[0].step_number == 1
    assert employee_steps[0].extra_fields == {"priority": "high"}
    assert employee_steps[0].flow == flow

    # Test get current steps for employee
    current_steps = get_user_approval_steps(employee, status="current")
    assert len(current_steps) == 1
    assert current_steps[0].status == "current"

    # Test get pending steps for manager
    pending_steps = get_user_approval_steps(manager, status="pending")
    assert len(pending_steps) == 1
    assert pending_steps[0].status == "pending"


@pytest.mark.django_db
def test_get_user_approval_summary(setup_roles_and_users):
    """Test get_user_approval_summary utility function."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    doc1 = MockRequestModel.objects.create(title="Doc 1", description="Test")
    doc2 = MockRequestModel.objects.create(title="Doc 2", description="Test")

    # Create workflows
    flow1 = start_flow(
        doc1,
        [
            {"step": 1, "assigned_to": employee},  # current
            {"step": 2, "assigned_to": manager},  # pending
        ],
    )

    flow2 = start_flow(
        doc2,
        [
            {"step": 1, "assigned_to": employee},  # current (will be approved)
            {"step": 2, "assigned_to": employee},  # pending
        ],
    )

    # Get initial summary for employee
    summary = get_user_approval_summary(employee)
    assert summary["total_steps"] == 3  # 2 current + 1 pending
    assert summary["current_count"] == 2  # 2 current steps
    assert summary["pending_count"] == 1  # 1 pending step
    assert summary["approved_count"] == 0
    assert summary["rejected_count"] == 0
    assert len(summary["current_step_ids"]) == 2
    assert len(summary["recent_steps"]) == 3

    # Approve one step
    current_step = get_current_approval(doc1)
    advance_flow(current_step, action="approved", user=employee)

    # Get updated summary
    summary = get_user_approval_summary(employee)
    assert summary["total_steps"] == 3  # Still 3 steps total
    assert summary["current_count"] == 1  # Only employee step 1 from doc2 is current
    assert summary["pending_count"] == 1  # employee step 2 from doc2 is still pending
    assert summary["approved_count"] == 1  # 1 approved step

    # Test user with no assignments
    third_user = User.objects.create(username="no_assignments")
    empty_summary = get_user_approval_summary(third_user)
    assert empty_summary["total_steps"] == 0
    assert empty_summary["current_count"] == 0
    assert len(empty_summary["current_step_ids"]) == 0
    assert len(empty_summary["recent_steps"]) == 0
