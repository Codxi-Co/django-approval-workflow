"""Tests for custom approval handlers and hook integration."""

import pytest
from unittest.mock import MagicMock
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.utils import get_current_approval

User = get_user_model()


@pytest.mark.django_db
def test_on_resubmission_handler_called(setup_roles_and_users, monkeypatch):
    """Test that on_resubmission handler is properly called."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Handler Test", description="Testing handler calls"
    )

    flow = start_flow(
        dummy,
        [{"step": 1, "assigned_to": employee}, {"step": 2, "assigned_to": manager}],
    )

    # Mock the handler
    mock_handler = MagicMock()

    def mock_get_handler(instance):
        return mock_handler

    monkeypatch.setattr(
        "approval_workflow.services.get_handler_for_instance", mock_get_handler
    )

    # Trigger resubmission with explicit step number to avoid conflicts
    current_step = get_current_approval(dummy)
    advance_flow(
        current_step,
        action="resubmission",
        user=employee,
        comment="Need additional review",
        resubmission_steps=[
            {"step": 3, "assigned_to": specialist}
        ],  # Step 3 to avoid conflict with existing steps 1,2
    )

    # Verify handler was called
    mock_handler.on_resubmission.assert_called_once_with(current_step)


@pytest.mark.django_db
def test_custom_resubmission_handler(setup_roles_and_users, monkeypatch):
    """Test custom resubmission handler implementation."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Custom Handler Test", description="Testing custom handler"
    )

    # Create a custom handler that tracks calls
    class TestHandler:
        def __init__(self):
            self.resubmission_called = False
            self.resubmission_instance = None

        def on_approve(self, instance):
            pass

        def on_final_approve(self, instance):
            pass

        def on_reject(self, instance):
            pass

        def on_resubmission(self, instance):
            self.resubmission_called = True
            self.resubmission_instance = instance

        def on_delegate(self, instance):
            pass

        def on_escalate(self, instance):
            pass

    test_handler = TestHandler()

    def mock_get_handler(instance):
        return test_handler

    monkeypatch.setattr(
        "approval_workflow.services.get_handler_for_instance", mock_get_handler
    )

    # Create flow and trigger resubmission
    flow = start_flow(
        dummy,
        [{"step": 1, "assigned_to": employee}, {"step": 2, "assigned_to": manager}],
    )

    current_step = get_current_approval(dummy)
    advance_flow(
        current_step,
        action="resubmission",
        user=employee,
        comment="Custom resubmission test",
        resubmission_steps=[
            {"step": 3, "assigned_to": specialist}
        ],  # Step 3 to avoid conflict with existing steps 1,2
    )

    # Verify custom handler was called
    assert test_handler.resubmission_called
    assert test_handler.resubmission_instance == current_step
