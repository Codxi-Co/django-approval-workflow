"""
Choice enums for approval workflow statuses and actions.
"""

from django.db import models


class ApprovalStatus(models.TextChoices):
    """
    Status of the approval instance.

    PERFORMANCE OPTIMIZATION:
    - CURRENT: Denormalized status for O(1) current step lookup
    - Only one instance per flow should have CURRENT status at any time
    - This eliminates the need for complex queries and reduces index overhead
    """

    PENDING = "pending", "Pending"
    CURRENT = "current", "Current"  # NEW: Active step requiring approval
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NEEDS_RESUBMISSION = "resubmission", "Needs Resubmission"
    DELEGATED = "delegated", "Delegated"
    ESCALATED = "escalated", "Escalated"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class RoleSelectionStrategy(models.TextChoices):
    """
    Strategy for role-based approval selection.

    When a step is assigned to a role instead of a specific user,
    this determines how approvers are selected from users with that role.
    """

    ANYONE = "anyone", "Anyone with role can approve"
    CONSENSUS = "consensus", "All users with role must approve"
    ROUND_ROBIN = "round_robin", "Distribute approvals evenly among role users"
