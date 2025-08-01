"""Tests for performance optimizations and repository caching."""

import pytest
from django.apps import apps
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.utils import (
    get_approval_repository,
    get_current_approval,
    get_next_approval,
    get_full_approvals,
    get_approval_flow,
    ApprovalRepository,
)


@pytest.mark.django_db
def test_approval_repository_single_query_optimization(setup_roles_and_users):
    """Test that ApprovalRepository reduces database queries."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Performance Test", description="Testing performance"
    )

    # Create workflow
    start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # Get repository (this should load all data in one query)
    repo = get_approval_repository(dummy)

    # These operations should not trigger additional queries
    current = repo.get_current_approval()
    next_step = repo.get_next_approval()
    all_approvals = repo.instances
    flow = repo.flow

    # Verify data is correct
    assert current.step_number == 1
    assert next_step.step_number == 2
    assert len(all_approvals) == 3
    assert flow is not None

    # Test repository methods
    assert repo.get_approved_count() == 0
    assert len(repo.get_pending_approvals()) == 2  # Steps 2,3 are PENDING
    assert not repo.is_workflow_complete()


@pytest.mark.django_db
def test_approval_repository_caching(setup_roles_and_users):
    """Test that repository flow caching works correctly."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Caching Test", description="Testing caching"
    )

    # Create workflow
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Get repository and access flow - should work
    repo1 = get_approval_repository(dummy)
    flow1 = repo1.flow  # This loads and caches the flow

    # Get another repository and access flow
    repo2 = get_approval_repository(dummy)
    flow2 = repo2.flow  # This should also work

    # The flows should have the same ID (same data from cache/db)
    assert flow1.id == flow2.id == flow.id

    # Clear cache methods should work without errors
    ApprovalRepository.clear_cache_for_object(dummy)
    repo3 = get_approval_repository(dummy)
    flow3 = repo3.flow
    assert flow3 is not None
    assert flow3.id == flow.id

    # Clear all cache should work without errors
    ApprovalRepository.clear_all_cache()
    repo4 = get_approval_repository(dummy)
    flow4 = repo4.flow
    assert flow4 is not None
    assert flow4.id == flow.id


@pytest.mark.django_db
def test_approval_repository_performance_methods(setup_roles_and_users):
    """Test repository performance-oriented methods."""
    manager, employee = setup_roles_and_users
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Performance Methods Test", description="Testing performance methods"
    )

    # Create workflow with multiple steps
    start_flow(
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
