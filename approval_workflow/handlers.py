"""Custom hook handler for approval steps."""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import ApprovalInstance

logger = logging.getLogger(__name__)


class BaseApprovalHandler:
    """Base class for custom approval hook logic.

    You can extend this per model or service to implement custom
    business logic for approval workflow events.
    """

    def before_approve(self, instance: "ApprovalInstance") -> None:
        """Called before a step is approved.

        This method is triggered before the approval action is processed,
        allowing for pre-approval validation, logging, or setup. Use this
        for actions that should occur before the approval state changes, such as:
        - Pre-approval validation
        - Logging approval attempts
        - Setting up resources needed for approval
        - Sending pre-approval notifications

        Args:
            instance: The approval instance about to be approved
        """
        logger.debug(
            "Base approval handler - before_approve called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_approve(self, instance: "ApprovalInstance") -> None:
        """Called when a step is approved.

        Args:
            instance: The approval instance that was approved
        """
        logger.debug(
            "Base approval handler - on_approve called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_final_approve(self, instance: "ApprovalInstance") -> None:
        """Called when the final step is approved.

        Args:
            instance: The final approval instance that was approved
        """
        logger.debug(
            "Base approval handler - on_final_approve called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def before_reject(self, instance: "ApprovalInstance") -> None:
        """Called before a step is rejected.

        This method is triggered before the rejection action is processed,
        allowing for pre-rejection validation, logging, or setup. Use this
        for actions that should occur before the rejection state changes, such as:
        - Pre-rejection validation
        - Logging rejection attempts
        - Backing up data before rejection
        - Sending pre-rejection notifications

        Args:
            instance: The approval instance about to be rejected
        """
        logger.debug(
            "Base approval handler - before_reject called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_reject(self, instance: "ApprovalInstance") -> None:
        """Called when a step is rejected.

        Args:
            instance: The approval instance that was rejected
        """
        logger.debug(
            "Base approval handler - on_reject called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def before_resubmission(self, instance: "ApprovalInstance") -> None:
        """Called before resubmission is requested.

        This method is triggered before the resubmission action is processed,
        allowing for pre-resubmission validation, logging, or setup. Use this
        for actions that should occur before resubmission begins, such as:
        - Validating resubmission requirements
        - Logging resubmission attempts
        - Preparing data for resubmission workflow
        - Sending pre-resubmission notifications

        Args:
            instance: The approval instance about to request resubmission
        """
        logger.debug(
            "Base approval handler - before_resubmission called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_resubmission(self, instance: "ApprovalInstance") -> None:
        """Called when resubmission is requested.

        This method is triggered when an approval step requests resubmission,
        meaning the current workflow is paused and new steps are added for
        additional review or corrections.

        Override this method in your custom handler to implement specific
        business logic when resubmission occurs, such as:
        - Notifying relevant stakeholders
        - Updating the target object's status
        - Logging resubmission events
        - Triggering external workflows

        Args:
            instance: The approval instance that requested resubmission.
                     This instance will have status NEEDS_RESUBMISSION.

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def on_resubmission(self, instance):
                    # Update document status
                    document = instance.flow.target
                    document.status = 'needs_revision'
                    document.save()

                    # Send notification
                    notify_author(document, instance.comment)
        """
        logger.debug(
            "Base approval handler - on_resubmission called - Flow ID: %s, Step: %s, User: %s, Comment: %s",
            instance.flow.id,
            instance.step_number,
            (
                getattr(instance.action_user, "username", "Unknown")
                if instance.action_user
                else "None"
            ),
            (
                instance.comment[:50] + "..."
                if instance.comment and len(instance.comment) > 50
                else instance.comment or "No comment"
            ),
        )

    def before_delegate(self, instance: "ApprovalInstance") -> None:
        """Called before a step is delegated to another user.

        This method is triggered before the delegation action is processed,
        allowing for pre-delegation validation, logging, or setup. Use this
        for actions that should occur before delegation begins, such as:
        - Validating delegation permissions
        - Logging delegation attempts
        - Preparing delegation data
        - Sending pre-delegation notifications

        Args:
            instance: The approval instance about to be delegated
        """
        logger.debug(
            "Base approval handler - before_delegate called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_delegate(self, instance: "ApprovalInstance") -> None:
        """Called when a step is delegated to another user.

        Args:
            instance: The approval instance that was delegated
        """
        logger.debug(
            "Base approval handler - on_delegate called - Flow ID: %s, Step: %s, User: %s",
            instance.flow.id,
            instance.step_number,
            (
                getattr(instance.action_user, "username", "Unknown")
                if instance.action_user
                else "None"
            ),
        )

    def before_escalate(self, instance: "ApprovalInstance") -> None:
        """Called before a step is escalated to a higher manager.

        This method is triggered before the escalation action is processed,
        allowing for pre-escalation validation, logging, or setup. Use this
        for actions that should occur before escalation begins, such as:
        - Validating escalation permissions
        - Logging escalation attempts
        - Preparing escalation data
        - Sending pre-escalation notifications

        Args:
            instance: The approval instance about to be escalated
        """
        logger.debug(
            "Base approval handler - before_escalate called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def on_escalate(self, instance: "ApprovalInstance") -> None:
        """Called when a step is escalated to a higher manager.

        Args:
            instance: The approval instance that was escalated
        """
        logger.debug(
            "Base approval handler - on_escalate called - Flow ID: %s, Step: %s, User: %s",
            instance.flow.id,
            instance.step_number,
            (
                getattr(instance.action_user, "username", "Unknown")
                if instance.action_user
                else "None"
            ),
        )

    def after_approve(self, instance: "ApprovalInstance") -> None:
        """Called after the entire approval workflow is completed successfully.

        This method is triggered only when the final approval step is completed
        and the entire workflow has finished successfully. Use this for actions
        that should occur after the complete approval cycle, such as:
        - Updating the target object's final status
        - Sending final notifications
        - Triggering downstream processes
        - Cleaning up temporary resources

        Args:
            instance: The final approval instance that completed the workflow

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def after_approve(self, instance):
                    # Update document to published status
                    document = instance.flow.target
                    document.status = 'published'
                    document.save()

                    # Send final notification
                    notify_all_stakeholders(document)
        """
        logger.debug(
            "Base approval handler - after_approve called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def after_reject(self, instance: "ApprovalInstance") -> None:
        """Called after a workflow is rejected and completely terminated.

        This method is triggered when any approval step is rejected and the
        entire workflow is terminated. Use this for cleanup actions that should
        occur after the complete rejection cycle, such as:
        - Updating the target object's final rejected status
        - Sending rejection notifications to all stakeholders
        - Archiving or cleaning up related data
        - Triggering alternative workflows

        Args:
            instance: The approval instance that was rejected

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def after_reject(self, instance):
                    # Update document to rejected status
                    document = instance.flow.target
                    document.status = 'rejected'
                    document.save()

                    # Notify all participants
                    notify_workflow_participants(document, 'rejected')
        """
        logger.debug(
            "Base approval handler - after_reject called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def after_resubmission(self, instance: "ApprovalInstance") -> None:
        """Called after a resubmission workflow is completed (approved or rejected).

        This method is triggered when a workflow that was previously marked for
        resubmission finally completes (either approved or rejected). Use this
        for actions that should occur after the complete resubmission cycle, such as:
        - Final status updates after resubmission review
        - Notifications about resubmission completion
        - Audit logging for resubmission cycles
        - Cleanup of resubmission-related temporary data

        Args:
            instance: The final approval instance that completed the resubmission workflow

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def after_resubmission(self, instance):
                    # Log resubmission completion
                    document = instance.flow.target
                    log_resubmission_cycle_complete(document, instance)

                    # Update revision tracking
                    document.increment_revision_cycle()
                    document.save()
        """
        logger.debug(
            "Base approval handler - after_resubmission called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def after_delegate(self, instance: "ApprovalInstance") -> None:
        """Called after a delegated workflow is completed (approved or rejected).

        This method is triggered when a workflow that was previously delegated
        finally completes. Use this for actions that should occur after the
        complete delegation cycle, such as:
        - Notifying original delegator about completion
        - Updating delegation tracking metrics
        - Final status synchronization
        - Cleanup of delegation-related data

        Args:
            instance: The final approval instance that completed the delegated workflow

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def after_delegate(self, instance):
                    # Find original delegator and notify
                    original_delegator = find_original_delegator(instance)
                    notify_delegation_complete(original_delegator, instance)
        """
        logger.debug(
            "Base approval handler - after_delegate called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )

    def after_escalate(self, instance: "ApprovalInstance") -> None:
        """Called after an escalated workflow is completed (approved or rejected).

        This method is triggered when a workflow that was previously escalated
        finally completes. Use this for actions that should occur after the
        complete escalation cycle, such as:
        - Notifying original escalator about completion
        - Updating escalation tracking and metrics
        - HR notifications for escalation patterns
        - Cleanup of escalation-related data

        Args:
            instance: The final approval instance that completed the escalated workflow

        Example:
            class DocumentApprovalHandler(BaseApprovalHandler):
                def after_escalate(self, instance):
                    # Track escalation patterns for HR
                    track_escalation_completion(instance)

                    # Notify original escalator
                    original_escalator = find_original_escalator(instance)
                    notify_escalation_complete(original_escalator, instance)
        """
        logger.debug(
            "Base approval handler - after_escalate called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )


def get_handler_for_instance(instance: "ApprovalInstance") -> BaseApprovalHandler:
    """Dynamically resolve the custom approval handler for the instance's model.

    This function first checks APPROVAL_HANDLERS setting for configured handlers,
    then falls back to the old auto-discovery method.

    Args:
        instance: The approval instance to get a handler for

    Returns:
        Instance of the custom handler or BaseApprovalHandler if none found

    Settings Configuration Example:
        APPROVAL_HANDLERS = [
            'myapp.handlers.DocumentApprovalHandler',
            'myapp.handlers.TicketApprovalHandler',
            'myapp.custom.StageApprovalHandler',
        ]

    Fallback Example:
        For a model named 'Document' in app 'myapp', this function will try
        to import 'myapp.approval.DocumentApprovalHandler'.
    """
    from django.conf import settings

    model_class = instance.flow.target.__class__
    app_label = model_class._meta.app_label
    model_name = model_class.__name__

    logger.debug(
        "Resolving approval handler - Flow ID: %s, Model: %s.%s",
        instance.flow.id,
        app_label,
        model_name,
    )

    # First, try settings-based configuration
    approval_handlers = getattr(settings, "APPROVAL_HANDLERS", [])
    if approval_handlers:
        handler = _get_handler_from_settings(instance, approval_handlers, model_name)
        if handler:
            return handler

    # Fallback to old auto-discovery method
    return _get_handler_auto_discovery(instance, app_label, model_name)


def _get_handler_from_settings(
    instance: "ApprovalInstance", handlers_list: list, model_name: str
) -> Optional[BaseApprovalHandler]:
    """Try to load handler from settings-based configuration."""
    target_handler_name = f"{model_name}ApprovalHandler"

    for handler_path in handlers_list:
        try:
            # Split the path into module and class
            module_path, class_name = handler_path.rsplit(".", 1)

            # Check if this is the handler we're looking for
            if class_name == target_handler_name:
                logger.debug(
                    "Attempting to import handler from settings - Path: %s",
                    handler_path,
                )

                module = __import__(module_path, fromlist=[class_name])
                handler_class = getattr(module, class_name)
                handler = handler_class()

                logger.info(
                    "Handler loaded from settings - Flow ID: %s, Handler: %s",
                    instance.flow.id,
                    handler_path,
                )

                return handler

        except (ImportError, AttributeError, ValueError) as e:
            logger.warning(
                "Failed to import handler from settings - Path: %s, Error: %s",
                handler_path,
                str(e),
            )
            continue

    logger.debug(
        "No matching handler found in settings for model: %s",
        model_name,
    )
    return None


def _get_handler_auto_discovery(
    instance: "ApprovalInstance", app_label: str, model_name: str
) -> BaseApprovalHandler:
    """Fallback to auto-discovery method (original behavior)."""
    try:
        module_path = f"{app_label}.approval"
        handler_class_name = f"{model_name}ApprovalHandler"

        logger.debug(
            "Attempting auto-discovery - Module: %s, Class: %s",
            module_path,
            handler_class_name,
        )

        module = __import__(module_path, fromlist=[handler_class_name])
        handler_class = getattr(module, handler_class_name)
        handler = handler_class()

        logger.info(
            "Handler loaded via auto-discovery - Flow ID: %s, Handler: %s.%s",
            instance.flow.id,
            module_path,
            handler_class_name,
        )

        return handler

    except (ImportError, AttributeError) as e:
        logger.debug(
            "Auto-discovery failed, using base handler - Flow ID: %s, Error: %s",
            instance.flow.id,
            str(e),
        )
        return BaseApprovalHandler()
