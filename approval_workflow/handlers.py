"""Custom hook handler for approval steps."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ApprovalInstance

logger = logging.getLogger(__name__)


class BaseApprovalHandler:
    """Base class for custom approval hook logic.
    
    You can extend this per model or service to implement custom
    business logic for approval workflow events.
    """

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

    def on_resubmission(self, instance: "ApprovalInstance") -> None:
        """Called when resubmission is requested.
        
        Args:
            instance: The approval instance requesting resubmission
        """
        logger.debug(
            "Base approval handler - on_resubmission called - Flow ID: %s, Step: %s",
            instance.flow.id,
            instance.step_number,
        )


def get_handler_for_instance(instance: "ApprovalInstance") -> BaseApprovalHandler:
    """Dynamically resolve the custom approval handler for the instance's model.
    
    This function attempts to import a custom handler class from the app's
    approval module following the naming convention: {ModelName}ApprovalHandler.
    If no custom handler is found, returns the base handler.
    
    Args:
        instance: The approval instance to get a handler for
        
    Returns:
        Instance of the custom handler or BaseApprovalHandler if none found
        
    Example:
        For a model named 'Document' in app 'myapp', this function will try
        to import 'myapp.approval.DocumentApprovalHandler'.
    """
    model_class = instance.flow.target.__class__
    app_label = model_class._meta.app_label
    model_name = model_class.__name__
    
    logger.debug(
        "Resolving approval handler - Flow ID: %s, Model: %s.%s",
        instance.flow.id,
        app_label,
        model_name,
    )

    try:
        module_path = f"{app_label}.approval"
        handler_class_name = f"{model_name}ApprovalHandler"
        
        logger.debug(
            "Attempting to import custom handler - Module: %s, Class: %s",
            module_path,
            handler_class_name,
        )
        
        module = __import__(module_path, fromlist=[handler_class_name])
        handler_class = getattr(module, handler_class_name)
        handler = handler_class()
        
        logger.info(
            "Custom approval handler loaded - Flow ID: %s, Handler: %s.%s",
            instance.flow.id,
            module_path,
            handler_class_name,
        )
        
        return handler
        
    except (ImportError, AttributeError) as e:
        logger.debug(
            "Custom handler not found, using base handler - Flow ID: %s, Error: %s",
            instance.flow.id,
            str(e),
        )
        return BaseApprovalHandler()
