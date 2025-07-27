"""
Choice enums for approval workflow statuses and actions.
"""

from django.db import models


class ApprovalStatus(models.TextChoices):
    """
    Status of the approval instance.
    """

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NEEDS_RESUBMISSION = "resubmission", "Needs Resubmission"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"
