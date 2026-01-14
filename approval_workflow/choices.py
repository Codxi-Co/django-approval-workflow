"""
Choice enums for approval workflow statuses and actions.

This module provides type-safe choices for approval workflow models with
built-in internationalization support.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ApprovalStatus(models.TextChoices):
    """
    Status of the approval instance.

    PERFORMANCE OPTIMIZATION:
    - CURRENT: Denormalized status for O(1) current step lookup
    - Only one instance per flow should have CURRENT status at any time
    - This eliminates the need for complex queries and reduces index overhead
    """

    PENDING = "pending", _("Pending")
    CURRENT = "current", _("Current")  # NEW: Active step requiring approval
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
    NEEDS_RESUBMISSION = "resubmission", _("Needs Resubmission")
    DELEGATED = "delegated", _("Delegated")
    ESCALATED = "escalated", _("Escalated")
    CANCELLED = "cancelled", _("Cancelled")
    COMPLETED = "completed", _("Completed")


class RoleSelectionStrategy(models.TextChoices):
    """
    Strategy for role-based approval selection.

    When a step is assigned to a role instead of a specific user,
    this determines how approvers are selected from users with that role.

    Strategies are organized into categories:
    - Basic: ANYONE, CONSENSUS, ROUND_ROBIN
    - Quorum-based: QUORUM, MAJORITY, PERCENTAGE
    - Hierarchical: HIERARCHY_UP, HIERARCHY_CHAIN, MANAGEMENT_PATH
    - Dynamic: DYNAMIC_ATTRIBUTE, DYNAMIC_FUNCTION
    - Specialized: LEAD_ONLY, SENIORITY_BASED, WORKLOAD_BALANCED
    """

    # === Basic Strategies ===
    ANYONE = "anyone", _("Anyone with role can approve")
    CONSENSUS = "consensus", _("All users with role must approve")
    ROUND_ROBIN = "round_robin", _("Distribute approvals evenly among role users")

    # === Quorum-Based Strategies ===
    QUORUM = "quorum", _("Require N out of M users to approve (configurable)")
    MAJORITY = "majority", _("Require majority (>50%) of role users to approve")
    PERCENTAGE = "percentage", _("Require X% of role users to approve")

    # === Hierarchical Strategies ===
    HIERARCHY_UP = "hierarchy_up", _("Escalate through N levels of role hierarchy")
    HIERARCHY_CHAIN = "hierarchy_chain", _(
        "Require approval from entire chain (direct manager + N levels up)"
    )
    MANAGEMENT_PATH = "management_path", _("Follow organizational reporting structure")

    # === Dynamic Strategies ===
    DYNAMIC_ATTRIBUTE = "dynamic_attribute", _(
        "Select users based on business object attributes"
    )
    DYNAMIC_FUNCTION = "dynamic_function", _("Custom function to determine approvers")

    # === Specialized Strategies ===
    LEAD_ONLY = "lead_only", _("Only the role lead/owner can approve")
    SENIORITY_BASED = "seniority_based", _("Assign based on user seniority/tenure")
    WORKLOAD_BALANCED = "workload_balanced", _(
        "Distribute based on current active approvals only"
    )


class ApprovalType(models.TextChoices):
    """
    Type of approval action for the instance.

    This determines the behavior and requirements for the approval step:
    - APPROVE: Normal approval flow
    - SUBMIT: Normal approval flow but requires form data
    - CHECK_IN_VERIFY: Verification step with checking, can CLOSE or delegate
    - MOVE: Transfer/move step without requiring form data
    """

    APPROVE = "approve", _("Approve")
    SUBMIT = "submit", _("Submit with Form")
    CHECK_IN_VERIFY = "check_in_verify", _("Check-in/Verify")
    MOVE = "move", _("Move")
