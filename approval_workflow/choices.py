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


class ApprovalType(models.TextChoices):
    """
    Type of approval action for the instance.

    This determines the behavior and requirements for the approval step:
    - APPROVE: Normal approval flow
    - SUBMIT: Normal approval flow but requires form data
    - CHECK_IN_VERIFY: Verification step with checking, can CLOSE or delegate
    - MOVE: Transfer/move step without requiring form data
    """

    APPROVE = "approve", "Approve"
    SUBMIT = "submit", "Submit with Form"
    CHECK_IN_VERIFY = "check_in_verify", "Check-in/Verify"
    MOVE = "move", "Move"
