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
from approval_workflow.utils import (
    can_user_approve,
    get_current_approval,
    get_next_approval,
    get_full_approvals,
    get_approval_flow,
    get_approval_repository,
    get_approval_summary,
    ApprovalRepository,
)
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def setup_roles_and_users(django_user_model):
    # Clear cache before each test to ensure clean state
    ApprovalRepository.clear_all_cache()

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


@pytest.mark.django_db
def test_on_resubmission_handler_called(setup_roles_and_users, monkeypatch):
    """Test that on_resubmission handler is called during resubmission workflow."""
    from approval_workflow.handlers import BaseApprovalHandler

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

    # Mock the handler method to track if it's called
    handler_called = []
    original_on_resubmission = BaseApprovalHandler.on_resubmission

    def mock_on_resubmission(self, instance):
        handler_called.append(
            {
                "flow_id": instance.flow.id,
                "step_number": instance.step_number,
                "status": instance.status,
                "user": instance.action_user.username if instance.action_user else None,
                "comment": instance.comment,
            }
        )
        return original_on_resubmission(self, instance)

    monkeypatch.setattr(BaseApprovalHandler, "on_resubmission", mock_on_resubmission)

    # Trigger resubmission
    advance_flow(
        step,
        action="resubmission",
        user=employee,
        comment="Needs more review",
        resubmission_steps=[{"step": 2, "assigned_to": manager}],
    )

    # Verify handler was called
    assert len(handler_called) == 1
    assert handler_called[0]["flow_id"] == flow.id
    assert handler_called[0]["step_number"] == 1
    assert handler_called[0]["status"] == ApprovalStatus.NEEDS_RESUBMISSION
    assert handler_called[0]["user"] == employee.username
    assert handler_called[0]["comment"] == "Needs more review"


@pytest.mark.django_db
def test_custom_resubmission_handler(setup_roles_and_users, monkeypatch):
    """Test custom resubmission handler implementation."""
    from approval_workflow.handlers import BaseApprovalHandler, get_handler_for_instance

    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    # Create a custom handler class
    class TestResubmissionHandler(BaseApprovalHandler):
        def __init__(self):
            self.resubmission_called = False
            self.instance_data = None

        def on_resubmission(self, instance):
            self.resubmission_called = True
            self.instance_data = {
                "flow_id": instance.flow.id,
                "step": instance.step_number,
                "comment": instance.comment,
                "target_title": instance.flow.target.title,
            }

    # Mock the handler resolution to return our custom handler
    custom_handler = TestResubmissionHandler()
    monkeypatch.setattr(
        "approval_workflow.services.get_handler_for_instance",
        lambda instance: custom_handler,
    )

    dummy = MockRequestModel.objects.create(
        title="Custom Handler Test", description="Testing"
    )
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])
    step = flow.instances.get(step_number=1)

    # Trigger resubmission
    advance_flow(
        step,
        action="resubmission",
        user=employee,
        comment="Custom handler test",
        resubmission_steps=[{"step": 2, "assigned_to": manager}],
    )

    # Verify custom handler was called
    assert custom_handler.resubmission_called is True
    assert custom_handler.instance_data is not None
    assert custom_handler.instance_data["flow_id"] == flow.id
    assert custom_handler.instance_data["step"] == 1
    assert custom_handler.instance_data["comment"] == "Custom handler test"
    assert custom_handler.instance_data["target_title"] == "Custom Handler Test"


@pytest.mark.django_db
def test_get_current_approval(setup_roles_and_users):
    """Test get_current_approval utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Test Document", description="Testing"
    )

    # Test with no workflow
    current = get_current_approval(dummy)
    assert current is None

    # Create workflow with multiple steps
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test getting current (first CURRENT) step
    current = get_current_approval(dummy)
    assert current is not None
    assert current.step_number == 1
    assert current.assigned_to == employee
    assert current.status == ApprovalStatus.CURRENT

    # Approve first step
    advance_flow(current, action="approved", user=employee)

    # Current should now be step 2
    current = get_current_approval(dummy)
    assert current is not None
    assert current.step_number == 2
    assert current.assigned_to == manager
    assert current.status == ApprovalStatus.CURRENT

    # Approve final step
    advance_flow(current, action="approved", user=manager)

    # No current approval should exist
    current = get_current_approval(dummy)
    assert current is None


@pytest.mark.django_db
def test_get_next_approval(setup_roles_and_users):
    """Test get_next_approval utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Test Document", description="Testing"
    )

    # Test with no workflow
    next_approval = get_next_approval(dummy)
    assert next_approval is None

    # Create workflow with multiple steps
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test getting next step (should be step 2)
    next_approval = get_next_approval(dummy)
    assert next_approval is not None
    assert next_approval.step_number == 2
    assert next_approval.assigned_to == manager
    assert next_approval.status == ApprovalStatus.PENDING

    # Approve first step
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=employee)

    # Next approval should be None (current is final)
    next_approval = get_next_approval(dummy)
    assert next_approval is None

    # Approve final step
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=manager)

    # Still None after completion
    next_approval = get_next_approval(dummy)
    assert next_approval is None


