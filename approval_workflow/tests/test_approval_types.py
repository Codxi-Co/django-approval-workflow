"""Comprehensive test suite for approval types functionality.

Tests all four approval types:
- APPROVE: Optional form validation
- SUBMIT: Required form and form_data
- CHECK_IN_VERIFY: Two-phase verification flow
- MOVE: Rejects any forms

Author: Mohamed Salah
"""

import pytest
from datetime import datetime, timezone as dt_timezone
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.choices import ApprovalStatus, ApprovalType
from approval_workflow.services import start_flow, advance_flow

User = get_user_model()


@pytest.mark.django_db
class TestApproveType:
    """Test cases for APPROVE approval type."""

    def test_approve_type_default(self):
        """Test that APPROVE is the default approval type."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(obj=request, steps=[{"step": 1, "assigned_to": user1}])

        instance = flow.instances.first()
        assert instance.approval_type == ApprovalType.APPROVE

    def test_approve_type_without_form(self):
        """Test APPROVE type works without form."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.APPROVE}
            ],
        )

        # Should work without form_data
        result = advance_flow(request, "approved", user1, comment="Approved")
        assert result is None  # Workflow complete

    def test_approve_type_with_optional_form(self):
        """Test APPROVE type with optional form validation."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        user2 = User.objects.create_user(username="user2", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(
            name="Test Form",
            schema={"type": "object", "properties": {"comment": {"type": "string"}}},
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.APPROVE,
                    "form": form,
                },
                {"step": 2, "assigned_to": user2},
            ],
        )

        # Should work without form_data (form is optional for APPROVE)
        result = advance_flow(request, "approved", user1)
        assert result is not None
        assert result.step_number == 2

        # Should also work with form_data
        result = advance_flow(request, "approved", user2, form_data={"comment": "Good"})
        assert result is None  # Workflow complete


@pytest.mark.django_db
class TestSubmitType:
    """Test cases for SUBMIT approval type."""

    def test_submit_type_requires_form(self):
        """Test SUBMIT type requires form to be attached."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        # Create step without form - should fail when approving
        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.SUBMIT}
            ],
        )

        with pytest.raises(ValueError, match="requires a form to be attached"):
            advance_flow(request, "approved", user1)

    def test_submit_type_requires_form_data(self):
        """Test SUBMIT type requires form_data to be provided."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(
            name="Submission Form",
            schema={"type": "object", "properties": {"reason": {"type": "string"}}},
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.SUBMIT,
                    "form": form,
                }
            ],
        )

        # Should fail without form_data
        with pytest.raises(ValueError, match="requires form_data"):
            advance_flow(request, "approved", user1)

    def test_submit_type_success_with_form_data(self):
        """Test SUBMIT type succeeds with form and form_data."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(
            name="Submission Form",
            schema={"type": "object", "properties": {"reason": {"type": "string"}}},
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.SUBMIT,
                    "form": form,
                }
            ],
        )

        # Should succeed with form_data
        result = advance_flow(
            request, "approved", user1, form_data={"reason": "Initial submission"}
        )
        assert result is None  # Workflow complete

        # Verify form_data was saved
        instance = flow.instances.get(step_number=1)
        assert instance.form_data == {"reason": "Initial submission"}


@pytest.mark.django_db
class TestMoveType:
    """Test cases for MOVE approval type."""

    def test_move_type_rejects_form(self):
        """Test MOVE type rejects any attached form."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(name="Test Form", schema={"type": "object"})

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.MOVE,
                    "form": form,
                }
            ],
        )

        with pytest.raises(ValueError, match="MOVE type does not accept forms"):
            advance_flow(request, "approved", user1)

    def test_move_type_rejects_form_data(self):
        """Test MOVE type rejects any form_data."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.MOVE}
            ],
        )

        with pytest.raises(ValueError, match="MOVE type does not accept forms"):
            advance_flow(request, "approved", user1, form_data={"data": "value"})

    def test_move_type_success_without_form(self):
        """Test MOVE type succeeds without form or form_data."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        user2 = User.objects.create_user(username="user2", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.MOVE},
                {"step": 2, "assigned_to": user2, "approval_type": ApprovalType.MOVE},
            ],
        )

        # Should succeed without any form
        result = advance_flow(
            request, "approved", user1, comment="Routing to department"
        )
        assert result is not None
        assert result.step_number == 2

        result = advance_flow(request, "approved", user2)
        assert result is None  # Workflow complete


@pytest.mark.django_db
class TestCheckInVerifyType:
    """Test cases for CHECK_IN_VERIFY approval type."""

    def test_check_in_verify_two_phase_flow(self):
        """Test CHECK_IN_VERIFY two-phase flow: check-in then approve."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.CHECK_IN_VERIFY,
                }
            ],
        )

        instance = flow.instances.get(step_number=1)
        assert (
            instance.extra_fields is None
            or instance.extra_fields.get("checked_in") is None
        )

        # Phase 1: Check-in
        result = advance_flow(request, "approved", user1, comment="Checking in")
        assert result is not None  # Should return same instance
        assert result.id == instance.id  # Same instance
        assert result.status == ApprovalStatus.CURRENT  # Still current

        # Verify check-in metadata
        instance.refresh_from_db()
        assert instance.extra_fields["checked_in"] is True
        assert instance.extra_fields["checked_in_by"] == "user1"
        assert "checked_in_at" in instance.extra_fields

        # Phase 2: Approval
        result = advance_flow(
            request, "approved", user1, comment="Verified and approved"
        )
        assert result is None  # Workflow complete

        instance.refresh_from_db()
        assert instance.status == ApprovalStatus.APPROVED

    def test_check_in_verify_with_custom_timestamp(self):
        """Test CHECK_IN_VERIFY with custom timestamp from integrated system."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.CHECK_IN_VERIFY,
                }
            ],
        )

        # Custom timestamp from different timezone
        custom_timestamp = "2025-10-04T15:30:00+05:00"

        # Phase 1: Check-in with custom timestamp
        result = advance_flow(request, "approved", user1, timestamp=custom_timestamp)

        instance = flow.instances.get(step_number=1)
        assert instance.extra_fields["checked_in_at"] == custom_timestamp

    def test_check_in_verify_with_optional_form(self):
        """Test CHECK_IN_VERIFY with optional form validation."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(
            name="Verification Form",
            schema={"type": "object", "properties": {"notes": {"type": "string"}}},
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.CHECK_IN_VERIFY,
                    "form": form,
                }
            ],
        )

        # Phase 1: Check-in
        result = advance_flow(request, "approved", user1)
        assert result.status == ApprovalStatus.CURRENT

        # Phase 2: Approval with optional form_data
        result = advance_flow(
            request, "approved", user1, form_data={"notes": "All verified"}
        )
        assert result is None  # Workflow complete


