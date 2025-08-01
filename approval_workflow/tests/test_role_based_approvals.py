"""
Test cases for role-based approval functionality.

Tests all three role selection strategies:
- ANYONE: Any user with the role can approve
- CONSENSUS: All users with the role must approve
- ROUND_ROBIN: Distributes approvals evenly among role users
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from approval_workflow.models import ApprovalFlow, ApprovalInstance
from approval_workflow.choices import ApprovalStatus, RoleSelectionStrategy
from approval_workflow.services import advance_flow, _activate_role_based_step
from approval_workflow.utils import get_users_for_role, get_user_with_least_assignments

# Import the actual models from sandbox
from sandbox.testapp.models import MockRole, MockRequestModel

User = get_user_model()


class RoleBasedApprovalTestCase(TestCase):
    """Base test case with common setup for role-based approval tests."""

    def setUp(self):
        """Set up test data."""
        # Create test roles
        self.manager_role = MockRole.objects.create(name="Manager")
        self.director_role = MockRole.objects.create(
            name="Director", parent=self.manager_role
        )

        # Create test users
        self.user1 = User.objects.create_user(
            username="manager1", email="manager1@test.com", role=self.manager_role
        )
        self.user2 = User.objects.create_user(
            username="manager2", email="manager2@test.com", role=self.manager_role
        )
        self.user3 = User.objects.create_user(
            username="manager3", email="manager3@test.com", role=self.manager_role
        )
        self.user4 = User.objects.create_user(
            username="director1", email="director1@test.com", role=self.director_role
        )

        # Create mock document
        self.document = MockRequestModel.objects.create(
            title="Test Document", description="Test Description"
        )

        # Create approval flow
        content_type = ContentType.objects.get_for_model(MockRequestModel)
        self.flow = ApprovalFlow.objects.create(
            content_type=content_type, object_id=str(self.document.pk)
        )

        # Get role content type for use in tests
        self.role_content_type = ContentType.objects.get_for_model(MockRole)


class TestAnyoneStrategy(RoleBasedApprovalTestCase):
    """Test the ANYONE role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_anyone_strategy_creates_multiple_current_instances(self, mock_get_users):
        """Test that ANYONE strategy creates multiple CURRENT instances."""
        mock_get_users.return_value = [self.user1, self.user2, self.user3]

        # Create a role-based step template
        step_template = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            status=ApprovalStatus.PENDING,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ANYONE,
        )

        # Activate the role-based step
        result = _activate_role_based_step(step_template)

        # Check that multiple CURRENT instances were created
        current_instances = ApprovalInstance.objects.filter(
            flow=self.flow, step_number=1, status=ApprovalStatus.CURRENT
        )

        self.assertEqual(current_instances.count(), 3)
        self.assertIn(self.user1, [inst.assigned_to for inst in current_instances])
        self.assertIn(self.user2, [inst.assigned_to for inst in current_instances])
        self.assertIn(self.user3, [inst.assigned_to for inst in current_instances])

        # Check that template was deleted
        self.assertFalse(ApprovalInstance.objects.filter(pk=step_template.pk).exists())

    def test_anyone_strategy_first_approval_completes_step(self):
        """Test that in ANYONE strategy, first approval completes the step."""
        # Create role-based instances (simulating _activate_role_based_step)
        inst1 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ANYONE,
            status=ApprovalStatus.CURRENT,
        )
        inst2 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user2,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ANYONE,
            status=ApprovalStatus.CURRENT,
        )
        inst3 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user3,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ANYONE,
            status=ApprovalStatus.CURRENT,
        )

        # First user approves
        advance_flow(inst1, "approved", self.user1, comment="Approved by user1")

        # Check that instance is approved
        inst1.refresh_from_db()
        self.assertEqual(inst1.status, ApprovalStatus.APPROVED)

        # Check that other instances were deleted
        self.assertFalse(ApprovalInstance.objects.filter(pk=inst2.pk).exists())
        self.assertFalse(ApprovalInstance.objects.filter(pk=inst3.pk).exists())


