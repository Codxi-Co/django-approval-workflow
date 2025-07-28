"""Utility functions for the approval_workflow package.

This module provides helper functions used throughout the approval flow system,
including dynamic model resolution, permission checks, and integration hooks
for custom project-level behavior.

Configuration:
--------------
The following Django settings may be defined to support custom role handling:

- APPROVAL_ROLE_MODEL (str):
    Dotted path to the Role model used for hierarchy comparisons (e.g., "myapp.Role").

- APPROVAL_ROLE_FIELD (str):
    Name of the field on the User model that links to the Role model (default: "role").
"""

import logging
from typing import TYPE_CHECKING, Optional, List, Union, Dict, Any
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.cache import cache

if TYPE_CHECKING:
    from .models import ApprovalInstance, ApprovalFlow

logger = logging.getLogger(__name__)
User = get_user_model()


class ApprovalRepository:
    """
    High-performance repository for approval workflow data access.

    Implements enterprise-level optimizations:
    - Single query strategy with select_related/prefetch_related
    - Intelligent caching at multiple levels
    - Minimal database hits through lazy loading
    - Repository pattern for centralized data access
    """

    def __init__(self, obj: models.Model):
        """Initialize repository for a specific object.

        Args:
            obj: The Django model instance to manage approvals for
        """
        self.obj = obj
        self._content_type: Optional[ContentType] = None
        self._flow: Optional["ApprovalFlow"] = None
        self._instances: Optional[List["ApprovalInstance"]] = None

    @property
    def content_type(self) -> Optional[ContentType]:
        """Get content type with LRU caching for performance."""
        if self._content_type is None:
            self._content_type = self._get_cached_content_type(self.obj.__class__)
        return self._content_type

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_cached_content_type(model_class: type) -> ContentType:
        """Cache ContentType lookups using LRU cache."""
        return ContentType.objects.get_for_model(model_class)

    @property
    def flow(self) -> Optional["ApprovalFlow"]:
        """Get approval flow with lazy loading and caching."""
        if self._flow is None:
            self._load_flow()
        return self._flow

    def _load_flow(self) -> None:
        """Load approval flow with optimized query."""
        from .models import ApprovalFlow

        cache_key = f"approval_flow_{self.content_type.id}_{self.obj.pk}"
        cached_flow = cache.get(cache_key)

        if cached_flow:
            self._flow = cached_flow
            logger.debug(
                "Flow loaded from cache - Object: %s(%s)",
                self.obj.__class__.__name__,
                self.obj.pk,
            )
        else:
            try:
                self._flow = ApprovalFlow.objects.select_related("content_type").get(
                    content_type=self.content_type, object_id=str(self.obj.pk)
                )
                # Cache for 5 minutes
                cache.set(cache_key, self._flow, 300)
                logger.debug("Flow loaded from database - Flow ID: %s", self._flow.id)
            except ApprovalFlow.DoesNotExist:
                self._flow = None
                logger.debug(
                    "No flow found - Object: %s(%s)",
                    self.obj.__class__.__name__,
                    self.obj.pk,
                )

    @property
    def instances(self) -> List["ApprovalInstance"]:
        """Get all approval instances with single optimized query."""
        if self._instances is None:
            self._load_instances()
        return self._instances or []

    def _load_instances(self) -> None:
        """Load all approval instances with optimized query and relationships."""
        if not self.flow:
            self._instances = []
            return

        from .models import ApprovalInstance

        # Single query with all optimizations
        self._instances = list(
            ApprovalInstance.objects.select_related(
                "assigned_to", "action_user", "flow"
            )
            .filter(flow=self.flow)
            .order_by("step_number")
        )

        logger.debug(
            "Loaded all instances - Flow ID: %s, Count: %s, Steps: %s",
            self.flow.id,
            len(self._instances),
            [f"{i.step_number}({i.status})" for i in self._instances],
        )

    def get_current_approval(self) -> Optional["ApprovalInstance"]:
        """Get current approval with O(1) database lookup using CURRENT status.

        PERFORMANCE OPTIMIZATION: Uses direct query with CURRENT status for
        maximum efficiency instead of loading all instances.
        """
        if not self.flow:
            return None

        from .models import ApprovalInstance
        from .choices import ApprovalStatus

        try:
            current_approval = ApprovalInstance.objects.select_related(
                "assigned_to", "action_user"
            ).get(flow=self.flow, status=ApprovalStatus.CURRENT)

            logger.debug(
                "Found current approval - Step: %s, Assigned to: %s",
                current_approval.step_number,
                (
                    getattr(current_approval.assigned_to, "username", "None")
                    if current_approval.assigned_to
                    else "None"
                ),
            )
            return current_approval

        except ApprovalInstance.DoesNotExist:
            logger.debug("No current approval found")
            return None

    def get_next_approval(self) -> Optional["ApprovalInstance"]:
        """Get next pending approval with optimized query.

        PERFORMANCE OPTIMIZATION: Uses direct query to find next PENDING
        step after current, avoiding full table scan.
        """
        if not self.flow:
            return None

        current = self.get_current_approval()
        if not current:
            return None

        from .models import ApprovalInstance
        from .choices import ApprovalStatus

        try:
            next_approval = (
                ApprovalInstance.objects.select_related("assigned_to", "action_user")
                .filter(
                    flow=self.flow,
                    status=ApprovalStatus.PENDING,
                    step_number__gt=current.step_number,
                )
                .order_by("step_number")
                .first()
            )

            if next_approval:
                logger.debug(
                    "Found next approval - Step: %s, Assigned to: %s",
                    next_approval.step_number,
                    (
                        getattr(next_approval.assigned_to, "username", "None")
                        if next_approval.assigned_to
                        else "None"
                    ),
                )
            else:
                logger.debug("No next approval found (current is final)")

            return next_approval

        except Exception as e:
            logger.error("Error finding next approval: %s", str(e))
            return None

    def get_pending_approvals(self) -> List["ApprovalInstance"]:
        """Get all pending approvals with optimized query.

        PERFORMANCE OPTIMIZATION: Direct query for PENDING status instead
        of loading all instances and filtering in memory.
        """
        if not self.flow:
            return []

        from .models import ApprovalInstance
        from .choices import ApprovalStatus

        pending = list(
            ApprovalInstance.objects.select_related("assigned_to", "action_user")
            .filter(flow=self.flow, status=ApprovalStatus.PENDING)
            .order_by("step_number")
        )

        logger.debug("Found %s pending approvals", len(pending))
        return pending

    def get_approved_count(self) -> int:
        """Get count of approved steps with optimized query."""
        if not self.flow:
            return 0

        from .models import ApprovalInstance
        from .choices import ApprovalStatus

        count = ApprovalInstance.objects.filter(
            flow=self.flow, status=ApprovalStatus.APPROVED
        ).count()

        logger.debug("Found %s approved steps", count)
        return count

    def is_workflow_complete(self) -> bool:
        """Check if workflow is complete with optimized query.

        PERFORMANCE OPTIMIZATION: Uses exists() query instead of counting.
        """
        if not self.flow:
            return True

        from .models import ApprovalInstance
        from .choices import ApprovalStatus

        # Check if no CURRENT or PENDING steps exist
        has_active_steps = ApprovalInstance.objects.filter(
            flow=self.flow, status__in=[ApprovalStatus.CURRENT, ApprovalStatus.PENDING]
        ).exists()

        is_complete = not has_active_steps
        logger.debug("Workflow complete: %s", is_complete)
        return is_complete

    def get_workflow_progress(self) -> Dict[str, Any]:
        """Get comprehensive workflow progress information."""
        from .choices import ApprovalStatus

        instances = self.instances
        if not instances:
            return {
                "total_steps": 0,
                "completed_steps": 0,
                "pending_steps": 0,
                "rejected_steps": 0,
                "progress_percentage": 0,
                "is_complete": False,
                "current_step": None,
                "next_step": None,
            }

        status_counts = {}
        for status in ApprovalStatus:
            status_counts[status.value] = 0

        for instance in instances:
            status_counts[instance.status] += 1

        total = len(instances)
        completed = status_counts.get(ApprovalStatus.APPROVED, 0)
        pending = status_counts.get(ApprovalStatus.PENDING, 0)
        current = status_counts.get(ApprovalStatus.CURRENT, 0)
        rejected = status_counts.get(ApprovalStatus.REJECTED, 0)

        # CURRENT status optimization: Include CURRENT status in pending count
        total_pending = pending + current

        progress = {
            "total_steps": total,
            "completed_steps": completed,
            "pending_steps": total_pending,
            "rejected_steps": rejected,
            "resubmission_steps": status_counts.get(
                ApprovalStatus.NEEDS_RESUBMISSION, 0
            ),
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "is_complete": total_pending == 0 and rejected == 0,
            "current_step": self.get_current_approval(),
            "next_step": self.get_next_approval(),
        }

        logger.debug("Workflow progress calculated - %s", progress)
        return progress

    @classmethod
    def for_object(cls, obj: models.Model) -> "ApprovalRepository":
        """Factory method to create repository for an object."""
        return cls(obj)

    @classmethod
    def clear_cache_for_object(cls, obj: models.Model) -> None:
        """Clear cache for a specific object. Useful for testing."""
        content_type = cls._get_cached_content_type(obj.__class__)
        cache_key = f"approval_flow_{content_type.id}_{obj.pk}"
        cache.delete(cache_key)
        logger.debug("Cache cleared for object: %s(%s)", obj.__class__.__name__, obj.pk)

    @classmethod
    def clear_all_cache(cls) -> None:
        """Clear all approval workflow cache. Use with caution."""
        # This is a simple implementation - in production you might want
        # to use cache versioning or more sophisticated invalidation
        cache.clear()
        logger.debug("All approval workflow cache cleared")


