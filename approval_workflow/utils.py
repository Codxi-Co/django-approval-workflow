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
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from .models import ApprovalInstance

logger = logging.getLogger(__name__)
User = get_user_model()


def can_user_approve(instance: "ApprovalInstance", acting_user: User, allow_higher_level: bool = True) -> bool:
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
    flow_id = getattr(instance.flow, 'id', 'None') if hasattr(instance, 'flow') and instance.flow else 'None'
    logger.debug(
        "Checking user approval permission - Flow ID: %s, Step: %s, Acting user: %s, Assigned to: %s",
        flow_id,
        instance.step_number,
        getattr(acting_user, 'username', str(acting_user)),
        getattr(instance.assigned_to, 'username', str(instance.assigned_to)) if instance.assigned_to else None,
    )
    
    assigned_user = instance.assigned_to

    # Direct assignment check
    if assigned_user and acting_user == assigned_user:
        logger.debug(
            "User authorized by direct assignment - Flow ID: %s, Step: %s, User: %s",
            flow_id,
            instance.step_number,
            getattr(acting_user, 'username', str(acting_user)),
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
            getattr(assigned_role, 'name', str(assigned_role)) if assigned_role else None,
            getattr(acting_role, 'name', str(acting_role)) if acting_role else None,
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
                getattr(acting_user, 'username', str(acting_user)),
                getattr(acting_role, 'name', str(acting_role)),
            )
        else:
            logger.debug(
                "User not authorized by role hierarchy - Flow ID: %s, Step: %s, User: %s",
                flow_id,
                instance.step_number,
                getattr(acting_user, 'username', str(acting_user)),
            )
            
        return is_authorized
        
    except Exception as e:
        logger.warning(
            "Role authorization check failed - Flow ID: %s, Step: %s, User: %s, Error: %s",
            flow_id,
            instance.step_number,
            getattr(acting_user, 'username', str(acting_user)),
            str(e),
        )
        return False
