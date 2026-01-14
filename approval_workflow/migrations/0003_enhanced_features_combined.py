# Generated for enhanced role strategies, logging, and translation support
#
# This migration adds support for:
# - Quorum-based approval strategies (QUORUM, MAJORITY, PERCENTAGE)
# - Hierarchical approval strategies (HIERARCHY_UP, HIERARCHY_CHAIN)
# - SLA and timeout management
# - Parallel approval support
# - Enhanced logging and tracking
# - Full translation support (i18n)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("approval_workflow", "0002_approvalinstance_approval_type"),
    ]

    operations = [
        # === Update Model Options for Translation ===
        migrations.AlterModelOptions(
            name="approvalflow",
            options={
                "verbose_name": "Approval Flow",
                "verbose_name_plural": "Approval Flows",
            },
        ),

        # === Update Role Selection Strategy Choices ===
        migrations.AlterField(
            model_name="approvalinstance",
            name="role_selection_strategy",
            field=models.CharField(
                blank=True,
                choices=[
                    ("anyone", "Anyone with role can approve"),
                    ("consensus", "All users with role must approve"),
                    ("round_robin", "Distribute approvals evenly among role users"),
                    ("quorum", "Require N out of M users to approve (configurable)"),
                    ("majority", "Require majority (>50%) of role users to approve"),
                    ("percentage", "Require X% of role users to approve"),
                    ("hierarchy_up", "Escalate through N levels of role hierarchy"),
                    (
                        "hierarchy_chain",
                        "Require approval from entire chain (direct manager + N levels up)",
                    ),
                    ("management_path", "Follow organizational reporting structure"),
                    (
                        "dynamic_attribute",
                        "Select users based on business object attributes",
                    ),
                    ("dynamic_function", "Custom function to determine approvers"),
                    ("lead_only", "Only the role lead/owner can approve"),
                    ("seniority_based", "Assign based on user seniority/tenure"),
                    (
                        "workload_balanced",
                        "Distribute based on current active approvals only",
                    ),
                ],
                help_text="Strategy for selecting approvers when assigned to a role",
                max_length=20,
                null=True,
            ),
        ),

        # === Quorum-Based Approval Fields ===
        migrations.AddField(
            model_name="approvalinstance",
            name="quorum_count",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                help_text="Number of approvals required for QUORUM strategy (e.g., 2 out of 5)",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="quorum_total",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                help_text="Total number of users for quorum calculation (optional, defaults to role users count)",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="percentage_required",
            field=models.DecimalField(
                max_digits=5,
                decimal_places=2,
                null=True,
                blank=True,
                help_text="Percentage required for PERCENTAGE strategy (e.g., 66.67 for 2/3)",
            ),
        ),

        # === Hierarchical Approval Fields ===
        migrations.AddField(
            model_name="approvalinstance",
            name="hierarchy_levels",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                default=1,
                help_text="Number of hierarchy levels to escalate for HIERARCHY_UP strategy",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="hierarchy_base_user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="hierarchy_base_approvals",
                to=settings.AUTH_USER_MODEL,
                help_text="Base user for hierarchical approval (e.g., account manager)",
            ),
        ),

        # === Delegation & Escalation Tracking ===
        migrations.AddField(
            model_name="approvalinstance",
            name="delegation_chain",
            field=models.JSONField(
                null=True,
                blank=True,
                help_text="Track delegation history: [{from_user, to_user, timestamp, reason}]",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="escalation_level",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Current escalation level for this approval instance",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="max_escalation_level",
            field=models.PositiveIntegerField(
                default=3,
                help_text="Maximum escalation level allowed for this approval",
            ),
        ),

        # === SLA & Timeout Management ===
        migrations.AddField(
            model_name="approvalinstance",
            name="due_date",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Deadline for this approval step",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="reminder_sent",
            field=models.BooleanField(
                default=False,
                help_text="Whether reminder notification has been sent",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="escalation_on_timeout",
            field=models.BooleanField(
                default=False,
                help_text="Whether to auto-escalate when timeout is reached",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="timeout_action",
            field=models.CharField(
                max_length=20,
                null=True,
                blank=True,
                choices=[
                    ("escalate", "Escalate"),
                    ("delegate", "Delegate"),
                    ("auto_approve", "Auto Approve"),
                    ("reject", "Auto Reject"),
                ],
                help_text="Action to take when timeout is reached",
            ),
        ),

        # === Parallel Approval Support ===
        migrations.AddField(
            model_name="approvalinstance",
            name="parallel_group",
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                help_text="Group identifier for parallel approval tracks",
            ),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="parallel_required",
            field=models.BooleanField(
                default=False,
                help_text="Whether this parallel step must complete before next sequential step",
            ),
        ),

        # === New Indexes for Performance ===
        migrations.AddIndex(
            model_name="approvalinstance",
            index=models.Index(
                fields=["due_date", "status"],
                name="appinst_due_date_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="approvalinstance",
            index=models.Index(
                fields=["flow", "parallel_group", "status"],
                name="appinst_parallel_idx",
            ),
        ),
    ]
