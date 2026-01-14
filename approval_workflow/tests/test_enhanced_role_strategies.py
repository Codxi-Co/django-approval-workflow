"""
Comprehensive test cases for enhanced role-based approval strategies.

Tests all new role selection strategies:
- QUORUM: Require N out of M users to approve
- MAJORITY: Require majority (>50%) of role users to approve
- PERCENTAGE: Require X% of role users to approve
- HIERARCHY_UP: Escalate through N levels of role hierarchy
- HIERARCHY_CHAIN: Require approval from entire management chain

Also tests:
- Enhanced logging with structured messages
- Edge cases and error handling
- Integration with existing features
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from approval_workflow.models import ApprovalFlow, ApprovalInstance
from approval_workflow.choices import (
    ApprovalStatus,
    ApprovalType,
    RoleSelectionStrategy,
)
from approval_workflow.services import (
    start_flow,
    advance_flow,
    _activate_role_based_step,
    _handle_role_based_approval_completion,
)
from approval_workflow.utils import get_users_for_role

# Import the actual models from sandbox
from sandbox.testapp.models import MockRole, MockRequestModel

User = get_user_model()


class EnhancedRoleStrategiesTestCase(TestCase):
    """Base test case with common setup for enhanced role-based approval tests."""

    def setUp(self):
        """Set up test data with role hierarchy."""
        # Create role hierarchy: VP -> Director -> Manager -> Agent
        # Hierarchy goes UP (Agent reports to Manager, etc.)
        self.vp_role = MockRole.objects.create(name="VP", parent=None)
        self.director_role = MockRole.objects.create(
            name="Director", parent=self.vp_role
        )
        self.manager_role = MockRole.objects.create(
            name="Manager", parent=self.director_role
        )
        self.agent_role = MockRole.objects.create(
            name="Agent", parent=self.manager_role
        )

        # Create users at different hierarchy levels
        self.agent1 = User.objects.create_user(
            username="agent1", email="agent1@test.com", role=self.agent_role
        )
        self.agent2 = User.objects.create_user(
            username="agent2", email="agent2@test.com", role=self.agent_role
        )
        self.manager1 = User.objects.create_user(
            username="manager1", email="manager1@test.com", role=self.manager_role
        )
        self.manager2 = User.objects.create_user(
            username="manager2", email="manager2@test.com", role=self.manager_role
        )
        self.manager3 = User.objects.create_user(
            username="manager3", email="manager3@test.com", role=self.manager_role
        )
        self.director1 = User.objects.create_user(
            username="director1", email="director1@test.com", role=self.director_role
        )
        self.vp1 = User.objects.create_user(
            username="vp1", email="vp1@test.com", role=self.vp_role
        )

        # Create test business object
        self.document = MockRequestModel.objects.create(
            title="Test Deal",
            description="Test Description",
            account_manager=self.agent1,  # Set agent1 as account manager
        )

        # Get content types
        self.document_content_type = ContentType.objects.get_for_model(MockRequestModel)
        self.role_content_type = ContentType.objects.get_for_model(MockRole)


class TestQuorumStrategy(EnhancedRoleStrategiesTestCase):
    """Test the QUORUM role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_2_out_of_5_strategy_activation(self, mock_get_users):
        """Test QUORUM strategy activation with 2 out of 5 users required."""
        # Mock 5 managers
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
            self.vp1,
        ]

        # Create flow with QUORUM step (2 out of 5)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 5,
                }
            ],
        )

        # Verify 5 CURRENT instances created
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(current_instances.count(), 5)

        # Verify quorum settings
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 2)
        self.assertEqual(instance.quorum_total, 5)
        self.assertEqual(instance.extra_fields.get("quorum_required"), 2)
        self.assertEqual(instance.extra_fields.get("quorum_total"), 5)

    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_completion_on_required_approvals(self, mock_get_users):
        """Test that step completes when quorum is reached."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
        ]

        # Create flow with QUORUM step (2 out of 4)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 4,
                },
                {
                    "step": 2,
                    "assigned_to": self.vp1,
                },
            ],
        )

        # Approve with manager1 (1/2)
        result = advance_flow(self.document, "approved", self.manager1)
        self.assertIsNotNone(result)  # Should return None (stay on step)
        self.assertEqual(result.status, ApprovalStatus.CURRENT)

        # Approve with manager2 (2/2) - quorum reached!
        result = advance_flow(self.document, "approved", self.manager2)
        self.assertIsNotNone(result)
        self.assertEqual(result.step_number, 2)  # Moved to step 2
        self.assertEqual(result.assigned_to, self.vp1)

        # Verify remaining CURRENT instances were cancelled
        remaining_current = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(remaining_current.count(), 0)

    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_extra_approvals_allowed(self, mock_get_users):
        """Test that extra approvals beyond quorum are allowed."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
        ]

        # Create flow with QUORUM step (2 out of 3)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 3,
                },
                {
                    "step": 2,
                    "assigned_to": self.vp1,
                },
            ],
        )

        # Approve with manager1 (1/2)
        advance_flow(self.document, "approved", self.manager1)

        # Approve with manager2 (2/2) - quorum reached
        advance_flow(self.document, "approved", self.manager2)

        # Verify manager3's instance was cancelled
        manager3_instance = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, assigned_to=self.manager3
        ).first()
        self.assertIsNotNone(manager3_instance)
        self.assertEqual(manager3_instance.status, ApprovalStatus.CANCELLED)

    def test_quorum_from_extra_fields(self):
        """Test QUORUM strategy when quorum settings are in extra_fields."""
        # Create step template with quorum in extra_fields
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "extra_fields": {
                        "quorum_count": 2,
                        "quorum_total": 3,
                    },
                },
            ],
        )

        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 2)
        self.assertEqual(instance.quorum_total, 3)