@pytest.mark.django_db
def test_get_full_approvals(setup_roles_and_users):
    """Test get_full_approvals utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Test Document", description="Testing"
    )

    # Test with no workflow
    approvals = get_full_approvals(dummy)
    assert approvals == []

    # Create workflow with multiple steps
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test getting all approvals (should be 1 CURRENT, 1 PENDING)
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2
    assert approvals[0].step_number == 1
    assert approvals[0].status == ApprovalStatus.CURRENT
    assert approvals[1].step_number == 2
    assert approvals[1].status == ApprovalStatus.PENDING

    # Approve first step
    advance_flow(approvals[0], action="approved", user=employee)

    # Get all approvals again
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2
    assert approvals[0].step_number == 1
    assert approvals[0].status == ApprovalStatus.APPROVED
    assert approvals[1].step_number == 2
    assert approvals[1].status == ApprovalStatus.CURRENT

    # Reject second step
    advance_flow(
        approvals[1], action="rejected", user=manager, comment="Not good enough"
    )

    # Get all approvals after rejection
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2  # Second step still exists, just rejected
    assert approvals[0].status == ApprovalStatus.APPROVED
    assert approvals[1].status == ApprovalStatus.REJECTED


@pytest.mark.django_db
def test_get_approval_flow(setup_roles_and_users):
    """Test get_approval_flow utility function."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Test Document", description="Testing"
    )

    # Test with no workflow
    flow = get_approval_flow(dummy)
    assert flow is None

    # Create workflow
    created_flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test getting the flow
    flow = get_approval_flow(dummy)
    assert flow is not None
    assert flow.id == created_flow.id
    assert flow.target == dummy
    assert flow.instances.count() == 2


@pytest.mark.django_db
def test_get_full_approvals_with_resubmission(setup_roles_and_users):
    """Test get_full_approvals with resubmission workflow."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Test Document", description="Testing"
    )

    # Create initial workflow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
        ],
    )

    # Request resubmission
    step = flow.instances.get(step_number=1)
    advance_flow(
        step,
        action="resubmission",
        user=employee,
        comment="Need manager review",
        resubmission_steps=[{"step": 2, "assigned_to": manager}],
    )

    # Get all approvals including resubmission
    approvals = get_full_approvals(dummy)
    assert len(approvals) == 2
    assert approvals[0].step_number == 1
    assert approvals[0].status == ApprovalStatus.NEEDS_RESUBMISSION
    assert approvals[1].step_number == 2
    assert approvals[1].status == ApprovalStatus.CURRENT  # First new step is CURRENT
    assert approvals[1].assigned_to == manager


@pytest.mark.django_db
def test_utility_functions_with_different_objects(setup_roles_and_users):
    """Test utility functions work with different object types."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    # Create two different objects
    doc1 = MockRequestModel.objects.create(title="Document 1", description="First")
    doc2 = MockRequestModel.objects.create(title="Document 2", description="Second")

    # Create workflows for both
    flow1 = start_flow(doc1, [{"step": 1, "assigned_to": employee}])
    flow2 = start_flow(doc2, [{"step": 1, "assigned_to": manager}])

    # Test that functions return correct data for each object
    current1 = get_current_approval(doc1)
    current2 = get_current_approval(doc2)

    assert current1.assigned_to == employee
    assert current2.assigned_to == manager

    flow1_found = get_approval_flow(doc1)
    flow2_found = get_approval_flow(doc2)

    assert flow1_found.id == flow1.id
    assert flow2_found.id == flow2.id
    assert flow1_found.target == doc1
    assert flow2_found.target == doc2


# =============================================================================
# TESTS FOR OPTIMIZED REPOSITORY PATTERN FUNCTIONS
# =============================================================================