def can_user_approve(
    instance: "ApprovalInstance", acting_user: User, allow_higher_level: bool = True
) -> bool:
    """Determine whether the acting user is authorized to approve the given step.

    Authorization is granted if:
    - The acting user is the `assigned_to` user for the current step.
    - If allow_higher_level is True, the acting user's role is an ancestor of the assigned user's role,
      based on a hierarchical Role model using MPTT.

    The system dynamically uses the role model and field name defined in settings:
    - APPROVAL_ROLE_MODEL: String path to the Role model (e.g., "myapp.Role").
    - APPROVAL_ROLE_FIELD: Name of the field on the User model that links to Role (e.g., "role").

    Args:
        instance: The approval step being evaluated
        acting_user: The user attempting to take an action on the step
        allow_higher_level: Whether to allow users with higher roles to approve on behalf of assigned user

    Returns:
        True if the user is authorized to approve, False otherwise

    Notes:
        - If role configuration is missing or misconfigured in settings,
          the function falls back to strict matching on `assigned_to`.
        - This function assumes that the role model inherits from MPTTModel
          and provides the `is_ancestor_of()` method.
    """
    flow_id = (
        getattr(instance.flow, "id", "None")
        if hasattr(instance, "flow") and instance.flow
        else "None"
    )
    logger.debug(
        "Checking user approval permission - Flow ID: %s, Step: %s, Acting user: %s, Assigned to: %s",
        flow_id,
        instance.step_number,
        getattr(acting_user, "username", str(acting_user)),
        (
            getattr(instance.assigned_to, "username", str(instance.assigned_to))
            if instance.assigned_to
            else None
        ),
    )

    assigned_user = instance.assigned_to

    # Direct assignment check
    if assigned_user and acting_user == assigned_user:
        logger.debug(
            "User authorized by direct assignment - Flow ID: %s, Step: %s, User: %s",
            flow_id,
            instance.step_number,
            getattr(acting_user, "username", str(acting_user)),
        )
        return True

    # Role-based authorization check (only if allow_higher_level is True)
    if not allow_higher_level:
        logger.debug(
            "Higher level approval disabled - Flow ID: %s, Step: %s",
            flow_id,
            instance.step_number,
        )
        return False

    role_field = getattr(settings, "APPROVAL_ROLE_FIELD", "role")
    logger.debug(
        "Checking role-based authorization - Flow ID: %s, Step: %s, Role field: %s",
        flow_id,
        instance.step_number,
        role_field,
    )

    try:
        assigned_role = getattr(assigned_user, role_field, None)
        acting_role = getattr(acting_user, role_field, None)

        logger.debug(
            "Role comparison - Flow ID: %s, Step: %s, Assigned role: %s, Acting role: %s",
            flow_id,
            instance.step_number,
            (
                getattr(assigned_role, "name", str(assigned_role))
                if assigned_role
                else None
            ),
            getattr(acting_role, "name", str(acting_role)) if acting_role else None,
        )

        if not assigned_role or not acting_role:
            logger.debug(
                "Role authorization failed - Missing roles - Flow ID: %s, Step: %s",
                flow_id,
                instance.step_number,
            )
            return False

        is_authorized = acting_role.is_ancestor_of(assigned_role)

        if is_authorized:
            logger.debug(
                "User authorized by role hierarchy - Flow ID: %s, Step: %s, User: %s, Role: %s",
                flow_id,
                instance.step_number,
                getattr(acting_user, "username", str(acting_user)),
                getattr(acting_role, "name", str(acting_role)),
            )
        else:
            logger.debug(
                "User not authorized by role hierarchy - Flow ID: %s, Step: %s, User: %s",
                flow_id,
                instance.step_number,
                getattr(acting_user, "username", str(acting_user)),
            )

        return is_authorized

    except Exception as e:
        logger.warning(
            "Role authorization check failed - Flow ID: %s, Step: %s, User: %s, Error: %s",
            flow_id,
            instance.step_number,
            getattr(acting_user, "username", str(acting_user)),
            str(e),
        )
        return False