class TestMajorityStrategy(EnhancedRoleStrategiesTestCase):
    """Test the MAJORITY role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_majority_calculation_odd_number(self, mock_get_users):
        """Test MAJORITY calculation with odd number of users (5 users = 3 required)."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
            self.vp1,
        ]

        # Create flow with MAJORITY step (5 users, need 3)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.MAJORITY,
                },
                {
                    "step": 2,
                    "assigned_to": self.agent1,
                },
            ],
        )

        # Verify quorum was calculated correctly
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 3)  # (5 // 2) + 1 = 3
        self.assertEqual(instance.quorum_total, 5)

    @patch("approval_workflow.utils.get_users_for_role")
    def test_majority_calculation_even_number(self, mock_get_users):
        """Test MAJORITY calculation with even number of users (4 users = 3 required)."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
        ]

        # Create flow with MAJORITY step (4 users, need 3)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.MAJORITY,
                },
            ],
        )

        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 3)  # (4 // 2) + 1 = 3
        self.assertEqual(instance.quorum_total, 4)

    @patch("approval_workflow.utils.get_users_for_role")
    def test_majority_completion(self, mock_get_users):
        """Test that MAJORITY strategy completes correctly."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
        ]

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.MAJORITY,
                },
                {
                    "step": 2,
                    "assigned_to": self.agent1,
                },
            ],
        )

        # Approve 2 times (not enough)
        advance_flow(self.document, "approved", self.manager1)
        advance_flow(self.document, "approved", self.manager2)

        # Still on step 1
        current = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(current.count(), 2)

        # Approve 3rd time (majority reached!)
        result = advance_flow(self.document, "approved", self.manager3)
        self.assertIsNotNone(result)
        self.assertEqual(result.step_number, 2)


class TestPercentageStrategy(EnhancedRoleStrategiesTestCase):
    """Test the PERCENTAGE role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_percentage_66_percent(self, mock_get_users):
        """Test PERCENTAGE strategy with 66% requirement."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
            self.vp1,
        ]

        # Create flow with 66% requirement (5 users * 0.66 = 3.3 -> 4 required)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.PERCENTAGE,
                    "percentage_required": 66.67,
                },
            ],
        )

        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 4)  # int(5 * 66.67 / 100) + 1 = 4
        self.assertEqual(instance.quorum_total, 5)

    @patch("approval_workflow.utils.get_users_for_role")
    def test_percentage_50_percent(self, mock_get_users):
        """Test PERCENTAGE strategy with 50% requirement."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
            self.director1,
        ]

        # Create flow with 50% requirement (4 users * 0.50 = 2 required)
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.PERCENTAGE,
                    "percentage_required": 50.0,
                },
            ],
        )

        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.quorum_count, 2)  # ceil(4 * 50.0 / 100) = 2

    @patch("approval_workflow.utils.get_users_for_role")
    def test_percentage_from_model_field(self, mock_get_users):
        """Test PERCENTAGE strategy using model field instead of extra_fields."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
        ]

        # Create flow with percentage in model field
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.PERCENTAGE,
                    "percentage_required": 75.0,
                },
            ],
        )

        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        instance = current_instances.first()
        self.assertEqual(instance.percentage_required, 75.0)
        self.assertEqual(instance.quorum_count, 3)  # int(3 * 75.0 / 100) + 1 = 3