@pytest.mark.django_db
class TestApprovalTypesIntegration:
    """Integration tests for approval types with other features."""

    def test_mixed_approval_types_workflow(self):
        """Test workflow with different approval types."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        user2 = User.objects.create_user(username="user2", password="password")
        user3 = User.objects.create_user(username="user3", password="password")
        user4 = User.objects.create_user(username="user4", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(
            name="Submission Form",
            schema={"type": "object", "properties": {"data": {"type": "string"}}},
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.SUBMIT,
                    "form": form,
                },
                {
                    "step": 2,
                    "assigned_to": user2,
                    "approval_type": ApprovalType.CHECK_IN_VERIFY,
                },
                {
                    "step": 3,
                    "assigned_to": user3,
                    "approval_type": ApprovalType.APPROVE,
                },
                {"step": 4, "assigned_to": user4, "approval_type": ApprovalType.MOVE},
            ],
        )

        # Step 1: SUBMIT - requires form_data
        result = advance_flow(
            request, "approved", user1, form_data={"data": "submission"}
        )
        assert result.step_number == 2

        # Step 2: CHECK_IN_VERIFY - two-phase
        result = advance_flow(request, "approved", user2)  # Check-in
        assert result.step_number == 2
        result = advance_flow(request, "approved", user2)  # Approve
        assert result.step_number == 3

        # Step 3: APPROVE - optional form
        result = advance_flow(request, "approved", user3)
        assert result.step_number == 4

        # Step 4: MOVE - no form allowed
        result = advance_flow(request, "approved", user4)
        assert result is None  # Complete

    def test_approval_type_preserved_in_delegation(self):
        """Test that approval_type is preserved when delegating."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        user2 = User.objects.create_user(username="user2", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.CHECK_IN_VERIFY,
                }
            ],
        )

        # Delegate
        result = advance_flow(
            request,
            "delegated",
            user1,
            delegate_to=user2,
            comment="Delegating to specialist",
        )

        # Check delegated instance preserves approval_type
        assert result.approval_type == ApprovalType.CHECK_IN_VERIFY
        assert result.assigned_to == user2

    def test_approval_type_preserved_in_escalation(self):
        """Test that approval_type is preserved when escalating."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        manager = User.objects.create_user(username="manager", password="password")
        user1.head_manager = manager
        user1.save()

        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(name="Test Form", schema={"type": "object"})

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.SUBMIT,
                    "form": form,
                }
            ],
        )

        # Escalate
        result = advance_flow(
            request, "escalated", user1, comment="Escalating to manager"
        )

        # Check escalated instance preserves approval_type
        assert result.approval_type == ApprovalType.SUBMIT
        assert result.assigned_to == manager

    def test_approval_type_validation_after_delegation(self):
        """Test that validation rules still apply after delegation."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        user2 = User.objects.create_user(username="user2", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.MOVE}
            ],
        )

        # Delegate
        result = advance_flow(request, "delegated", user1, delegate_to=user2)

        # Delegated instance should still reject form_data
        with pytest.raises(ValueError, match="MOVE type does not accept forms"):
            advance_flow(request, "approved", user2, form_data={"data": "value"})


@pytest.mark.django_db
class TestApprovalTypeErrorHandling:
    """Test error handling for approval types."""

    def test_submit_without_form_clear_error(self):
        """Test clear error message when SUBMIT type missing form."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        flow = start_flow(
            obj=request,
            steps=[
                {"step": 1, "assigned_to": user1, "approval_type": ApprovalType.SUBMIT}
            ],
        )

        with pytest.raises(ValueError) as exc_info:
            advance_flow(request, "approved", user1)

        assert "SUBMIT type" in str(exc_info.value)
        assert "form" in str(exc_info.value).lower()

    def test_move_with_form_clear_error(self):
        """Test clear error message when MOVE type has form."""
        MockRequestModel = apps.get_model("testapp", "MockRequestModel")
        DynamicForm = apps.get_model("testapp", "DynamicForm")
        user1 = User.objects.create_user(username="user1", password="password")
        request = MockRequestModel.objects.create(
            title="Test Request", description="Test"
        )

        form = DynamicForm.objects.create(name="Test Form", schema={})

        flow = start_flow(
            obj=request,
            steps=[
                {
                    "step": 1,
                    "assigned_to": user1,
                    "approval_type": ApprovalType.MOVE,
                    "form": form,
                }
            ],
        )

        with pytest.raises(ValueError) as exc_info:
            advance_flow(request, "approved", user1)

        assert "MOVE type" in str(exc_info.value)
        assert "does not accept" in str(exc_info.value)
