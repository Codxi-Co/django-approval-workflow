"""Django app configuration for approval workflow."""

from django.apps import AppConfig


class ApprovalWorkflowConfig(AppConfig):
    """Configuration for the approval workflow Django app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "approval_workflow"
    verbose_name = "Approval Workflow"

    def ready(self):
        """Perform app initialization."""
        # Import signals or other setup code here if needed
        pass
