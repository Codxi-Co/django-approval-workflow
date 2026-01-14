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
from django.utils.translation import gettext_lazy as _

from .choices import ApprovalStatus, ApprovalType, RoleSelectionStrategy

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
        verbose_name = _("Approval Flow")
        verbose_name_plural = _("Approval Flows")

    def __str__(self):
        """Return string representation with translation support."""
        return _("Flow for %(content_type)s(%(object_id)s)") % {
            "content_type": f"{self.content_type.app_label}.{self.content_type.model}",
            "object_id": self.object_id,
        }

    def save(self, *args, **kwargs):
        """Override save to add logging."""
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            logger.info(
                "[APPROVAL_WORKFLOW] ✨ NEW FLOW CREATED | "
                "Flow ID: %(flow_id)s | Object: %(app_label)s.%(model)s(%(object_id)s) | "
                "Event: flow_created",
                {
                    "flow_id": self.pk,
                    "app_label": self.content_type.app_label,
                    "model": self.content_type.model,
                    "object_id": self.object_id,
                    "event": "flow_created",
                },
            )
        else:
            logger.debug(
                "[APPROVAL_WORKFLOW] 📝 FLOW UPDATED | "
                "Flow ID: %(flow_id)s | Event: flow_updated",
                {"flow_id": self.pk, "event": "flow_updated"},
            )


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

    approval_type = models.CharField(
        max_length=20,
        choices=ApprovalType,
        default=ApprovalType.APPROVE,
        help_text="Type of approval action (approve, submit, check-in/verify, move)",
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

    # === Quorum-Based Approval Fields ===
    quorum_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "Number of approvals required for QUORUM strategy (e.g., 2 out of 5)"
        ),
    )
    quorum_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "Total number of users for quorum calculation (optional, defaults to role users count)"
        ),
    )
    percentage_required = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Percentage required for PERCENTAGE strategy (e.g., 66.67 for 2/3)"
        ),
    )

    # === Hierarchical Approval Fields ===
    hierarchy_levels = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=1,
        help_text=_("Number of hierarchy levels to escalate for HIERARCHY_UP strategy"),
    )
    hierarchy_base_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hierarchy_base_approvals",
        help_text=_("Base user for hierarchical approval (e.g., account manager)"),
    )

    # === Delegation & Escalation Tracking ===
    delegation_chain = models.JSONField(
        null=True,
        blank=True,
        help_text=_(
            "Track delegation history: [{from_user, to_user, timestamp, reason}]"
        ),
    )
    escalation_level = models.PositiveIntegerField(
        default=0,
        help_text=_("Current escalation level for this approval instance"),
    )
    max_escalation_level = models.PositiveIntegerField(
        default=3,
        help_text=_("Maximum escalation level allowed for this approval"),
    )

    # === SLA & Timeout Management ===
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Deadline for this approval step"),
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text=_("Whether reminder notification has been sent"),
    )
    escalation_on_timeout = models.BooleanField(
        default=False,
        help_text=_("Whether to auto-escalate when timeout is reached"),
    )
    timeout_action = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("escalate", _("Escalate")),
            ("delegate", _("Delegate")),
            ("auto_approve", _("Auto Approve")),
            ("reject", _("Auto Reject")),
        ],
        help_text=_("Action to take when timeout is reached"),
    )

    # === Parallel Approval Support ===
    parallel_group = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Group identifier for parallel approval tracks"),
    )
    parallel_required = models.BooleanField(
        default=False,
        help_text=_(
            "Whether this parallel step must complete before next sequential step"
        ),
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
            # NEW: Index for SLA/timeout tracking
            models.Index(
                fields=["due_date", "status"], name="appinst_due_date_status_idx"
            ),
            # NEW: Index for parallel approval grouping
            models.Index(
                fields=["flow", "parallel_group", "status"], name="appinst_parallel_idx"
            ),
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
        """Return string representation with translation support."""
        assigned = (
            self.assigned_to.username
            if self.assigned_to
            else self.assigned_role or "Unassigned"
        )
        return f"{self.flow} - Step {self.step_number} [{self.status}] → {assigned}"

    def __repr__(self):
        """Return detailed representation for debugging."""
        return (
            f"<ApprovalInstance flow_id={self.flow.id} step={self.step_number} "
            f"status={self.status} assigned_to={self.assigned_to_id} "
            f"role={self.assigned_role_object_id}>"
        )

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
                        "[APPROVAL_WORKFLOW] Invalid APPROVAL_DYNAMIC_FORM_MODEL setting: %s - %s",
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
                        "[APPROVAL_WORKFLOW] Invalid APPROVAL_ROLE_MODEL setting: %s - %s",
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

        # === Enhanced Structured Logging ===
        if is_new:
            logger.info(
                "[APPROVAL_WORKFLOW] ✨ NEW INSTANCE CREATED | "
                "Flow ID: %(flow_id)s | Step: %(step)s | Status: %(status)s | "
                "Assigned To: %(assigned_user)s | Strategy: %(strategy)s | "
                "Type: %(approval_type)s",
                {
                    "flow_id": self.flow.id,
                    "step": self.step_number,
                    "status": self.status,
                    "assigned_user": (
                        self.assigned_to.username if self.assigned_to else None
                    ),
                    "strategy": self.role_selection_strategy or "N/A",
                    "approval_type": self.approval_type,
                    "event": "instance_created",
                },
            )
        elif old_status and old_status != self.status:
            logger.info(
                "[APPROVAL_WORKFLOW] 🔄 STATUS CHANGED | "
                "Flow ID: %(flow_id)s | Step: %(step)s | "
                "Old Status: %(old_status)s → New Status: %(new_status)s | "
                "Action User: %(action_user)s | Comment: %(comment)s",
                {
                    "flow_id": self.flow.id,
                    "step": self.step_number,
                    "old_status": old_status,
                    "new_status": self.status,
                    "action_user": (
                        self.action_user.username if self.action_user else None
                    ),
                    "comment": self.comment[:100] if self.comment else None,
                    "event": "status_changed",
                },
            )
        else:
            logger.debug(
                "[APPROVAL_WORKFLOW] 📝 INSTANCE UPDATED | "
                "Flow ID: %(flow_id)s | Step: %(step)s | "
                "Fields Updated: %(fields)s",
                {
                    "flow_id": self.flow.id,
                    "step": self.step_number,
                    "fields": "update",
                    "event": "instance_updated",
                },
            )