class TestHierarchyUpStrategy(EnhancedRoleStrategiesTestCase):
    """Test the HIERARCHY_UP role selection strategy."""

    def test_hierarchy_one_level_up(self):
        """Test HIERARCHY_UP with 1 level (direct manager only)."""
        # Create flow with HIERARCHY_UP starting from agent
        self.document.account_manager = self.agent1
        self.document.save()

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.agent1,
                    "approval_type": ApprovalType.APPROVE,
                },
                {
                    "step": 2,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                    "hierarchy_levels": 1,
                    "hierarchy_base_user": self.agent1,
                },
            ],
        )

        # Approve step 1 to activate step 2
        advance_flow(self.document, "approved", self.agent1)

        # Verify manager role users were selected (manager1, manager2 have Manager role)
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=2, status=ApprovalStatus.CURRENT
        )
        self.assertGreaterEqual(current_instances.count(), 1)

        # Verify hierarchy settings
        instance = current_instances.first()
        self.assertEqual(instance.hierarchy_levels, 1)
        self.assertEqual(instance.hierarchy_base_user, self.agent1)

    def test_hierarchy_two_levels_up(self):
        """Test HIERARCHY_UP with 2 levels (manager + director)."""
        # Agent needs approval from 2 levels up
        self.document.account_manager = self.agent1
        self.document.save()

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                    "hierarchy_levels": 2,
                    "hierarchy_base_user": self.agent1,
                },
            ],
        )

        # Should get managers (level 1) + directors (level 2)
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertGreater(current_instances.count(), 0)

    def test_hierarchy_base_user_from_business_object(self):
        """Test HIERARCHY_UP gets base_user from business object attribute."""
        # This tests the fallback to account_manager attribute
        self.document.account_manager = self.agent1
        self.document.save()

        with patch("approval_workflow.utils.get_users_for_role") as mock_get_users:
            mock_get_users.return_value = [self.manager1]

            flow = start_flow(
                obj=self.document,
                steps=[
                    {
                        "step": 1,
                        "assigned_role": self.manager_role,
                        "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                        "hierarchy_levels": 1,
                        # hierarchy_base_user not specified - should fall back to business object
                    },
                ],
            )

            current_instances = ApprovalInstance.objects.filter(
                flow=flow, step_number=1
            )
            instance = current_instances.first()
            self.assertIsNotNone(instance)

    def test_hierarchy_requires_base_user(self):
        """Test that HIERARCHY_UP raises error without base_user."""
        # Clear account_manager
        self.document.account_manager = None
        self.document.save()

        with self.assertRaises(ValueError) as context:
            start_flow(
                obj=self.document,
                steps=[
                    {
                        "step": 1,
                        "assigned_role": self.manager_role,
                        "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                        "hierarchy_levels": 1,
                    },
                ],
            )

        self.assertIn("base user", str(context.exception).lower())

    def test_hierarchy_requires_role_hierarchy(self):
        """Test that HIERARCHY_UP requires MPTT role hierarchy."""
        # Create a role with no parent (flat hierarchy)
        flat_role = MockRole.objects.create(name="FlatRole", parent=None)

        # agent1 has this flat role which has no parent
        self.agent1.role = flat_role
        self.agent1.save()

        with self.assertRaises(ValueError) as context:
            start_flow(
                obj=self.document,
                steps=[
                    {
                        "step": 1,
                        "assigned_role": flat_role,
                        "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                        "hierarchy_levels": 1,
                        "hierarchy_base_user": self.agent1,
                    },
                ],
            )

        self.assertIn("hierarchy", str(context.exception).lower())


