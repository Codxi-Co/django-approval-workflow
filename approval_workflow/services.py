"""Approval flow orchestration services."""

import logging
from typing import Any, Dict, List, Optional, Type

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from functools import lru_cache
from django.db.models import Model, Q

from .choices import ApprovalStatus, RoleSelectionStrategy
from .handlers import get_handler_for_instance
from .models import ApprovalFlow, ApprovalInstance

logger = logging.getLogger(__name__)


@lru_cache(maxsize=128)
def _get_cached_content_type(model_class: type) -> ContentType:
    """Cache ContentType lookups using LRU cache for better performance.

    This reduces database hits when creating multiple approval instances
    with the same model types, especially for role-based approvals.
    """
    return ContentType.objects.get_for_model(model_class)


User = get_user_model()


def _is_user_authorized_for_step(instance: ApprovalInstance, user: User) -> bool:
    """Check if a user is authorized to act on an approval step.

    Args:
        instance: The approval instance to check
        user: The user to authorize

    Returns:
        True if user is authorized, False otherwise
    """
    # For user-based approval, check direct assignment
    if instance.assigned_to:
        return instance.assigned_to == user

    # For role-based approval, check if user has the assigned role
    if instance.assigned_role:
        from .utils import get_users_for_role

        try:
            role_users = get_users_for_role(instance.assigned_role)
            return user in role_users
        except Exception as e:
            logger.warning(
                "Error checking role authorization - Flow ID: %s, Step: %s, User: %s, Error: %s",
                instance.flow.id,
                instance.step_number,
                user.username,
                str(e),
            )
            return False

    logger.warning(
        "No assignment found for approval step - Flow ID: %s, Step: %s",
        instance.flow.id,
        instance.step_number,
    )
    return False


def get_current_approval_for_object(obj: Model) -> Optional[ApprovalInstance]:
    """Get the current approval instance for a given object.

    PERFORMANCE OPTIMIZED: Uses ApprovalRepository for maximum efficiency.
    Single query with proper select_related and caching.

    Args:
        obj: The Django model instance to get approval for

    Returns:
        Current ApprovalInstance if found, None otherwise
    """
    from .utils import get_approval_repository

    # Use optimized repository pattern for better performance
    repo = get_approval_repository(obj)
    current = repo.get_current_approval()

    # Handle both single instance and QuerySet/list of instances
    if hasattr(current, "__iter__") and not isinstance(current, (str, bytes)):
        # Convert QuerySet or list to list and return first instance
        current_list = list(current)
        return current_list[0] if current_list else None

    return current


def advance_flow(
    obj_or_instance=None,
    action: str = None,
    user: User = None,
    comment: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
    resubmission_steps: Optional[List[Dict[str, Any]]] = None,
    delegate_to: Optional[User] = None,
    # Support old keyword-only interface
    instance: Optional[ApprovalInstance] = None,
) -> Optional[ApprovalInstance]:
    """Advance the approval flow for a given object.

    Supports both new and old interfaces:
    New: advance_flow(ticket, 'approved', user)
    Old: advance_flow(instance=approval_instance, action='approved', user=user)

    Args:
        obj_or_instance: The Django model instance (e.g., Ticket, Stage) or ApprovalInstance
        action: Action to take ('approved', 'rejected', 'resubmission', 'delegated', 'escalated')
        user: User performing the action
        comment: Optional comment for the action
        form_data: Optional form data for the step
        resubmission_steps: Optional list of new steps for resubmission
        delegate_to: Optional user to delegate the step to (required for 'delegated' action)
        instance: (Deprecated) ApprovalInstance for backward compatibility

    Returns:
        Next approval instance if workflow continues, None if complete

    Raises:
        ValueError: If no current approval found, action is invalid, or validation fails
        PermissionError: If user is not authorized to act on this step
    """
    # Validate required parameters
    if action is None:
        raise ValueError("action parameter is required")
    if user is None:
        raise ValueError("user parameter is required")

    # Handle backward compatibility with old keyword interface
    if instance is not None:
        # Check if instance is an ApprovalInstance or a business object
        if isinstance(instance, ApprovalInstance):
            # Old interface: advance_flow(instance=approval_instance, ...)
            return _advance_flow_internal(
                instance=instance,
                action=action,
                user=user,
                comment=comment,
                form_data=form_data,
                resubmission_steps=resubmission_steps,
                delegate_to=delegate_to,
            )
        else:
            # New interface: advance_flow(instance=business_object, ...) - treat as business object
            obj = instance
            current_instance = get_current_approval_for_object(obj)

            if not current_instance:
                logger.error(
                    "No current approval found for object - Object: %s (%s), User: %s",
                    obj.__class__.__name__,
                    obj.pk,
                    user.username,
                )
                raise ValueError(
                    f"No current approval found for {obj.__class__.__name__} with ID {obj.pk}"
                )

            return _advance_flow_internal(
                instance=current_instance,
                action=action,
                user=user,
                comment=comment,
                form_data=form_data,
                resubmission_steps=resubmission_steps,
                delegate_to=delegate_to,
            )

    # Validate that we have an object to work with
    if obj_or_instance is None:
        raise ValueError(
            "Either obj_or_instance or instance parameter must be provided"
        )

    # Check if first argument is ApprovalInstance (old positional interface)
    if isinstance(obj_or_instance, ApprovalInstance):
        # Old interface: advance_flow(approval_instance, ...)
        return _advance_flow_internal(
            instance=obj_or_instance,
            action=action,
            user=user,
            comment=comment,
            form_data=form_data,
            resubmission_steps=resubmission_steps,
            delegate_to=delegate_to,
        )

    # New interface: advance_flow(object, ...)
    obj = obj_or_instance
    current_instance = get_current_approval_for_object(obj)

    if not current_instance:
        logger.error(
            "No current approval found for object - Object: %s (%s), User: %s",
            obj.__class__.__name__,
            obj.pk,
            user.username,
        )
        raise ValueError(
            f"No current approval found for {obj.__class__.__name__} with ID {obj.pk}"
        )

    return _advance_flow_internal(
        instance=current_instance,
        action=action,
        user=user,
        comment=comment,
        form_data=form_data,
        resubmission_steps=resubmission_steps,
        delegate_to=delegate_to,
    )


