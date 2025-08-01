"""Models for approval_workflow Django app.

Includes core models to support dynamic multi-step approval flows
attached to arbitrary Django models using GenericForeignKey.

Author: Mohamed Salah
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .choices import ApprovalStatus, RoleSelectionStrategy

logger = logging.getLogger(__name__)
User = get_user_model()


class ApprovalFlow(models.Model):
    """
    Represents a reusable approval flow attached to a specific object.

    This model uses GenericForeignKey to dynamically associate a flow
    to any model instance (e.g., Ticket, Stage, etc.).
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    target = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options for ApprovalFlow model."""

        indexes = [
            # Composite index for efficient flow lookups by object
            models.Index(
                fields=["content_type", "object_id"], name="approval_flow_object_idx"
            ),
        ]
        # Ensure one flow per object
        unique_together = ["content_type", "object_id"]

    def __str__(self):
        return f"Flow for {self.content_type.app_label}.{self.content_type.model}({self.object_id})"

    def save(self, *args, **kwargs):
        """Override save to add logging."""
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            logger.info(
                "New approval flow created - Flow ID: %s, Object: %s.%s (%s)",
                self.pk,
                self.content_type.app_label,
                self.content_type.model,
                self.object_id,
            )
        else:
            logger.debug("Approval flow updated - Flow ID: %s", self.pk)


class ApprovalInstance(models.Model):
    """
    Tracks the progress of an approval flow.

    Merges the concept of "step" into this model directly, where each
    instance represents the current step in the flow and can be updated
    with approval/rejection logic.

    The instance also stores the role responsible for the step.
    """

    flow = models.ForeignKey(
        ApprovalFlow, on_delete=models.CASCADE, related_name="instances"
    )
    form_data = models.JSONField(null=True, blank=True)

    # Dynamic form using GenericForeignKey to avoid migrations
    form_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_forms",
        help_text="Content type of the dynamic form model",
    )
    form_object_id = models.CharField(max_length=255, null=True, blank=True)
    form = GenericForeignKey("form_content_type", "form_object_id")
    step_number = models.PositiveIntegerField(
        default=1, help_text="The current step in the flow"
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User currently assigned to act on this step",
    )

    action_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_actions",
        help_text="User who actually performed the approve/reject action",
    )

    status = models.CharField(
        max_length=30,
        choices=ApprovalStatus,
        default=ApprovalStatus.PENDING,
        help_text="Current approval status",
    )

    comment = models.TextField(blank=True)

    # SLA tracking
    sla_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="SLA duration for this step (e.g., 2 days, 4 hours). Optional.",
    )

    # Role hierarchy permissions
    allow_higher_level = models.BooleanField(
        default=False,
        help_text="Allow users with higher roles to approve this step on behalf of assigned user",
    )

    # Role-based approval fields
    assigned_role_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_roles",
        help_text="Content type of the role model from settings",
    )
    assigned_role_object_id = models.CharField(
        max_length=255, null=True, blank=True, help_text="ID of the role instance"
    )
    assigned_role = GenericForeignKey(
        "assigned_role_content_type", "assigned_role_object_id"
    )

    role_selection_strategy = models.CharField(
        max_length=20,
        choices=RoleSelectionStrategy,
        null=True,
        blank=True,
        help_text="Strategy for selecting approvers when assigned to a role",
    )

    # Additional fields for custom data
    extra_fields = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional custom fields for extending functionality without package modifications",
    )

    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for ApprovalInstance model."""

        ordering = ["-started_at"]
        indexes = [
            # OPTIMIZED: Single strategic index for CURRENT status O(1) lookups
            models.Index(fields=["flow", "status"], name="appinst_flow_status_idx"),
            # Index for finding approvals by assigned user (dashboard queries)
            models.Index(
                fields=["assigned_to", "status"], name="appinst_assigned_status_idx"
            ),
            # Index for temporal queries (reporting/analytics)
            models.Index(fields=["started_at"], name="appinst_started_at_idx"),
        ]
        constraints = [
            # For user-assigned approvals, ensure only one CURRENT status per flow
            # For role-based approvals, we allow multiple CURRENT instances
            models.UniqueConstraint(
                fields=["flow"],
                condition=models.Q(status="current")
                & models.Q(assigned_to__isnull=False)
                & models.Q(assigned_role_content_type__isnull=True),
                name="unique_current_per_flow_user",
            ),
        ]

    def __str__(self):
        return f"{self.flow} - Step {self.step_number} [{self.status}]"

    def __repr__(self):
        return f"<ApprovalInstance flow_id={self.flow.id} step={self.step_number} status={self.status}>"

    def save(self, *args, **kwargs):
        """Override save to add logging and auto-set form_content_type."""
        is_new = self._state.adding
        old_status = None

        # Auto-set form_content_type from settings if not already set
        if not self.form_content_type:
            form_model_path = getattr(settings, "APPROVAL_DYNAMIC_FORM_MODEL", None)
            if form_model_path:
                try:
                    app_label, model_name = form_model_path.split(".", 1)
                    content_type = ContentType.objects.get(
                        app_label=app_label, model=model_name.lower()
                    )
                    self.form_content_type = content_type
                except (ValueError, ContentType.DoesNotExist) as e:
                    logger.warning(
                        "Invalid APPROVAL_DYNAMIC_FORM_MODEL setting: %s - %s",
                        form_model_path,
                        e,
                    )

        # Auto-set role_content_type from settings if not already set
        if not self.assigned_role_content_type and self.assigned_role_object_id:
            role_model_path = getattr(settings, "APPROVAL_ROLE_MODEL", None)
            if role_model_path:
                try:
                    app_label, model_name = role_model_path.split(".", 1)
                    content_type = ContentType.objects.get(
                        app_label=app_label, model=model_name.lower()
                    )
                    self.assigned_role_content_type = content_type
                except (ValueError, ContentType.DoesNotExist) as e:
                    logger.warning(
                        "Invalid APPROVAL_ROLE_MODEL setting: %s - %s",
                        role_model_path,
                        e,
                    )

        if not is_new:
            # Get the old status before saving
            try:
                old_instance = ApprovalInstance.objects.get(pk=self.pk)
                old_status = old_instance.status
            except ApprovalInstance.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if is_new:
            logger.info(
                "New approval instance created - Flow ID: %s, Step: %s, Status: %s, Assigned to: %s",
                self.flow.id,
                self.step_number,
                self.status,
                self.assigned_to.username if self.assigned_to else None,
            )
        elif old_status and old_status != self.status:
            logger.info(
                "Approval instance status changed - Flow ID: %s, Step: %s, Old status: %s, New status: %s, Action user: %s",
                self.flow.id,
                self.step_number,
                old_status,
                self.status,
                self.action_user.username if self.action_user else None,
            )
        else:
            logger.debug(
                "Approval instance updated - Flow ID: %s, Step: %s",
                self.flow.id,
                self.step_number,
            )