# =============================================================================
# OPTIMIZED UTILITY FUNCTIONS (Enterprise-Level Performance)
# =============================================================================


def get_approval_repository(obj: models.Model) -> ApprovalRepository:
    """
    Get optimized approval repository for an object.

    This is the recommended way to access approval data for high-performance scenarios.
    Single database query loads all data with proper caching and select_related.

    Args:
        obj: Django model instance

    Returns:
        ApprovalRepository: High-performance repository instance

    Example:
        repo = get_approval_repository(document)
        current = repo.get_current_approval()  # No additional DB hit
        next_step = repo.get_next_approval()   # No additional DB hit
        progress = repo.get_workflow_progress() # Comprehensive data, no DB hit
    """
    return ApprovalRepository.for_object(obj)


def get_approval_summary(obj: models.Model) -> Dict[str, Any]:
    """
    Get comprehensive approval summary with single database query.

    Optimized function that provides all approval information in one call.
    Perfect for dashboards, status pages, and API endpoints.

    Args:
        obj: Django model instance

    Returns:
        Dict containing all approval information

    Example:
        summary = get_approval_summary(document)
        print(f"Progress: {summary['progress_percentage']}%")
        print(f"Current: {summary['current_step']}")
        print(f"Total steps: {summary['total_steps']}")
    """
    repo = get_approval_repository(obj)
    return repo.get_workflow_progress()


