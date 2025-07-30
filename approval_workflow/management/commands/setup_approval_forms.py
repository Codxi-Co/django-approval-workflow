"""Management command to setup dynamic form references for approval workflow."""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from approval_workflow.models import ApprovalInstance


class Command(BaseCommand):
    """
    Management command to update existing ApprovalInstance records
    with the configured dynamic form model from settings.

    This is only needed for existing instances created before
    APPROVAL_DYNAMIC_FORM_MODEL was configured. New instances
    automatically get the form_content_type set.
    """

    help = "Setup dynamic form references for existing approval workflow instances"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        form_model_path = getattr(settings, "APPROVAL_DYNAMIC_FORM_MODEL", None)

        if not form_model_path:
            self.stdout.write(
                self.style.WARNING(
                    "APPROVAL_DYNAMIC_FORM_MODEL not configured in settings. "
                    "Set this to your dynamic form model (e.g., 'myapp.DynamicForm')"
                )
            )
            return

        try:
            app_label, model_name = form_model_path.split(".", 1)
            content_type = ContentType.objects.get(
                app_label=app_label, model=model_name.lower()
            )
        except (ValueError, ContentType.DoesNotExist) as e:
            raise CommandError(
                f"Invalid APPROVAL_DYNAMIC_FORM_MODEL setting '{form_model_path}': {e}"
            )

        # Only update instances without form_content_type
        queryset = ApprovalInstance.objects.filter(form_content_type__isnull=True)
        count = queryset.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No existing approval instances need updating. "
                    "New instances will automatically use the configured form model."
                )
            )
            return

        if options["dry_run"]:
            self.stdout.write(
                f"DRY RUN: Would update {count} existing approval instances with "
                f"form_content_type={content_type}"
            )
            return

        # Update existing instances by triggering their save method
        # This ensures the automatic form_content_type setting logic runs
        for instance in queryset:
            instance.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {count} existing approval instances. "
                f"New instances will automatically use form_content_type={content_type}"
            )
        )
