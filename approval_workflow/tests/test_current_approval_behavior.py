"""Test to verify get_current_approval returns single object or QuerySet of objects as needed."""

import pytest
from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from approval_workflow.services import start_flow
from approval_workflow.utils import get_current_approval
from approval_workflow.choices import RoleSelectionStrategy
from sandbox.testapp.models import MockRequestModel as Document, MockRole as Role

User = get_user_model()


@pytest.mark.django_db
def test_single_current_approval():
    """Test that get_current_approval returns single object for regular approvals."""
    # Create test data
    user1 = User.objects.create_user(username="testuser1", email="test1@example.com")
    user2 = User.objects.create_user(username="testuser2", email="test2@example.com")

    document = Document.objects.create(title="Test Document")

    # Start a regular workflow with user-based steps
    flow = start_flow(
        obj=document,
        steps=[
            {"step": 1, "assigned_to": user1},
            {"step": 2, "assigned_to": user2},
        ],
    )

    # Get current approval - should return single object
    current = get_current_approval(document)

    # Assertions
    assert not isinstance(
        current, QuerySet
    ), "Single current approval should not be a QuerySet"
    assert current.assigned_to == user1, "Should be assigned to first user"
    assert current.step_number == 1, "Should be step 1"


@pytest.mark.django_db
def test_multiple_current_approvals_consensus():
    """Test that get_current_approval returns QuerySet for consensus approvals."""
    # Create test role and users
    manager_role = Role.objects.create(name="Manager")
    user1 = User.objects.create_user(
        username="manager1", email="manager1@example.com", role=manager_role
    )
    user2 = User.objects.create_user(
        username="manager2", email="manager2@example.com", role=manager_role
    )
    user3 = User.objects.create_user(
        username="manager3", email="manager3@example.com", role=manager_role
    )

    document = Document.objects.create(title="Test Document for Consensus")

    # Start workflow with consensus role-based step
    flow = start_flow(
        obj=document,
        steps=[
            {
                "step": 1,
                "assigned_role": manager_role,
                "role_selection_strategy": RoleSelectionStrategy.CONSENSUS,
            }
        ],
    )

    # Get current approval - should return QuerySet for consensus
    current = get_current_approval(document)

    # Assertions
    assert isinstance(current, QuerySet), "Consensus approval should return a QuerySet"
    assert len(current) == 3, "Should have 3 current approvals (one for each manager)"

    # Verify all users are represented
    assigned_users = {approval.assigned_to for approval in current}
    expected_users = {user1, user2, user3}
    assert (
        assigned_users == expected_users
    ), "All managers should have current approval steps"

    # Verify all have same step number
    step_numbers = {approval.step_number for approval in current}
    assert len(step_numbers) == 1, "All current approvals should have same step number"
    assert list(step_numbers)[0] == 1, "Should be step 1"


@pytest.mark.django_db
def test_usage_pattern_like_user_code():
    """Test the usage pattern shown in user's code."""
    # Create test role and users for consensus
    manager_role = Role.objects.create(name="TestManager")
    user1 = User.objects.create_user(
        username="mgr1", email="mgr1@example.com", role=manager_role
    )
    user2 = User.objects.create_user(
        username="mgr2", email="mgr2@example.com", role=manager_role
    )

    document = Document.objects.create(title="Pattern Test Document")

    # Start workflow with consensus
    flow = start_flow(
        obj=document,
        steps=[
            {
                "step": 1,
                "assigned_role": manager_role,
                "role_selection_strategy": RoleSelectionStrategy.CONSENSUS,
            }
        ],
    )

    # Use the pattern from user's main code
    approvals = get_current_approval(document)
    current_approval = (
        [approval.assigned_to for approval in approvals]
        if isinstance(approvals, QuerySet)
        else [approvals.assigned_to]
    )

    # Verify the pattern works
    if isinstance(approvals, QuerySet):
        # Should get user objects
        assert len(current_approval) == 2, "Should have 2 users"
        assert user1 in current_approval, "Should contain user1"
        assert user2 in current_approval, "Should contain user2"
    else:
        # Single approval case
        assert current_approval == [
            approvals.assigned_to
        ], "Should be wrapped in QuerySet"


@pytest.mark.django_db
def test_single_approval_pattern():
    """Test the user's pattern with single approval."""
    # Create single user workflow
    user1 = User.objects.create_user(username="singleuser", email="single@example.com")
    document = Document.objects.create(title="Single User Document")

    # Start simple workflow
    flow = start_flow(obj=document, steps=[{"step": 1, "assigned_to": user1}])

    # Use the pattern from user's main code
    approvals = get_current_approval(document)
    current_approval = (
        [approval.assigned_to for approval in approvals]
        if isinstance(approvals, QuerySet)
        else [approvals.assigned_to]
    )

    # Verify single approval case
    assert not isinstance(approvals, QuerySet), "Should be single approval instance"
    assert current_approval == [approvals.assigned_to], "Should be wrapped in QuerySet"
    assert current_approval[0] == user1, "Should be assigned to user1"


@pytest.mark.django_db
def test_no_current_approval():
    """Test behavior when no current approval exists."""
    document = Document.objects.create(title="No Workflow Document")

    # Get current approval - should return None
    current = get_current_approval(document)

    assert current is None, "Should return None when no workflow exists"