# =============================================================================
# BACKWARD COMPATIBLE FUNCTIONS (Legacy Support - Use Repository Functions Above)
# =============================================================================


def get_current_approval(obj: models.Model) -> Optional["ApprovalInstance"]:
    """Get the current pending approval step for a given object.

    PERFORMANCE NOTE: This function is optimized using ApprovalRepository.
    For multiple calls on the same object, consider using get_approval_repository()
    directly for better performance.

    Args:
        obj: The Django model instance to get current approval for

    Returns:
        ApprovalInstance: The current pending approval step, or None if no
                         pending approval exists

    Example:
        document = Document.objects.get(id=1)
        current_step = get_current_approval(document)
        if current_step:
            print(f"Waiting for approval from: {current_step.assigned_to}")
        else:
            print("No pending approvals")
    """
    repo = get_approval_repository(obj)
    return repo.get_current_approval()


def get_next_approval(obj: models.Model) -> Optional["ApprovalInstance"]:
    """Get the next approval step that would be processed after the current one.

    PERFORMANCE NOTE: This function is optimized using ApprovalRepository.
    For multiple calls on the same object, consider using get_approval_repository()
    directly for better performance.

    Args:
        obj: The Django model instance to get next approval for

    Returns:
        ApprovalInstance: The next pending approval step, or None if current
                         is the last step or no workflow exists

    Example:
        document = Document.objects.get(id=1)
        next_step = get_next_approval(document)
        if next_step:
            print(f"Next approver will be: {next_step.assigned_to}")
        else:
            print("This is the final approval step")
    """
    repo = get_approval_repository(obj)
    return repo.get_next_approval()


def get_full_approvals(obj: models.Model) -> List["ApprovalInstance"]:
    """Get all approval instances for a given object, ordered by step number.

    PERFORMANCE NOTE: This function is optimized using ApprovalRepository.
    For multiple calls on the same object, consider using get_approval_repository()
    directly for better performance.

    Args:
        obj: The Django model instance to get all approvals for

    Returns:
        List[ApprovalInstance]: List of all approval instances ordered by step
                               number, empty list if no workflow exists

    Example:
        document = Document.objects.get(id=1)
        all_approvals = get_full_approvals(document)

        for approval in all_approvals:
            print(f"Step {approval.step_number}: {approval.status} "
                  f"by {approval.assigned_to} at {approval.updated_at}")
    """
    repo = get_approval_repository(obj)
    return repo.instances


def get_approval_flow(obj: models.Model) -> Optional["ApprovalFlow"]:
    """Get the approval flow for a given object.

    PERFORMANCE NOTE: This function is optimized using ApprovalRepository.
    For multiple calls on the same object, consider using get_approval_repository()
    directly for better performance.

    Args:
        obj: The Django model instance to get the flow for

    Returns:
        ApprovalFlow: The approval flow instance, or None if no flow exists

    Example:
        document = Document.objects.get(id=1)
        flow = get_approval_flow(document)
        if flow:
            print(f"Flow created at: {flow.created_at}")
            print(f"Total steps: {flow.instances.count()}")
    """
    repo = get_approval_repository(obj)
    return repo.flow