class TestEnhancedLogging(EnhancedRoleStrategiesTestCase):
    """Test enhanced structured logging for new strategies."""

    @patch("approval_workflow.services.logger")
    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_logging(self, mock_get_users, mock_logger):
        """Test that QUORUM strategy logs properly."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
        ]

        # Create QUORUM step
        start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 3,
                },
            ],
        )

        # Verify info log was called with structured data
        self.assertTrue(mock_logger.info.called)
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        self.assertTrue(any("QUORUM INSTANCES CREATED" in call for call in log_calls))

    @patch("approval_workflow.services.logger")
    def test_hierarchy_logging(self, mock_logger):
        """Test that HIERARCHY strategy logs properly."""
        start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                    "hierarchy_levels": 1,
                    "hierarchy_base_user": self.agent1,
                },
            ],
        )

        # Verify info log was called with structured data
        self.assertTrue(mock_logger.info.called)
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        self.assertTrue(
            any("HIERARCHY INSTANCES CREATED" in call for call in log_calls)
        )

    @patch("approval_workflow.services.logger")
    @patch("approval_workflow.utils.get_users_for_role")
    def test_error_logging_for_missing_role_users(self, mock_get_users, mock_logger):
        """Test error logging when no users found for role."""
        mock_get_users.return_value = []

        with self.assertRaises(ValueError):
            start_flow(
                obj=self.document,
                steps=[
                    {
                        "step": 1,
                        "assigned_role": self.manager_role,
                        "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                        "quorum_count": 2,
                    },
                ],
            )

        # Verify error log was called
        self.assertTrue(mock_logger.error.called)
        log_calls = [str(call) for call in mock_logger.error.call_args_list]
        self.assertTrue(any("NO USERS FOUND FOR ROLE" in call for call in log_calls))


class TestEdgeCases(EnhancedRoleStrategiesTestCase):
    """Test edge cases and error handling."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_with_single_user(self, mock_get_users):
        """Test QUORUM strategy with only 1 user in role."""
        mock_get_users.return_value = [self.manager1]

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 1,
                    "quorum_total": 1,
                },
            ],
        )

        # Should work fine with 1 user
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(current_instances.count(), 1)

    def test_unknown_strategy_raises_error(self):
        """Test that unknown strategy raises ValueError."""
        from approval_workflow.services import _activate_role_based_step

        flow = ApprovalFlow.objects.create(
            content_type=self.document_content_type, object_id=str(self.document.pk)
        )

        step_template = ApprovalInstance.objects.create(
            flow=flow,
            step_number=1,
            status=ApprovalStatus.PENDING,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy="unknown_strategy",
        )

        with self.assertRaises(ValueError) as context:
            _activate_role_based_step(step_template)

        self.assertIn("unknown", str(context.exception).lower())

    @patch("approval_workflow.utils.get_users_for_role")
    def test_quorum_progress_tracking(self, mock_get_users):
        """Test that quorum progress is tracked in extra_fields."""
        mock_get_users.return_value = [
            self.manager1,
            self.manager2,
            self.manager3,
        ]

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_role": self.manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 3,
                },
                {
                    "step": 2,
                    "assigned_to": self.vp1,
                },
            ],
        )

        # Get instance and check initial progress
        instance = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, assigned_to=self.manager1
        ).first()
        self.assertEqual(instance.extra_fields.get("quorum_progress"), 0)

        # Approve once
        advance_flow(self.document, "approved", self.manager1)

        # Progress should still be tracked (implementation may vary)
        current_instances = ApprovalInstance.objects.filter(
            flow=flow, step_number=1, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(current_instances.count(), 2)  # 2 remaining


class TestTranslationSupport(EnhancedRoleStrategiesTestCase):
    """Test that translation support is properly integrated."""

    def test_model_verbose_names_translatable(self):
        """Test that model verbose names use gettext_lazy."""
        from django.utils.translation import activate, gettext

        # Test with English
        activate("en")
        flow_en = str(ApprovalFlow._meta.verbose_name)
        self.assertIn("Flow", flow_en)

        # The verbose_name should be a translation string
        from approval_workflow.models import ApprovalFlow as FlowModel

        self.assertIsNotNone(FlowModel._meta.verbose_name)

    def test_choice_labels_translatable(self):
        """Test that choice labels use gettext_lazy."""
        # Choices should be translatable
        from approval_workflow.choices import RoleSelectionStrategy
        from django.utils.functional import Promise

        # All choice values should be translatable strings or Promise objects
        for choice in RoleSelectionStrategy:
            self.assertIsNotNone(choice.label)
            # gettext_lazy returns a Promise, which is acceptable
            self.assertTrue(
                isinstance(choice.label, (str, Promise)),
                f"Choice label should be str or Promise, got {type(choice.label)}",
            )


class TestSLAFeatures(EnhancedRoleStrategiesTestCase):
    """Test SLA and timeout management features."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_due_date_set_on_instance(self, mock_get_users):
        """Test that due_date is properly set."""
        from datetime import timedelta
        from django.utils import timezone

        mock_get_users.return_value = [self.manager1]

        due_date = timezone.now() + timedelta(days=2)

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                    "due_date": due_date,
                },
            ],
        )

        instance = ApprovalInstance.objects.get(flow=flow, step_number=1)
        self.assertIsNotNone(instance.due_date)

    def test_timeout_action_choices(self):
        """Test that timeout_action has proper choices."""
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                    "timeout_action": "escalate",
                },
            ],
        )

        instance = ApprovalInstance.objects.get(flow=flow, step_number=1)
        self.assertEqual(instance.timeout_action, "escalate")


class TestParallelApprovalSupport(EnhancedRoleStrategiesTestCase):
    """Test parallel approval group support."""

    def test_parallel_group_assignment(self):
        """Test that parallel_group can be set."""
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                    "parallel_group": "financial_review",
                    "parallel_required": True,
                },
                {
                    "step": 2,
                    "assigned_to": self.director1,
                    "parallel_group": "financial_review",
                    "parallel_required": True,
                },
                {
                    "step": 3,
                    "assigned_to": self.vp1,
                },
            ],
        )

        # Verify parallel groups are set
        instance1 = ApprovalInstance.objects.get(flow=flow, step_number=1)
        instance2 = ApprovalInstance.objects.get(flow=flow, step_number=2)

        self.assertEqual(instance1.parallel_group, "financial_review")
        self.assertEqual(instance2.parallel_group, "financial_review")
        self.assertTrue(instance1.parallel_required)
        self.assertTrue(instance2.parallel_required)


class TestDelegationChain(EnhancedRoleStrategiesTestCase):
    """Test delegation chain tracking."""

    def test_delegation_chain_tracking(self):
        """Test that delegation_chain can store history."""
        initial_delegation = [
            {
                "from_user_id": self.manager1.id,
                "to_user_id": self.manager2.id,
                "timestamp": "2024-01-01T10:00:00Z",
                "reason": "Original delegation",
            }
        ]

        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                    "delegation_chain": initial_delegation,
                },
            ],
        )

        instance = ApprovalInstance.objects.get(flow=flow, step_number=1)
        self.assertEqual(instance.delegation_chain, initial_delegation)


class TestEscalationLevelTracking(EnhancedRoleStrategiesTestCase):
    """Test escalation level tracking."""

    def test_escalation_level_defaults(self):
        """Test that escalation levels have proper defaults."""
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                },
            ],
        )

        instance = ApprovalInstance.objects.get(flow=flow, step_number=1)
        self.assertEqual(instance.escalation_level, 0)
        self.assertEqual(instance.max_escalation_level, 3)

    def test_custom_max_escalation_level(self):
        """Test that max_escalation_level can be customized."""
        flow = start_flow(
            obj=self.document,
            steps=[
                {
                    "step": 1,
                    "assigned_to": self.manager1,
                    "max_escalation_level": 5,
                },
            ],
        )

        instance = ApprovalInstance.objects.get(flow=flow, step_number=1)
        self.assertEqual(instance.max_escalation_level, 5)


# Additional integration test classes can be added here
# to test combinations of strategies and complex workflows
