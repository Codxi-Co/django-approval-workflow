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

from .choices import ApprovalStatus

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

    form_model = getattr(settings, "APPROVAL_DYNAMIC_FORM_MODEL", "contenttypes.ContentType")

    form = models.ForeignKey(
        form_model,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional dynamic form for this step",
    )
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

    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.flow} - Step {self.step_number} [{self.status}]"

    def __repr__(self):
        return f"<ApprovalInstance flow_id={self.flow.id} step={self.step_number} status={self.status}>"
    
    def save(self, *args, **kwargs):
        """Override save to add logging."""
        is_new = self._state.adding
        old_status = None
        
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