class TestConsensusStrategy(RoleBasedApprovalTestCase):
    """Test the CONSENSUS role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_consensus_strategy_creates_multiple_current_instances(
        self, mock_get_users
    ):
        """Test that CONSENSUS strategy creates multiple CURRENT instances."""
        mock_get_users.return_value = [self.user1, self.user2]

        # Create a role-based step template
        step_template = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            status=ApprovalStatus.PENDING,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.CONSENSUS,
        )

        # Activate the role-based step
        result = _activate_role_based_step(step_template)

        # Check that multiple CURRENT instances were created
        current_instances = ApprovalInstance.objects.filter(
            flow=self.flow, step_number=1, status=ApprovalStatus.CURRENT
        )

        self.assertEqual(current_instances.count(), 2)
        self.assertIn(self.user1, [inst.assigned_to for inst in current_instances])
        self.assertIn(self.user2, [inst.assigned_to for inst in current_instances])

    def test_consensus_strategy_requires_all_approvals(self):
        """Test that CONSENSUS strategy requires all users to approve."""
        # Create role-based instances (simulating _activate_role_based_step)
        inst1 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.CONSENSUS,
            status=ApprovalStatus.CURRENT,
        )
        inst2 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user2,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.CONSENSUS,
            status=ApprovalStatus.CURRENT,
        )

        # First user approves
        result = advance_flow(
            inst1, "approved", self.user1, comment="Approved by user1"
        )

        # Check that first instance is approved but step hasn't advanced (result is None)
        inst1.refresh_from_db()
        self.assertEqual(inst1.status, ApprovalStatus.APPROVED)
        self.assertIsNone(result)  # No next step yet

        # Check that second instance is still CURRENT
        inst2.refresh_from_db()
        self.assertEqual(inst2.status, ApprovalStatus.CURRENT)

        # Second user approves
        result = advance_flow(
            inst2, "approved", self.user2, comment="Approved by user2"
        )

        # Now both are approved and step should advance
        inst2.refresh_from_db()
        self.assertEqual(inst2.status, ApprovalStatus.APPROVED)
        # Since there's no next step, result should be None (workflow complete)
        self.assertIsNone(result)


class TestRoundRobinStrategy(RoleBasedApprovalTestCase):
    """Test the ROUND_ROBIN role selection strategy."""

    @patch("approval_workflow.utils.get_users_for_role")
    @patch("approval_workflow.utils.get_user_with_least_assignments")
    def test_round_robin_strategy_creates_single_instance(
        self, mock_least_assignments, mock_get_users
    ):
        """Test that ROUND_ROBIN strategy creates single CURRENT instance."""
        mock_get_users.return_value = [self.user1, self.user2, self.user3]
        mock_least_assignments.return_value = self.user2

        # Create a role-based step template
        step_template = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            status=ApprovalStatus.PENDING,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ROUND_ROBIN,
        )

        # Activate the role-based step
        result = _activate_role_based_step(step_template)

        # Check that only one CURRENT instance was created
        current_instances = ApprovalInstance.objects.filter(
            flow=self.flow, step_number=1, status=ApprovalStatus.CURRENT
        )

        self.assertEqual(current_instances.count(), 1)
        self.assertEqual(current_instances.first().assigned_to, self.user2)

        # Verify that get_user_with_least_assignments was called
        mock_least_assignments.assert_called_once_with(
            [self.user1, self.user2, self.user3]
        )

    def test_round_robin_strategy_single_approval_completes_step(self):
        """Test that in ROUND_ROBIN strategy, single approval completes the step."""
        # Create role-based instance (simulating _activate_role_based_step)
        inst1 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ROUND_ROBIN,
            status=ApprovalStatus.CURRENT,
        )

        # User approves
        result = advance_flow(
            inst1, "approved", self.user1, comment="Approved by user1"
        )

        # Check that instance is approved
        inst1.refresh_from_db()
        self.assertEqual(inst1.status, ApprovalStatus.APPROVED)

        # Since there's no next step, result should be None (workflow complete)
        self.assertIsNone(result)


class TestRoleUtilityFunctions(RoleBasedApprovalTestCase):
    """Test utility functions for role-based approvals."""

    @patch("approval_workflow.utils.getattr")
    def test_get_users_for_role(self, mock_getattr):
        """Test getting users for a specific role."""

        # Mock getattr to return 'role' when called with settings and 'APPROVAL_ROLE_FIELD'
        def side_effect(obj, attr, default=None):
            if attr == "APPROVAL_ROLE_FIELD":
                return "role"
            return default

        mock_getattr.side_effect = side_effect

        users = get_users_for_role(self.manager_role)

        # Should return users with manager role
        self.assertEqual(len(users), 3)
        self.assertIn(self.user1, users)
        self.assertIn(self.user2, users)
        self.assertIn(self.user3, users)
        self.assertNotIn(self.user4, users)  # user4 has director role

    def test_get_users_for_role_with_none(self):
        """Test getting users for None role returns empty list."""
        users = get_users_for_role(None)
        self.assertEqual(users, [])

    def test_get_user_with_least_assignments(self):
        """Test getting user with least assignments using annotation."""
        # Create some approval instances to test assignment counting
        ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            status=ApprovalStatus.CURRENT,
        )
        ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=2,
            assigned_to=self.user1,
            status=ApprovalStatus.PENDING,
        )
        ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=3,
            assigned_to=self.user2,
            status=ApprovalStatus.APPROVED,
        )

        # user1 has 2 assignments, user2 has 1, user3 has 0
        users = [self.user1, self.user2, self.user3]
        selected_user = get_user_with_least_assignments(users)

        # Should select user3 (0 assignments)
        self.assertEqual(selected_user, self.user3)

    def test_get_user_with_least_assignments_empty_list(self):
        """Test get_user_with_least_assignments with empty list raises ValueError."""
        with self.assertRaises(ValueError):
            get_user_with_least_assignments([])


class TestRoleBasedApprovalIntegration(RoleBasedApprovalTestCase):
    """Integration tests for complete role-based approval workflows."""

    @patch("approval_workflow.utils.get_users_for_role")
    def test_mixed_user_and_role_based_workflow(self, mock_get_users):
        """Test workflow mixing user-based and role-based steps."""
        mock_get_users.return_value = [self.user2, self.user3]

        # Create a workflow: user1 -> role-based (ANYONE: user2,user3) -> user4

        # Step 1: Regular user-based approval
        step1 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            status=ApprovalStatus.CURRENT,
        )

        # Step 2: Role-based approval (template)
        step2_template = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=2,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.ANYONE,
            status=ApprovalStatus.PENDING,
        )

        # Step 3: Regular user-based approval
        step3 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=3,
            assigned_to=self.user4,
            status=ApprovalStatus.PENDING,
        )

        # User1 approves step 1
        result = advance_flow(step1, "approved", self.user1)

        # Should activate role-based step 2
        self.assertIsNotNone(result)
        self.assertEqual(result.step_number, 2)

        # Check that multiple CURRENT instances were created for step 2
        current_step2_instances = ApprovalInstance.objects.filter(
            flow=self.flow, step_number=2, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(current_step2_instances.count(), 2)

        # One of the role users approves step 2
        step2_instance = current_step2_instances.first()
        result = advance_flow(step2_instance, "approved", step2_instance.assigned_to)

        # Should advance to step 3
        self.assertIsNotNone(result)
        self.assertEqual(result.step_number, 3)
        self.assertEqual(result.assigned_to, self.user4)
        self.assertEqual(result.status, ApprovalStatus.CURRENT)

        # Check that other step 2 instances were deleted
        remaining_step2_instances = ApprovalInstance.objects.filter(
            flow=self.flow, step_number=2, status=ApprovalStatus.CURRENT
        )
        self.assertEqual(remaining_step2_instances.count(), 0)

    def test_rejection_in_role_based_step(self):
        """Test rejection in a role-based approval step."""
        # Create role-based instances (CONSENSUS strategy)
        inst1 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.CONSENSUS,
            status=ApprovalStatus.CURRENT,
        )
        inst2 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user2,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            role_selection_strategy=RoleSelectionStrategy.CONSENSUS,
            status=ApprovalStatus.CURRENT,
        )

        # Create next step
        step2 = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=2,
            assigned_to=self.user4,
            status=ApprovalStatus.PENDING,
        )

        # User1 rejects
        result = advance_flow(inst1, "rejected", self.user1, comment="Rejected")

        # Should return None (workflow terminated)
        self.assertIsNone(result)

        # Check that rejection was recorded
        inst1.refresh_from_db()
        self.assertEqual(inst1.status, ApprovalStatus.REJECTED)

        # Check that remaining steps were deleted
        self.assertFalse(ApprovalInstance.objects.filter(pk=inst2.pk).exists())
        self.assertFalse(ApprovalInstance.objects.filter(pk=step2.pk).exists())


class TestErrorHandling(RoleBasedApprovalTestCase):
    """Test error handling in role-based approvals."""

    def test_activate_role_step_with_no_users(self):
        """Test activating role step when no users have the role."""
        # Create empty role
        empty_role = MockRole.objects.create(name="Empty Role")

        with patch("approval_workflow.utils.get_users_for_role", return_value=[]):
            step_template = ApprovalInstance.objects.create(
                flow=self.flow,
                step_number=1,
                assigned_role_content_type=self.role_content_type,
                assigned_role_object_id=str(empty_role.pk),
                role_selection_strategy=RoleSelectionStrategy.ANYONE,
                status=ApprovalStatus.PENDING,
            )

            with self.assertRaises(ValueError) as context:
                _activate_role_based_step(step_template)

            self.assertIn("No users found for role", str(context.exception))

    def test_invalid_role_selection_strategy(self):
        """Test handling of invalid role selection strategy."""
        # Create an instance with invalid strategy (bypassing model validation)
        inst = ApprovalInstance.objects.create(
            flow=self.flow,
            step_number=1,
            assigned_to=self.user1,
            assigned_role_content_type=self.role_content_type,
            assigned_role_object_id=str(self.manager_role.pk),
            status=ApprovalStatus.CURRENT,
        )

        # Manually set invalid strategy
        inst.role_selection_strategy = "invalid_strategy"
        inst.save(update_fields=["role_selection_strategy"])

        with self.assertRaises(ValueError) as context:
            advance_flow(inst, "approved", self.user1)

        self.assertIn("Unknown role selection strategy", str(context.exception))