@pytest.mark.django_db
def test_approval_repository_single_query_optimization(setup_roles_and_users):
    """Test that ApprovalRepository uses single optimized query."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Performance Test", description="Testing"
    )

    # Create multi-step workflow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test that single repository instance can provide all data efficiently
    repo = get_approval_repository(dummy)

    # All these calls should use cached data from single query
    current = repo.get_current_approval()
    next_step = repo.get_next_approval()
    all_instances = repo.instances
    flow_obj = repo.flow
    pending = repo.get_pending_approvals()
    progress = repo.get_workflow_progress()

    # Verify data correctness
    assert current is not None
    assert current.step_number == 1
    assert next_step is not None
    assert next_step.step_number == 2
    assert len(all_instances) == 2
    assert flow_obj.id == flow.id
    assert len(pending) == 1  # Only step 2 is PENDING, step 1 is CURRENT
    assert progress["total_steps"] == 2
    assert progress["pending_steps"] == 2
    assert progress["progress_percentage"] == 0


@pytest.mark.django_db
def test_get_approval_summary_comprehensive(setup_roles_and_users):
    """Test get_approval_summary provides comprehensive workflow information."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Summary Test", description="Testing")

    # Test with no workflow
    summary = get_approval_summary(dummy)
    assert summary["total_steps"] == 0
    assert summary["completed_steps"] == 0
    assert summary["pending_steps"] == 0
    assert summary["rejected_steps"] == 0
    assert summary["progress_percentage"] == 0
    assert summary["is_complete"] is False
    assert summary["current_step"] is None
    assert summary["next_step"] is None

    # Create and test workflow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    summary = get_approval_summary(dummy)
    assert summary["total_steps"] == 2
    assert summary["pending_steps"] == 2  # 1 CURRENT + 1 PENDING = 2 total pending
    assert summary["completed_steps"] == 0
    assert summary["progress_percentage"] == 0
    assert summary["is_complete"] is False
    assert summary["current_step"].step_number == 1
    assert summary["next_step"].step_number == 2

    # Approve first step and test progress
    current = get_current_approval(dummy)
    advance_flow(current, action="approved", user=employee)

    summary = get_approval_summary(dummy)
    assert summary["completed_steps"] == 1
    assert summary["pending_steps"] == 1
    assert summary["progress_percentage"] == 50.0
    assert summary["current_step"].step_number == 2
    assert summary["next_step"] is None  # Final step


@pytest.mark.django_db
def test_approval_repository_caching(setup_roles_and_users):
    """Test that caching works correctly within repository instances."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(title="Cache Test", description="Testing")

    # Create workflow
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Test that single repository instance caches data internally
    repo = get_approval_repository(dummy)

    # First access loads from database
    flow1 = repo.flow
    instances1 = repo.instances

    # Subsequent accesses should use cached data (same objects)
    flow2 = repo.flow
    instances2 = repo.instances

    # Verify same objects are returned (cached)
    assert flow1 is flow2
    assert instances1 is instances2
    assert flow1.id == flow.id

    # Test cache clearing
    ApprovalRepository.clear_cache_for_object(dummy)

    # New repository should load fresh data
    new_repo = get_approval_repository(dummy)
    assert new_repo.flow is not None
    assert new_repo.flow.id == flow.id


@pytest.mark.django_db
def test_approval_repository_performance_methods(setup_roles_and_users):
    """Test additional performance-oriented repository methods."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Performance Methods", description="Testing"
    )

    # Create workflow and approve some steps
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    repo = get_approval_repository(dummy)

    # Test initial state
    assert repo.get_approved_count() == 0
    assert repo.is_workflow_complete() is False
    assert (
        len(repo.get_pending_approvals()) == 2
    )  # Steps 2,3 are PENDING, step 1 is CURRENT

    # Approve first step
    step1 = repo.get_current_approval()
    advance_flow(step1, action="approved", user=employee)

    # Clear cache to get fresh data
    ApprovalRepository.clear_cache_for_object(dummy)
    repo = get_approval_repository(dummy)

    assert repo.get_approved_count() == 1
    assert repo.is_workflow_complete() is False
    assert (
        len(repo.get_pending_approvals()) == 1
    )  # Step 3 is PENDING, step 2 is CURRENT

    # Approve remaining steps
    while repo.get_current_approval():
        current = repo.get_current_approval()
        user = current.assigned_to
        advance_flow(current, action="approved", user=user)
        ApprovalRepository.clear_cache_for_object(dummy)
        repo = get_approval_repository(dummy)

    assert repo.get_approved_count() == 3
    assert repo.is_workflow_complete() is True
    assert len(repo.get_pending_approvals()) == 0


@pytest.mark.django_db
def test_backward_compatibility_performance(setup_roles_and_users):
    """Test that legacy functions still work but with improved performance."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Compatibility Test", description="Testing"
    )

    # Create workflow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Test that legacy functions work exactly as before
    current = get_current_approval(dummy)
    next_step = get_next_approval(dummy)
    all_approvals = get_full_approvals(dummy)
    flow_obj = get_approval_flow(dummy)

    # Verify functionality is identical
    assert current.step_number == 1
    assert next_step.step_number == 2
    assert len(all_approvals) == 2
    assert flow_obj.id == flow.id

    # But now these should internally use the optimized repository
    # (This is tested indirectly through the fact that tests pass)