def _advance_flow_internal(
    instance: ApprovalInstance,
    action: str,
    user: User,
    comment: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
    resubmission_steps: Optional[List[Dict[str, Any]]] = None,
    delegate_to: Optional[User] = None,
) -> Optional[ApprovalInstance]:
    """Internal function to advance the approval flow by delegating to the appropriate handler.

    Args:
        instance: The approval instance to act upon
        action: Action to take ('approved', 'rejected', 'resubmission', 'delegated', 'escalated')
        user: User performing the action
        comment: Optional comment for the action
        form_data: Optional form data for the step
        resubmission_steps: Optional list of new steps for resubmission
        delegate_to: Optional user to delegate the step to (required for 'delegated' action)

    Returns:
        Next approval instance if workflow continues, None if complete

    Raises:
        ValueError: If action is invalid or instance status is not pending
        PermissionError: If user is not authorized to act on this step
    """
    logger.info(
        "Advancing approval flow - Flow ID: %s, Step: %s, Action: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        action,
        user.username,
    )

    if instance.status not in [ApprovalStatus.PENDING, ApprovalStatus.CURRENT]:
        logger.warning(
            "Cannot advance flow - Step already processed - Flow ID: %s, Step: %s, Status: %s",
            instance.flow.id,
            instance.step_number,
            instance.status,
        )
        raise ValueError(
            f"Cannot act on step {instance.step_number} as it's already {instance.status}"
        )

    # Check user authorization
    if not _is_user_authorized_for_step(instance, user):
        logger.warning(
            "User not authorized for step - Flow ID: %s, Step: %s, User: %s, Assigned to: %s",
            instance.flow.id,
            instance.step_number,
            user.username,
            instance.assigned_to.username if instance.assigned_to else None,
        )
        raise PermissionError("You are not authorized to act on this step.")

    action_map = {
        "approved": _handle_approve,
        "rejected": _handle_reject,
        "resubmission": _handle_resubmission,
        "delegated": _handle_delegate,
        "escalated": _handle_escalate,
    }

    if action not in action_map:
        logger.error(
            "Invalid action provided - Action: %s, Valid actions: %s",
            action,
            list(action_map.keys()),
        )
        raise ValueError(f"Unsupported action: {action}")

    logger.debug(
        "Delegating to action handler - Flow ID: %s, Step: %s, Action: %s",
        instance.flow.id,
        instance.step_number,
        action,
    )

    result = action_map[action](
        instance=instance,
        user=user,
        comment=comment,
        form_data=form_data,
        resubmission_steps=resubmission_steps,
        delegate_to=delegate_to,
    )

    logger.info(
        "Flow advancement completed - Flow ID: %s, Step: %s, Action: %s, Next step: %s",
        instance.flow.id,
        instance.step_number,
        action,
        result.step_number if result else "None (workflow complete)",
    )

    return result


