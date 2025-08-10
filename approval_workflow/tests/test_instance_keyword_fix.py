"""
Test the fix for instance= keyword parameter to support business objects.
"""

import pytest
from django.contrib.auth import get_user_model
from django.apps import apps

from approval_workflow.services import start_flow, advance_flow
from approval_workflow.models import ApprovalInstance

User = get_user_model()


@pytest.mark.django_db
def test_instance_keyword_with_business_object():
    """Test that advance_flow(instance=business_object, ...) works correctly."""
    # Setup
    user = User.objects.create_user(username="test_user", email="test@example.com")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    document = MockRequestModel.objects.create(
        title="Test Document", description="Test content"
    )

    # Start workflow
    start_flow(document, [{"step": 1, "assigned_to": user}])

    # Test the user's exact pattern - this should work now
    result = advance_flow(
        instance=document,  # Business object passed to instance= keyword
        action="approved",
        user=user,
        comment="Test approval",
        form_data={},
        delegate_to=None,
        resubmission_steps=None,
    )

    # Should complete successfully (return None for final step)
    assert result is None


@pytest.mark.django_db
def test_instance_keyword_with_approval_instance():
    """Test that advance_flow(instance=approval_instance, ...) still works (backward compatibility)."""
    # Setup
    user1 = User.objects.create_user(username="test_user1", email="test1@example.com")
    user2 = User.objects.create_user(username="test_user2", email="test2@example.com")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    document = MockRequestModel.objects.create(
        title="Test Document", description="Test content"
    )

    # Start workflow with 2 steps
    start_flow(
        document,
        [
            {"step": 1, "assigned_to": user1},
            {"step": 2, "assigned_to": user2},
        ],
    )

    # Get the approval instance
    approval_instance = ApprovalInstance.objects.filter(
        flow__object_id=str(document.pk), status="current"
    ).first()

    # Test old pattern with ApprovalInstance - should still work
    result = advance_flow(
        instance=approval_instance,  # ApprovalInstance passed to instance= keyword
        action="approved",
        user=user1,
        comment="Test approval",
    )

    # Should return next step
    assert result is not None
    assert isinstance(result, ApprovalInstance)
    assert result.assigned_to == user2


@pytest.mark.django_db
def test_instance_keyword_with_nonexistent_flow():
    """Test proper error handling when business object has no approval flow."""
    # Setup
    user = User.objects.create_user(username="test_user", email="test@example.com")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    document = MockRequestModel.objects.create(
        title="Test Document", description="Test content"
    )

    # Don't start a workflow - document has no approval flow

    # Test should raise ValueError
    with pytest.raises(ValueError, match="No current approval found"):
        advance_flow(
            instance=document,
            action="approved",
            user=user,
        )


@pytest.mark.django_db
def test_all_api_patterns_work():
    """Test that all API patterns work correctly."""
    # Setup
    user = User.objects.create_user(username="test_user", email="test@example.com")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")

    # Test Pattern 1: New API - advance_flow(object, action, user)
    doc1 = MockRequestModel.objects.create(title="Doc1", description="Test")
    start_flow(doc1, [{"step": 1, "assigned_to": user}])

    result1 = advance_flow(doc1, "approved", user)
    assert result1 is None  # Workflow complete

    # Test Pattern 2: New API with keyword - advance_flow(instance=object, ...)
    doc2 = MockRequestModel.objects.create(title="Doc2", description="Test")
    start_flow(doc2, [{"step": 1, "assigned_to": user}])

    result2 = advance_flow(instance=doc2, action="approved", user=user)
    assert result2 is None  # Workflow complete

    # Test Pattern 3: Old API - advance_flow(approval_instance, action, user)
    doc3 = MockRequestModel.objects.create(title="Doc3", description="Test")
    start_flow(doc3, [{"step": 1, "assigned_to": user}])
    approval_inst = ApprovalInstance.objects.filter(
        flow__object_id=str(doc3.pk), status="current"
    ).first()

    result3 = advance_flow(approval_inst, "approved", user)
    assert result3 is None  # Workflow complete

    # Test Pattern 4: Old API with keyword - advance_flow(instance=approval_instance, ...)
    doc4 = MockRequestModel.objects.create(title="Doc4", description="Test")
    start_flow(doc4, [{"step": 1, "assigned_to": user}])
    approval_inst4 = ApprovalInstance.objects.filter(
        flow__object_id=str(doc4.pk), status="current"
    ).first()

    result4 = advance_flow(instance=approval_inst4, action="approved", user=user)
    assert result4 is None  # Workflow complete
