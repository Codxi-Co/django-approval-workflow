"""Shared test fixtures for approval workflow tests."""

import pytest
from django.test import override_settings
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.utils import ApprovalRepository

User = get_user_model()


@pytest.fixture(autouse=True)
def configure_approval_settings():
    """Auto-configure approval workflow settings for all tests."""
    with override_settings(
        APPROVAL_ROLE_MODEL="testapp.MockRole",
        APPROVAL_ROLE_FIELD="role",
        APPROVAL_DYNAMIC_FORM_MODEL="testapp.DynamicForm",
        APPROVAL_FORM_SCHEMA_FIELD="schema",
        APPROVAL_HEAD_MANAGER_FIELD="head_manager",
    ):
        yield


@pytest.fixture
@override_settings(APPROVAL_ROLE_MODEL="testapp.MockRole", APPROVAL_ROLE_FIELD="role")
def setup_roles_and_users(django_user_model):
    """Create roles and users for testing."""
    # Clear cache before each test to ensure clean state
    ApprovalRepository.clear_all_cache()

    Role = apps.get_model("testapp", "MockRole")
    senior = Role.objects.create(name="Senior")
    junior = Role.objects.create(name="Junior", parent=senior)

    manager = django_user_model.objects.create(username="manager", role=senior)
    employee = django_user_model.objects.create(username="employee", role=junior)

    return manager, employee


@pytest.fixture
def mock_request_model():
    """Get the MockRequestModel for testing."""
    return apps.get_model("testapp", "MockRequestModel")