def _handle_approve(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Optional[ApprovalInstance]:
    """Approve the current step, optionally validate form data.

    Args:
        instance: The approval instance to approve
        user: User performing the approval
        comment: Optional comment for the approval
        form_data: Optional form data for validation
        **kwargs: Additional keyword arguments (unused)

    Returns:
        Next approval instance if workflow continues, None if complete

    Raises:
        ValueError: If form data is required but not provided
    """
    logger.debug(
        "Processing approval - Flow ID: %s, Step: %s, User: %s, Has form: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
        bool(instance.form),
    )

    # Call before_approve hook
    handler = get_handler_for_instance(instance)
    if hasattr(handler, "before_approve"):
        handler.before_approve(instance)

    # Check if form has schema/form_info field for validation
    if instance.form:
        # Get configurable schema field name (default: 'schema')
        schema_field = getattr(settings, "APPROVAL_FORM_SCHEMA_FIELD", "schema")
        form_schema = getattr(instance.form, schema_field, None)

        if form_schema:
            if not form_data:
                logger.error(
                    "Form data required but not provided - Flow ID: %s, Step: %s",
                    instance.flow.id,
                    instance.step_number,
                )
                raise ValueError("This step requires form_data.")
            logger.debug(
                "Form data validation passed - Flow ID: %s, Step: %s",
                instance.flow.id,
                instance.step_number,
            )

    # CURRENT status optimization: Mark current step as approved
    instance.status = ApprovalStatus.APPROVED
    instance.action_user = user
    instance.comment = comment or ""
    instance.form_data = form_data or {}
    instance.save()

    logger.info(
        "Step approved and saved - Flow ID: %s, Step: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
    )

    if instance.assigned_role and instance.role_selection_strategy:
        instance = _handle_role_based_approval_completion(instance)
    else:
        # Standard user-based approval flow
        instance = _advance_to_next_step(instance)
    if instance:
        # Get fresh handler instance for on_approve
        approval_handler = get_handler_for_instance(instance)
        approval_handler.on_approve(instance)
    return instance


def _handle_reject(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Reject the current step and clean up the rest of the flow.

    Args:
        instance: The approval instance to reject
        user: User performing the rejection
        comment: Optional comment for the rejection
        **kwargs: Additional keyword arguments (unused)
    """
    logger.info(
        "Processing rejection - Flow ID: %s, Step: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
    )

    # Call before_reject hook
    handler = get_handler_for_instance(instance)
    if hasattr(handler, "before_reject"):
        handler.before_reject(instance)

    instance.status = ApprovalStatus.REJECTED
    instance.action_user = user
    instance.comment = comment or ""
    instance.save()

    logger.info(
        "Step rejected and saved - Flow ID: %s, Step: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
    )

    remaining_steps = (
        ApprovalInstance.objects.select_related("assigned_to", "flow")
        .filter(
            flow=instance.flow,
            status__in=[ApprovalStatus.PENDING, ApprovalStatus.CURRENT],
        )
        .filter(
            Q(step_number__gt=instance.step_number)  # Future steps
            | (
                Q(step_number=instance.step_number) & ~Q(pk=instance.pk)
            )  # Same step, different instance
        )
    )

    remaining_count = remaining_steps.count()
    remaining_steps.delete()

    logger.info(
        "Cleaned up remaining steps - Flow ID: %s, Deleted steps: %s",
        instance.flow.id,
        remaining_count,
    )

    handler = get_handler_for_instance(instance)
    logger.debug(
        "Executing rejection handler - Flow ID: %s, Step: %s, Handler: %s",
        instance.flow.id,
        instance.step_number,
        handler.__class__.__name__,
    )
    handler.on_reject(instance)
    if hasattr(handler, "after_reject"):
        handler.after_reject(instance)

    return None


def _handle_resubmission(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    resubmission_steps: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> ApprovalInstance:
    """Request resubmission: cancel current flow & extend with new steps.

    Resubmission is used when the current approval step determines that additional
    review or corrections are needed before the workflow can continue. This function:

    1. Marks the current instance as NEEDS_RESUBMISSION
    2. Deletes any remaining pending steps in the workflow
    3. Uses extend_flow() to add new approval steps as specified in resubmission_steps
    4. Calls the on_resubmission handler for custom business logic
    5. Returns the first new step for the requester to continue processing

    The resubmission mechanism allows for dynamic workflow modification based on
    runtime decisions by reviewers. Common use cases include:
    - Adding additional reviewers (legal, security, compliance)
    - Requesting document revisions before continuing
    - Escalating to higher authorities
    - Parallel review processes

    Args:
        instance: The approval instance requesting resubmission. This instance
                 will be marked with NEEDS_RESUBMISSION status.
        user: User performing the resubmission request. Must have permission
              to act on the current step.
        comment: Optional comment explaining why resubmission is needed.
                This is stored with the instance and passed to handlers.
        resubmission_steps: List of new steps to add to the workflow. Each step
                           should contain 'step' number and either 'assigned_to' or
                           'assigned_role' with 'role_selection_strategy'. The developer
                           must provide explicit step numbers to maintain history properly.
        **kwargs: Additional keyword arguments (unused, reserved for future use)

    Returns:
        First new approval instance created for resubmission. This allows the
        caller to immediately continue processing or redirect to the new step.

    Raises:
        ValueError: If resubmission_steps is not provided or empty, or if step
                   numbers conflict with existing steps, or validation fails.

    Example:
        # Manager requests legal review before final approval
        legal_step = _handle_resubmission(
            instance=current_step,
            user=manager,
            comment="Legal review required for compliance",
            resubmission_steps=[
                {"step": 3, "assigned_to": legal_reviewer},  # Explicit step number
                {"step": 4, "assigned_to": director}         # Final approval
            ]
        )

        # The current_step is now NEEDS_RESUBMISSION
        # legal_step is the new first step to be processed

        # Role-based resubmission example
        role_based_step = _handle_resubmission(
            instance=current_step,
            user=manager,
            comment="Need consensus from all legal team",
            resubmission_steps=[
                {
                    "step": 5,
                    "assigned_role": legal_role,
                    "role_selection_strategy": RoleSelectionStrategy.CONSENSUS
                }
            ]
        )
    """
    logger.info(
        "Processing resubmission - Flow ID: %s, Step: %s, User: %s, New steps: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
        len(resubmission_steps) if resubmission_steps else 0,
    )

    # Call before_resubmission hook
    handler = get_handler_for_instance(instance)
    if hasattr(handler, "before_resubmission"):
        handler.before_resubmission(instance)

    if not resubmission_steps:
        logger.error(
            "Resubmission steps not provided - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )
        raise ValueError("resubmission_steps must be provided.")

    instance.status = ApprovalStatus.NEEDS_RESUBMISSION
    instance.action_user = user
    instance.comment = comment or ""
    instance.save()

    logger.info(
        "Resubmission status saved - Flow ID: %s, Step: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
    )

    # Delete remaining steps in this flow (including CURRENT status)
    remaining_steps = ApprovalInstance.objects.select_related(
        "assigned_to", "flow"
    ).filter(
        flow=instance.flow,
        step_number__gt=instance.step_number,
        status__in=[ApprovalStatus.PENDING, ApprovalStatus.CURRENT],
    )

    remaining_count = remaining_steps.count()
    remaining_steps.delete()

    logger.info(
        "Cleaned up remaining steps for resubmission - Flow ID: %s, Deleted steps: %s",
        instance.flow.id,
        remaining_count,
    )

    # Use extend_flow to add new steps with proper validation and role support
    logger.debug(
        "Extending flow with resubmission steps - Flow ID: %s, Steps: %s",
        instance.flow.id,
        len(resubmission_steps),
    )

    try:
        created_instances = extend_flow(instance.flow, resubmission_steps)
    except ValueError as e:
        logger.error(
            "Failed to extend flow for resubmission - Flow ID: %s, Error: %s",
            instance.flow.id,
            str(e),
        )
        raise ValueError(f"Resubmission failed: {str(e)}")

    logger.info(
        "Extended flow with resubmission steps - Flow ID: %s, New steps: %s",
        instance.flow.id,
        [inst.step_number for inst in created_instances],
    )

    handler = get_handler_for_instance(instance)
    logger.debug(
        "Executing resubmission handler - Flow ID: %s, Step: %s, Handler: %s",
        instance.flow.id,
        instance.step_number,
        handler.__class__.__name__,
    )
    handler.on_resubmission(instance)
    if hasattr(handler, "after_resubmission"):
        handler.after_resubmission(instance)

    # Return the first created instance (which should be CURRENT)
    first_new_step = created_instances[0] if created_instances else None

    if not first_new_step:
        logger.error(
            "No steps created during resubmission - Flow ID: %s",
            instance.flow.id,
        )
        raise ValueError("Failed to create resubmission steps")

    logger.info(
        "Resubmission completed - Flow ID: %s, First new step: %s",
        instance.flow.id,
        first_new_step.step_number,
    )

    return first_new_step


def _handle_delegate(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    delegate_to: Optional[User] = None,
    **kwargs: Any,
) -> ApprovalInstance:
    """Delegate the current step to another user by creating a new step record."""
    logger.info(
        "Processing delegation - Flow ID: %s, Step: %s, User: %s, Delegate to: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
        delegate_to.username if delegate_to else None,
    )

    # Call before_delegate hook
    handler = get_handler_for_instance(instance)
    if hasattr(handler, "before_delegate"):
        handler.before_delegate(instance)

    if not delegate_to:
        raise ValueError("delegate_to user must be provided.")

    instance.status = ApprovalStatus.DELEGATED
    instance.action_user = user
    instance.comment = comment or ""
    instance.save()

    delegated_step = ApprovalInstance.objects.create(
        flow=instance.flow,
        step_number=instance.step_number,
        assigned_to=delegate_to,
        status=ApprovalStatus.CURRENT,
        form=instance.form,
        sla_duration=instance.sla_duration,
        allow_higher_level=instance.allow_higher_level,
        extra_fields=instance.extra_fields,
    )

    handler = get_handler_for_instance(instance)
    handler.on_delegate(instance)
    if hasattr(handler, "after_delegate"):
        handler.after_delegate(instance)

    return delegated_step


def _handle_escalate(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    **kwargs: Any,
) -> ApprovalInstance:
    """Escalate the current step to a head manager by creating a new step record."""
    logger.info(
        "Processing escalation - Flow ID: %s, Step: %s, User: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
    )

    # Call before_escalate hook
    handler = get_handler_for_instance(instance)
    if hasattr(handler, "before_escalate"):
        handler.before_escalate(instance)

    head_manager_field = getattr(settings, "APPROVAL_HEAD_MANAGER_FIELD", None)
    escalation_user = None

    # Try to get head manager from direct field first
    if head_manager_field:
        escalation_user = getattr(user, head_manager_field, None)

    # Fallback to role hierarchy if no direct head manager found
    if not escalation_user:
        role_field = getattr(settings, "APPROVAL_ROLE_FIELD", "role")
        current_role = getattr(user, role_field, None)

        if current_role:
            parent_role = (
                current_role.parent if hasattr(current_role, "parent") else None
            )
            if parent_role:
                escalation_user = User.objects.filter(
                    **{role_field: parent_role}
                ).first()

    if not escalation_user:
        raise ValueError("No head manager or higher role user found for escalation.")

    instance.status = ApprovalStatus.ESCALATED
    instance.action_user = user
    instance.comment = comment or ""
    instance.save()

    escalated_step = ApprovalInstance.objects.create(
        flow=instance.flow,
        step_number=instance.step_number,
        assigned_to=escalation_user,
        status=ApprovalStatus.CURRENT,
        form=instance.form,
        sla_duration=instance.sla_duration,
        allow_higher_level=instance.allow_higher_level,
        extra_fields=instance.extra_fields,
    )

    handler = get_handler_for_instance(instance)
    handler.on_escalate(instance)
    if hasattr(handler, "after_escalate"):
        handler.after_escalate(instance)

    return escalated_step


def _validate_step_data(
    steps: List[Dict[str, Any]], existing_step_numbers: Optional[set] = None
) -> None:
    """Validate step data for both start_flow and extend_flow.

    Args:
        steps: List of step dictionaries to validate
        existing_step_numbers: Set of existing step numbers (for extend_flow conflict checking)

    Raises:
        ValueError: If validation fails
    """
    dynamic_form_model = get_dynamic_form_model()

    # PERFORMANCE: Bulk fetch all forms at once to avoid N+1 queries
    form_ids = [
        step["form"]
        for step in steps
        if "form" in step and isinstance(step["form"], int)
    ]
    forms_map = {}
    if form_ids and dynamic_form_model:
        forms_map = {
            f.pk: f for f in dynamic_form_model.objects.filter(pk__in=form_ids)
        }
        logger.debug(
            "Bulk fetched %s forms in single query - IDs: %s",
            len(forms_map),
            form_ids,
        )

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            logger.error(
                "Invalid step at index %s - Expected dict, got: %s",
                i,
                type(step).__name__,
            )
            raise ValueError(
                f"Step at index {i} must be a dict, got {type(step).__name__}"
            )
        if "step" not in step:
            logger.error("Missing 'step' key in step at index %s", i)
            raise ValueError(f"Missing 'step' key in step at index {i}")
        # Validate step number
        if not isinstance(step["step"], int) or step["step"] <= 0:
            logger.error("Invalid step number at index %s - Value: %s", i, step["step"])
            raise ValueError(f"'step' must be a positive integer at index {i}")

        # Check for step number conflicts (extend_flow only)
        if existing_step_numbers is not None and step["step"] in existing_step_numbers:
            logger.error(
                "Step number conflict at index %s - Step %s already exists",
                i,
                step["step"],
            )
            raise ValueError(
                f"Step number {step['step']} at index {i} already exists in the flow"
            )

        # Validate assignment - must have either assigned_to OR assigned_role
        has_assigned_to = "assigned_to" in step
        has_assigned_role = "assigned_role" in step

        if not has_assigned_to and not has_assigned_role:
            logger.error(
                "Missing assignment in step at index %s - Must have either 'assigned_to' or 'assigned_role'",
                i,
            )
            raise ValueError(
                f"Step at index {i} must have either 'assigned_to' or 'assigned_role'"
            )

        if has_assigned_to and has_assigned_role:
            logger.error(
                "Conflicting assignment in step at index %s - Cannot have both 'assigned_to' and 'assigned_role'",
                i,
            )
            raise ValueError(
                f"Step at index {i} cannot have both 'assigned_to' and 'assigned_role'"
            )

        # Validate user-based assignment
        if has_assigned_to:
            if step["assigned_to"] is not None and not isinstance(
                step["assigned_to"], User
            ):
                logger.error(
                    "Invalid assigned_to at index %s - Expected User, got: %s",
                    i,
                    type(step["assigned_to"]).__name__,
                )
                raise ValueError(f"'assigned_to' must be a User or None at index {i}")

        # Validate role-based assignment
        if has_assigned_role:
            if "role_selection_strategy" not in step:
                logger.error(
                    "Missing 'role_selection_strategy' for role-based step at index %s",
                    i,
                )
                raise ValueError(
                    f"'role_selection_strategy' is required when using 'assigned_role' at index {i}"
                )

            if step["assigned_role"] is None:
                logger.error("Invalid assigned_role at index %s - Cannot be None", i)
                raise ValueError(f"'assigned_role' cannot be None at index {i}")

            # Validate role_selection_strategy
            from .choices import RoleSelectionStrategy

            valid_strategies = [choice[0] for choice in RoleSelectionStrategy.choices]
            if step["role_selection_strategy"] not in valid_strategies:
                logger.error(
                    "Invalid role_selection_strategy at index %s - Expected one of %s, got: %s",
                    i,
                    valid_strategies,
                    step["role_selection_strategy"],
                )
                raise ValueError(
                    f"'role_selection_strategy' must be one of {valid_strategies} at index {i}"
                )

        # Validate form if used
        if "form" in step:
            if not dynamic_form_model:
                logger.error(
                    "Form provided but no dynamic form model configured - Step index: %s",
                    i,
                )
                raise ValueError(
                    f"'form' provided in step {i}, but no APPROVAL_DYNAMIC_FORM_MODEL is configured."
                )
            form_obj = step["form"]
            if isinstance(form_obj, int):
                # Resolve from pre-fetched forms_map (PERFORMANCE: avoid additional query)
                if form_obj in forms_map:
                    logger.debug(
                        "Resolving form from cache - Step: %s, Form ID: %s", i, form_obj
                    )
                    step["form"] = forms_map[form_obj]
                else:
                    logger.error(
                        "Form ID not found - Step: %s, Form ID: %s", i, form_obj
                    )
                    raise ValueError(f"Form with ID {form_obj} not found at step {i}")
            elif not isinstance(form_obj, dynamic_form_model):
                logger.error(
                    "Invalid form object at step %s - Expected: %s, Got: %s",
                    i,
                    dynamic_form_model.__name__,
                    type(form_obj).__name__,
                )
                raise ValueError(
                    f"'form' in step {i} must be a {dynamic_form_model.__name__} instance or ID."
                )

        # Log step validation info
        if "assigned_to" in step:
            assigned_info = (
                step["assigned_to"].username if step["assigned_to"] else None
            )
        else:
            assigned_info = f"role:{getattr(step['assigned_role'], 'name', str(step['assigned_role']))}"

        logger.debug(
            "Step validated - Index: %s, Step number: %s, Assigned to: %s, Has form: %s",
            i,
            step["step"],
            assigned_info,
            "form" in step,
        )


def _create_approval_instances(
    flow: ApprovalFlow,
    sorted_steps: List[Dict[str, Any]],
    make_first_current: bool = True,
    has_existing_current: bool = False,
) -> List[ApprovalInstance]:
    """Create approval instances for both start_flow and extend_flow.

    PERFORMANCE OPTIMIZED: Uses bulk_create to minimize database queries.

    Args:
        flow: The approval flow to add instances to
        sorted_steps: List of step dictionaries sorted by step number
        make_first_current: Whether to make the first step CURRENT (start_flow behavior)
        has_existing_current: Whether there's already a CURRENT step (extend_flow behavior)

    Returns:
        List of created ApprovalInstance objects
    """
    # PERFORMANCE: Collect instances to bulk create
    instances_to_bulk_create = []
    first_current_step_data = None
    first_current_is_role_based = False
    created_instances = []

    for i, step_data in enumerate(sorted_steps):
        # Determine if this step should be CURRENT
        if make_first_current:
            # start_flow behavior: first step is CURRENT, rest are PENDING
            should_be_current = i == 0
        else:
            # extend_flow behavior: first step is CURRENT only if no existing CURRENT step
            should_be_current = not has_existing_current and i == 0
            if should_be_current:
                has_existing_current = (
                    True  # Prevent subsequent steps from being current
                )

        # Check if this is a role-based step
        if "assigned_role" in step_data:
            # Role-based step: Create template instance
            role_content_type = _get_cached_content_type(
                step_data["assigned_role"].__class__
            )
            template_status = (
                ApprovalStatus.CURRENT if should_be_current else ApprovalStatus.PENDING
            )

            template_instance = ApprovalInstance(
                flow=flow,
                step_number=step_data["step"],
                status=template_status,
                assigned_to=None,  # No direct user assignment for role-based steps
                assigned_role_content_type=role_content_type,
                assigned_role_object_id=str(step_data["assigned_role"].pk),
                role_selection_strategy=step_data["role_selection_strategy"],
                form=step_data.get("form"),
                sla_duration=step_data.get("sla_duration"),
                allow_higher_level=step_data.get("allow_higher_level", False),
                extra_fields=step_data.get("extra_fields"),
            )
            instances_to_bulk_create.append(template_instance)

            # Track if first current step is role-based for later activation
            if should_be_current and first_current_step_data is None:
                first_current_step_data = step_data
                first_current_is_role_based = True

        else:
            # User-based step: Create instance directly
            status = (
                ApprovalStatus.CURRENT if should_be_current else ApprovalStatus.PENDING
            )
            instance = ApprovalInstance(
                flow=flow,
                step_number=step_data["step"],
                status=status,
                assigned_to=step_data["assigned_to"],
                form=step_data.get("form"),
                sla_duration=step_data.get("sla_duration"),
                allow_higher_level=step_data.get("allow_higher_level", False),
                extra_fields=step_data.get("extra_fields"),
            )
            instances_to_bulk_create.append(instance)

    # PERFORMANCE: Bulk create all instances in a single query
    if instances_to_bulk_create:
        created_instances = ApprovalInstance.objects.bulk_create(
            instances_to_bulk_create
        )
        logger.debug(
            "Bulk created %s approval instances - Flow ID: %s",
            len(created_instances),
            flow.id,
        )

    # If the first current step is role-based, activate it now
    if first_current_is_role_based and created_instances:
        # Find the first role-based template instance that was created
        first_role_template = created_instances[0]
        first_role_instance = _activate_role_based_step(first_role_template)
        # Replace the template with the activated instance in the return list
        created_instances[0] = first_role_instance

    return created_instances


def get_dynamic_form_model() -> Optional[Type[Any]]:
    """Resolve the optional DynamicForm model from settings.

    Returns:
        Model class if configured in settings, None otherwise

    Raises:
        LookupError: If configured model path is invalid
        ValueError: If configured model path format is invalid
    """
    model_path = getattr(settings, "APPROVAL_DYNAMIC_FORM_MODEL", None)
    logger.debug("Resolving dynamic form model - Path: %s", model_path)

    if not model_path:
        logger.debug("No dynamic form model configured")
        return None

    try:
        model = apps.get_model(model_path)
        logger.debug("Dynamic form model resolved - Model: %s", model.__name__)
        return model
    except (LookupError, ValueError) as e:
        logger.warning(
            "Failed to resolve dynamic form model - Path: %s, Error: %s",
            model_path,
            str(e),
        )
        return None


def start_flow(obj: Model, steps: List[Dict[str, Any]]) -> ApprovalFlow:
    """Start a new ApprovalFlow for a given object.

    Args:
        obj: The Django model instance this flow is for
        steps: List of step dictionaries with keys:
               - 'step': Step number (positive integer)
               - 'assigned_to': User instance (for user-based approval) OR
               - 'assigned_role': Role instance (for role-based approval)
               - 'role_selection_strategy': Required if assigned_role is used (ANYONE, CONSENSUS, ROUND_ROBIN)
               - 'form': Optional form instance or ID
               - 'sla_duration': Optional duration for SLA tracking (e.g., timedelta(days=2))
               - 'allow_higher_level': Optional boolean to allow higher role users to approve (default: False)
               - 'extra_fields': Optional dictionary of additional custom fields

    Returns:
        ApprovalFlow instance with created approval steps

    Raises:
        ValueError: If input validation fails
        TypeError: If step data types are incorrect
    """
    logger.info(
        "Starting new approval flow - Object: %s (%s), Steps count: %s",
        obj.__class__.__name__,
        obj.pk,
        len(steps),
    )

    if not isinstance(steps, list):
        logger.error(
            "Invalid steps parameter - Expected list, got: %s", type(steps).__name__
        )
        raise ValueError("steps must be a list of step dictionaries")

    logger.debug(
        "Validating flow steps - Count: %s, Has form model: %s",
        len(steps),
        bool(get_dynamic_form_model()),
    )

    # Use shared validation function
    _validate_step_data(steps)

    content_type = _get_cached_content_type(obj.__class__)
    flow = ApprovalFlow.objects.create(content_type=content_type, object_id=str(obj.pk))

    logger.info(
        "Created approval flow - Flow ID: %s, Object: %s (%s)",
        flow.id,
        obj.__class__.__name__,
        obj.pk,
    )

    # Sort steps and use shared creation function
    sorted_steps = sorted(steps, key=lambda x: x["step"])
    created_instances = _create_approval_instances(
        flow, sorted_steps, make_first_current=True
    )

    logger.info(
        "Created approval instances - Flow ID: %s, Instances: %s",
        flow.id,
        [f"Step {inst.step_number}" for inst in created_instances],
    )

    return flow


def extend_flow(
    flow: ApprovalFlow, steps: List[Dict[str, Any]]
) -> List[ApprovalInstance]:
    """Extend an existing ApprovalFlow with additional steps.

    This function allows you to add more steps to an existing workflow,
    useful for resubmission scenarios or dynamic workflow extension.

    Args:
        flow: The existing ApprovalFlow instance to extend
        steps: List of step dictionaries with keys:
               - 'step': Step number (positive integer)
               - 'assigned_to': User instance (for user-based approval) OR
               - 'assigned_role': Role instance (for role-based approval)
               - 'role_selection_strategy': Required if assigned_role is used (ANYONE, CONSENSUS, ROUND_ROBIN)
               - 'form': Optional form instance or ID
               - 'sla_duration': Optional duration for SLA tracking (e.g., timedelta(days=2))
               - 'allow_higher_level': Optional boolean to allow higher role users to approve (default: False)
               - 'extra_fields': Optional dictionary of additional custom fields

    Returns:
        List of created ApprovalInstance objects

    Raises:
        ValueError: If input validation fails or step numbers conflict with existing steps
        TypeError: If step data types are incorrect
    """
    logger.info(
        "Extending approval flow - Flow ID: %s, New steps count: %s",
        flow.id,
        len(steps),
    )

    if not isinstance(steps, list):
        logger.error(
            "Invalid steps parameter - Expected list, got: %s", type(steps).__name__
        )
        raise ValueError("steps must be a list of step dictionaries")

    logger.debug(
        "Validating extension steps - Count: %s, Has form model: %s",
        len(steps),
        bool(get_dynamic_form_model()),
    )

    # Get existing step numbers to prevent conflicts (optimized query)
    existing_step_numbers = set(
        ApprovalInstance.objects.filter(flow=flow).values_list("step_number", flat=True)
    )

    # Use shared validation function with conflict checking
    _validate_step_data(steps, existing_step_numbers)

    # Sort steps by step number for consistent creation
    sorted_steps = sorted(steps, key=lambda x: x["step"])

    # Determine if we need to set first new step as CURRENT
    # (if there are no existing CURRENT steps) - optimized exists() query
    has_current_step = ApprovalInstance.objects.filter(
        flow=flow, status=ApprovalStatus.CURRENT
    ).exists()

    # Use shared creation function
    created_instances = _create_approval_instances(
        flow,
        sorted_steps,
        make_first_current=False,
        has_existing_current=has_current_step,
    )

    logger.info(
        "Extended approval flow - Flow ID: %s, New instances: %s",
        flow.id,
        [f"Step {inst.step_number}" for inst in created_instances],
    )

    return created_instances


def _handle_role_based_approval_completion(
    instance: ApprovalInstance,
) -> Optional[ApprovalInstance]:
    """Handle completion logic for role-based approvals based on strategy.

    Args:
        instance: The just-approved role-based approval instance

    Returns:
        Next approval instance if workflow continues, None if complete
    """
    logger.debug(
        "Processing role-based approval completion - Flow ID: %s, Step: %s, Strategy: %s",
        instance.flow.id,
        instance.step_number,
        instance.role_selection_strategy,
    )

    if instance.role_selection_strategy == RoleSelectionStrategy.ANYONE:
        # For "anyone" strategy, first approval completes the step
        # Delete all other CURRENT instances for this step
        other_current_instances = (
            ApprovalInstance.objects.select_related("assigned_to", "flow")
            .filter(
                flow=instance.flow,
                step_number=instance.step_number,
                status=ApprovalStatus.CURRENT,
                assigned_role_content_type=instance.assigned_role_content_type,
                assigned_role_object_id=instance.assigned_role_object_id,
            )
            .exclude(pk=instance.pk)
        )

        cancelled_count = other_current_instances.count()
        other_current_instances.delete()

        logger.info(
            "ANYONE strategy: Deleted %s other current instances - Flow ID: %s, Step: %s",
            cancelled_count,
            instance.flow.id,
            instance.step_number,
        )

        return _advance_to_next_step(instance)

    elif instance.role_selection_strategy == RoleSelectionStrategy.CONSENSUS:
        # For "consensus" strategy, check if all instances for this step are approved
        remaining_current_instances = (
            ApprovalInstance.objects.select_related("assigned_to", "flow")
            .filter(
                flow=instance.flow,
                step_number=instance.step_number,
                status=ApprovalStatus.CURRENT,
                assigned_role_content_type=instance.assigned_role_content_type,
                assigned_role_object_id=instance.assigned_role_object_id,
            )
            .exists()
        )

        if remaining_current_instances:
            logger.info(
                "CONSENSUS strategy: Waiting for more approvals - Flow ID: %s, Step: %s",
                instance.flow.id,
                instance.step_number,
            )
            return None  # Stay on current step, wait for more approvals
        else:
            logger.info(
                "CONSENSUS strategy: All approvals received - Flow ID: %s, Step: %s",
                instance.flow.id,
                instance.step_number,
            )
            return _advance_to_next_step(instance)

    elif instance.role_selection_strategy == RoleSelectionStrategy.ROUND_ROBIN:
        # For "round_robin" strategy, single approval completes the step
        return _advance_to_next_step(instance)

    else:
        logger.error(
            "Unknown role selection strategy - Flow ID: %s, Step: %s, Strategy: %s",
            instance.flow.id,
            instance.step_number,
            instance.role_selection_strategy,
        )
        raise ValueError(
            f"Unknown role selection strategy: {instance.role_selection_strategy}"
        )


def _advance_to_next_step(instance: ApprovalInstance) -> Optional[ApprovalInstance]:
    """Advance to the next step in the workflow.

    Args:
        instance: The current completed approval instance

    Returns:
        Next approval instance if workflow continues, None if complete
    """
    # Find next step by ordering step numbers (safer than assuming step+1)
    next_step = (
        ApprovalInstance.objects.select_related("assigned_to", "flow")
        .filter(
            flow=instance.flow,
            step_number__gt=instance.step_number,
            status=ApprovalStatus.PENDING,
        )
        .order_by("step_number")
        .first()
    )

    if next_step:
        # For role-based approvals, we might need to create multiple instances
        if next_step.assigned_role and next_step.role_selection_strategy:
            return _activate_role_based_step(next_step)
        else:
            # Standard user-based approval
            next_step.status = ApprovalStatus.CURRENT
            next_step.save()

            logger.info(
                "Next step found and set as CURRENT - Flow ID: %s, Current step: %s, Next step: %s",
                instance.flow.id,
                instance.step_number,
                next_step.step_number,
            )
            return next_step

    logger.info(
        "Final approval reached - Flow ID: %s, Step: %s, Executing final approval handler",
        instance.flow.id,
        instance.step_number,
    )
    handler = get_handler_for_instance(instance)
    handler.on_final_approve(instance)
    if hasattr(handler, "after_approve"):
        handler.after_approve(instance)
    return None


def _activate_role_based_step(step_template: ApprovalInstance) -> ApprovalInstance:
    """Activate a role-based step by creating instances for all required users.

    PERFORMANCE OPTIMIZED: Uses bulk_create to minimize database queries.

    Args:
        step_template: The template step with role assignment

    Returns:
        First created approval instance (for consistency with API)
    """
    from .utils import get_users_for_role, get_user_with_least_assignments

    logger.info(
        "Activating role-based step - Flow ID: %s, Step: %s, Strategy: %s",
        step_template.flow.id,
        step_template.step_number,
        step_template.role_selection_strategy,
    )

    # Get users for the assigned role
    role_users = get_users_for_role(step_template.assigned_role)

    if not role_users:
        logger.error(
            "No users found for role - Flow ID: %s, Step: %s, Role: %s",
            step_template.flow.id,
            step_template.step_number,
            step_template.assigned_role,
        )
        raise ValueError(f"No users found for role: {step_template.assigned_role}")

    # PERFORMANCE: Collect instances to bulk create
    instances_to_create = []

    if step_template.role_selection_strategy == RoleSelectionStrategy.ANYONE:
        # Create approval instances for all users with this role, all CURRENT
        for user in role_users:
            instances_to_create.append(
                ApprovalInstance(
                    flow=step_template.flow,
                    step_number=step_template.step_number,
                    assigned_to=user,
                    assigned_role_content_type=step_template.assigned_role_content_type,
                    assigned_role_object_id=step_template.assigned_role_object_id,
                    role_selection_strategy=step_template.role_selection_strategy,
                    status=ApprovalStatus.CURRENT,
                    form=step_template.form,
                    sla_duration=step_template.sla_duration,
                    allow_higher_level=step_template.allow_higher_level,
                    extra_fields=step_template.extra_fields,
                )
            )

    elif step_template.role_selection_strategy == RoleSelectionStrategy.CONSENSUS:
        # Create approval instances for all users with this role, all CURRENT
        for user in role_users:
            instances_to_create.append(
                ApprovalInstance(
                    flow=step_template.flow,
                    step_number=step_template.step_number,
                    assigned_to=user,
                    assigned_role_content_type=step_template.assigned_role_content_type,
                    assigned_role_object_id=step_template.assigned_role_object_id,
                    role_selection_strategy=step_template.role_selection_strategy,
                    status=ApprovalStatus.CURRENT,
                    form=step_template.form,
                    sla_duration=step_template.sla_duration,
                    allow_higher_level=step_template.allow_higher_level,
                    extra_fields=step_template.extra_fields,
                )
            )

    elif step_template.role_selection_strategy == RoleSelectionStrategy.ROUND_ROBIN:
        # Find user with least current assignments
        selected_user = get_user_with_least_assignments(role_users)

        instances_to_create.append(
            ApprovalInstance(
                flow=step_template.flow,
                step_number=step_template.step_number,
                assigned_to=selected_user,
                assigned_role_content_type=step_template.assigned_role_content_type,
                assigned_role_object_id=step_template.assigned_role_object_id,
                role_selection_strategy=step_template.role_selection_strategy,
                status=ApprovalStatus.CURRENT,
                form=step_template.form,
                sla_duration=step_template.sla_duration,
                allow_higher_level=step_template.allow_higher_level,
                extra_fields=step_template.extra_fields,
            )
        )

    # PERFORMANCE: Bulk create all instances in a single query
    created_instances = ApprovalInstance.objects.bulk_create(instances_to_create)

    # Delete the template step
    step_template.delete()

    logger.info(
        "Created %s approval instances for role-based step - Flow ID: %s, Step: %s",
        len(created_instances),
        step_template.flow.id,
        step_template.step_number,
    )

    return created_instances[0] if created_instances else None
