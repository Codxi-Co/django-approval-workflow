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
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"
