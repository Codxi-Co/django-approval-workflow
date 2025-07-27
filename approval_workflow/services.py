"""Approval flow orchestration services."""

import logging
from typing import Any, Dict, List, Optional, Type

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from .choices import ApprovalStatus
from .handlers import get_handler_for_instance
from .models import ApprovalFlow, ApprovalInstance

logger = logging.getLogger(__name__)
User = get_user_model()


def advance_flow(
    instance: ApprovalInstance,
    action: str,
    user: User,
    comment: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
    resubmission_steps: Optional[List[Dict[str, Any]]] = None,
) -> Optional[ApprovalInstance]:
    """Advance the approval flow by delegating to the appropriate handler.
    
    Args:
        instance: The approval instance to act upon
        action: Action to take ('approved', 'rejected', 'resubmission')
        user: User performing the action
        comment: Optional comment for the action
        form_data: Optional form data for the step
        resubmission_steps: Optional list of new steps for resubmission
        
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
    
    if instance.status != ApprovalStatus.PENDING:
        logger.warning(
            "Cannot advance flow - Step already processed - Flow ID: %s, Step: %s, Status: %s",
            instance.flow.id,
            instance.step_number,
            instance.status,
        )
        raise ValueError(
            f"Cannot act on step {instance.step_number} as it's already {instance.status}"
        )

    if instance.assigned_to and instance.assigned_to != user:
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
    }

    if action not in action_map:
        logger.error("Invalid action provided - Action: %s, Valid actions: %s", action, list(action_map.keys()))
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
    
    if instance.form and instance.form.schema:
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

    handler = get_handler_for_instance(instance)
    logger.debug(
        "Executing approval handler - Flow ID: %s, Step: %s, Handler: %s",
        instance.flow.id,
        instance.step_number,
        handler.__class__.__name__,
    )
    handler.on_approve(instance)

    next_step = ApprovalInstance.objects.filter(
        flow=instance.flow, step_number=instance.step_number + 1
    ).first()

    if next_step:
        logger.info(
            "Next step found - Flow ID: %s, Current step: %s, Next step: %s",
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
    handler.on_final_approve(instance)
    return None


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

    # Delete remaining steps in flow
    remaining_steps = ApprovalInstance.objects.filter(
        flow=instance.flow,
        step_number__gt=instance.step_number,
        status=ApprovalStatus.PENDING,
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

    return None


def _handle_resubmission(
    instance: ApprovalInstance,
    user: User,
    comment: Optional[str] = None,
    resubmission_steps: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> ApprovalInstance:
    """Request resubmission: cancel current flow & append a new set of steps.
    
    Args:
        instance: The approval instance requesting resubmission
        user: User performing the resubmission request
        comment: Optional comment for the resubmission
        resubmission_steps: List of new steps to add to the workflow
        **kwargs: Additional keyword arguments (unused)
        
    Returns:
        First new approval instance created for resubmission
        
    Raises:
        ValueError: If resubmission_steps is not provided
    """
    logger.info(
        "Processing resubmission - Flow ID: %s, Step: %s, User: %s, New steps: %s",
        instance.flow.id,
        instance.step_number,
        user.username,
        len(resubmission_steps) if resubmission_steps else 0,
    )
    
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

    # Delete remaining steps in this flow
    remaining_steps = ApprovalInstance.objects.filter(
        flow=instance.flow,
        step_number__gt=instance.step_number,
        status=ApprovalStatus.PENDING,
    )
    
    remaining_count = remaining_steps.count()
    remaining_steps.delete()
    
    logger.info(
        "Cleaned up remaining steps for resubmission - Flow ID: %s, Deleted steps: %s",
        instance.flow.id,
        remaining_count,
    )

    # Create a new set of steps with step_number continuing from last
    last_step = (
        ApprovalInstance.objects.filter(flow=instance.flow)
        .order_by("-step_number")
        .first()
    )
    next_step_number = last_step.step_number + 1 if last_step else 1
    
    logger.debug(
        "Creating new resubmission steps - Flow ID: %s, Starting step: %s, Count: %s",
        instance.flow.id,
        next_step_number,
        len(resubmission_steps),
    )

    created_steps = []
    for i, step in enumerate(resubmission_steps):
        new_step = ApprovalInstance.objects.create(
            flow=instance.flow,
            step_number=next_step_number + i,
            assigned_to=step["assigned_to"],
            status=ApprovalStatus.PENDING,
            form=step.get("form"),
        )
        created_steps.append(new_step)
        
    logger.info(
        "Created resubmission steps - Flow ID: %s, Steps: %s",
        instance.flow.id,
        [step.step_number for step in created_steps],
    )

    handler = get_handler_for_instance(instance)
    logger.debug(
        "Executing resubmission handler - Flow ID: %s, Step: %s, Handler: %s",
        instance.flow.id,
        instance.step_number,
        handler.__class__.__name__,
    )
    handler.on_resubmission(instance)

    first_new_step = ApprovalInstance.objects.get(
        flow=instance.flow, step_number=next_step_number
    )
    
    logger.info(
        "Resubmission completed - Flow ID: %s, First new step: %s",
        instance.flow.id,
        first_new_step.step_number,
    )
    
    return first_new_step


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
        logger.warning("Failed to resolve dynamic form model - Path: %s, Error: %s", model_path, str(e))
        return None


def start_flow(obj: Model, steps: List[Dict[str, Any]]) -> ApprovalFlow:
    """Start a new ApprovalFlow for a given object.

    Args:
        obj: The Django model instance this flow is for
        steps: List of step dictionaries with keys:
               - 'step': Step number (positive integer)
               - 'assigned_to': User instance or None
               - 'form': Optional form instance or ID
               
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
        logger.error("Invalid steps parameter - Expected list, got: %s", type(steps).__name__)
        raise ValueError("steps must be a list of step dictionaries")

    dynamic_form_model = get_dynamic_form_model()
    
    logger.debug("Validating flow steps - Count: %s, Has form model: %s", len(steps), bool(dynamic_form_model))

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            logger.error("Invalid step at index %s - Expected dict, got: %s", i, type(step).__name__)
            raise ValueError(
                f"Step at index {i} must be a dict, got {type(step).__name__}"
            )
        if "step" not in step:
            logger.error("Missing 'step' key in step at index %s", i)
            raise ValueError(f"Missing 'step' key in step at index {i}")
        if "assigned_to" not in step:
            logger.error("Missing 'assigned_to' key in step at index %s", i)
            raise ValueError(f"Missing 'assigned_to' key in step at index {i}")
        if not isinstance(step["step"], int) or step["step"] <= 0:
            logger.error("Invalid step number at index %s - Value: %s", i, step["step"])
            raise ValueError(f"'step' must be a positive integer at index {i}")
        if step["assigned_to"] is not None and not isinstance(
            step["assigned_to"], User
        ):
            logger.error(
                "Invalid assigned_to at index %s - Expected User, got: %s", 
                i, 
                type(step["assigned_to"]).__name__
            )
            raise ValueError(f"'assigned_to' must be a User or None at index {i}")

        # Validate form if used
        if "form" in step:
            if not dynamic_form_model:
                logger.error("Form provided but no dynamic form model configured - Step index: %s", i)
                raise ValueError(
                    f"'form' provided in step {i}, but no APPROVAL_DYNAMIC_FORM_MODEL is configured."
                )
            form_obj = step["form"]
            if isinstance(form_obj, int):
                # Resolve by ID
                if hasattr(dynamic_form_model, 'objects'):
                    logger.debug("Resolving form by ID - Step: %s, Form ID: %s", i, form_obj)
                    step["form"] = dynamic_form_model.objects.get(pk=form_obj)
                else:
                    logger.error("Dynamic form model has no objects manager - Step: %s", i)
                    raise ValueError(f"Dynamic form model at step {i} has no objects manager")
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
                
        logger.debug(
            "Step validated - Index: %s, Step number: %s, Assigned to: %s, Has form: %s",
            i,
            step["step"],
            step["assigned_to"].username if step["assigned_to"] else None,
            "form" in step,
        )

    content_type = ContentType.objects.get_for_model(obj.__class__)
    flow = ApprovalFlow.objects.create(content_type=content_type, object_id=str(obj.pk))
    
    logger.info("Created approval flow - Flow ID: %s, Object: %s (%s)", flow.id, obj.__class__.__name__, obj.pk)

    created_instances = []
    for step_data in steps:
        instance = ApprovalInstance.objects.create(
            flow=flow,
            step_number=step_data["step"],
            status=ApprovalStatus.PENDING,
            assigned_to=step_data["assigned_to"],
            form=step_data.get("form"),
        )
        created_instances.append(instance)
        
    logger.info(
        "Created approval instances - Flow ID: %s, Instances: %s",
        flow.id,
        [f"Step {inst.step_number}" for inst in created_instances],
    )

    return flow
