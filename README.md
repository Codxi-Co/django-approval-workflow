# Django Approval Workflow

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-4.0%2B-green)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-81%20passing-green)]()

A powerful, flexible, and reusable Django package for implementing dynamic multi-step approval workflows in your Django applications.

## ✨ Features

- **🚀 Simplified Interface**: New developer-friendly `advance_flow` API that takes objects directly
- **⚙️ MIDDLEWARE-Style Configuration**: Configure handlers in settings just like Django MIDDLEWARE
- **🔄 Dynamic Workflow Creation**: Create approval workflows for any Django model using GenericForeignKey
- **👥 Multi-Step Approval Process**: Support for sequential approval steps with role-based assignments
- **🎯 Approval Types**: Four specialized types (APPROVE, SUBMIT, CHECK_IN_VERIFY, MOVE) with type-specific validation
- **🎭 Role-Based Approvals**: Basic strategies (ANYONE, CONSENSUS, ROUND_ROBIN) plus advanced quorum and hierarchy strategies
- **🔐 Automatic Permission Validation**: Built-in user authorization for both direct and role-based assignments
- **🔗 Role-Based Permissions**: Hierarchical role support using MPTT (Modified Preorder Tree Traversal)
- **⚡ High-Performance Architecture**: Enterprise-level optimizations with O(1) lookups and intelligent caching
- **📊 Repository Pattern**: Centralized data access with single-query optimizations
- **🔄 Flexible Actions**: Approve, reject, delegate, escalate, or request resubmission at any step
- **🎯 Enhanced Hook System**: Before and after hooks for complete workflow lifecycle control
- **🧩 Custom Fields Support**: Extensible `extra_fields` JSONField for custom data without package modifications
- **⏰ SLA Tracking**: Built-in SLA duration tracking for approval steps
- **🌐 REST API Ready**: Built-in REST API endpoints using Django REST Framework
- **🛠️ Django Admin Integration**: Full admin interface for managing workflows
- **🎨 Extensible Handlers**: Custom hook system for workflow events with settings-based configuration
- **📝 Form Integration**: Optional dynamic form support for approval steps
- **✅ Comprehensive Testing**: Full test suite with pytest (81+ tests passing)
- **🔄 Backward Compatibility**: Maintains compatibility with existing implementations

## 🚀 Quick Start

### Installation

```bash
pip install django-approval-workflow
```

### Django Settings

Add `approval_workflow` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your apps
    'approval_workflow',
    'mptt',  # Required for hierarchical roles
    'rest_framework',  # Optional, for API endpoints
]

# Optional: Configure handlers like Django MIDDLEWARE
APPROVAL_HANDLERS = [
    'myapp.handlers.DocumentApprovalHandler',
    'myapp.handlers.TicketApprovalHandler',
    'myapp.custom.StageApprovalHandler',
]

# Other optional settings
APPROVAL_ROLE_MODEL = "myapp.Role"  # Default: None
APPROVAL_ROLE_FIELD = "role"  # Default: "role"
APPROVAL_DYNAMIC_FORM_MODEL = "myapp.DynamicForm"  # Default: None
APPROVAL_FORM_SCHEMA_FIELD = "form_info"  # Default: "schema"
APPROVAL_HEAD_MANAGER_FIELD = "head_manager"  # Default: None
```

### Run Migrations

```bash
python manage.py migrate approval_workflow
```

## 📖 New Simplified Usage

### ✨ Enhanced `advance_flow` Interface

The new interface eliminates the need to manually find approval instances:

```python
from approval_workflow.services import start_flow, advance_flow
from django.contrib.auth import get_user_model

User = get_user_model()

# Create users
manager = User.objects.get(username='manager')
employee = User.objects.get(username='employee')

# Your model instance
document = MyDocument.objects.create(title="Important Document")

# Start an approval workflow
flow = start_flow(
    obj=document,
    steps=[
        {"step": 1, "assigned_to": employee},
        {"step": 2, "assigned_to": manager},
    ]
)

# ✨ NEW: Simple interface - just pass the object and user
result = advance_flow(document, 'approved', employee, comment="Looks good!")

# ✨ NEW: Automatic permission checking and error handling
try:
    advance_flow(document, 'approved', unauthorized_user)
except PermissionError as e:
    print(f"Access denied: {e}")
except ValueError as e:
    print(f"No current approval found: {e}")
```

### 🔄 All Workflow Actions

```python
# Approve a document
advance_flow(document, 'approved', current_user, comment="Approved by manager")

# Reject with detailed feedback
advance_flow(ticket, 'rejected', current_user, comment="Missing required documentation")

# Request resubmission with additional review steps
advance_flow(
    document,
    'resubmission',
    current_user,
    comment="Need legal review before final approval",
    resubmission_steps=[
        {"step": 5, "assigned_to": legal_reviewer},
        {"step": 6, "assigned_to": director}
    ]
)

# Delegate to another user
advance_flow(
    ticket,
    'delegated',
    current_user,
    comment="Delegating while on vacation",
    delegate_to=specialist_user
)

# Escalate to higher authority
advance_flow(
    document,
    'escalated',
    current_user,
    comment="Escalating for executive approval"
)
```

### 🎯 Approval Types

Control the behavior and validation requirements for each approval step:

```python
from approval_workflow.choices import ApprovalType

flow = start_flow(
    obj=document,
    steps=[
        {
            "step": 1,
            "assigned_to": employee,
            "approval_type": ApprovalType.SUBMIT,  # Requires form with data
            "form": submission_form
        },
        {
            "step": 2,
            "assigned_to": manager,
            "approval_type": ApprovalType.APPROVE  # Normal approval (default)
        },
        {
            "step": 3,
            "assigned_to": quality_checker,
            "approval_type": ApprovalType.CHECK_IN_VERIFY  # Verification step
        },
        {
            "step": 4,
            "assigned_to": admin,
            "approval_type": ApprovalType.MOVE  # Transfer without forms
        }
    ]
)
```

**Available Approval Types:**

| Type | Form Behavior | Validation | Use Case |
|------|--------------|------------|----------|
| `APPROVE` | Optional | If form exists with schema, validates only when form_data provided | Standard approval steps |
| `SUBMIT` | **Required** | Form must be attached, form_data must be provided | Initial submission, data collection steps |
| `CHECK_IN_VERIFY` | Optional | Two-phase: 1) Check-in, 2) Approval. Optional form validation | Quality checks, compliance verification |
| `MOVE` | **Rejected** | Cannot have forms or form_data - raises error | Document routing, status changes |

**Type-Specific Validation:**
```python
# SUBMIT type - enforces form requirement
advance_flow(
    document,
    'approved',
    employee,
    form_data={"field": "value"}  # Required - will raise error if missing
)

# APPROVE type - optional form validation
advance_flow(document, 'approved', manager)  # Works with or without form
advance_flow(document, 'approved', manager, form_data={...})  # Optional form_data

# MOVE type - rejects any forms
advance_flow(document, 'approved', admin)  # No form allowed - pure transfer

# CHECK_IN_VERIFY type - two-phase verification flow
# Phase 1: Check-in
advance_flow(document, 'approved', quality_checker)  # First call: checks in
# Phase 2: Normal approval
advance_flow(document, 'approved', quality_checker)  # Second call: approves
```

**CHECK_IN_VERIFY Two-Phase Flow:**
```python
# Step 1: User checks in (tracked in extra_fields)
result = advance_flow(expense, 'approved', auditor)
# Returns same instance - stays on current step
# extra_fields now contains: {"checked_in": True, "checked_in_by": "auditor", ...}

# Step 2: User approves after verification
result = advance_flow(expense, 'approved', auditor, comment="Verified - approved")
# Moves to next step - workflow progresses
```

### ⚙️ MIDDLEWARE-Style Handler Configuration

Configure approval handlers in Django settings just like MIDDLEWARE:

```python
# settings.py
APPROVAL_HANDLERS = [
    'myapp.handlers.DocumentApprovalHandler',
    'myapp.handlers.TicketApprovalHandler',
    'myapp.custom.StageApprovalHandler',
]
```

Create powerful handlers with before/after hooks:

```python
# myapp/handlers.py
from approval_workflow.handlers import BaseApprovalHandler
from django.core.mail import send_mail

class DocumentApprovalHandler(BaseApprovalHandler):
    def before_approve(self, instance):
        """Called before approval processing starts."""
        document = instance.flow.target
        document.status = 'being_approved'
        document.save()
        
    def on_approve(self, instance):
        """Called during approval processing."""
        print(f"Document {instance.flow.target.id} approved by {instance.action_user}")
        
    def after_approve(self, instance):
        """Called after entire workflow completes successfully."""
        document = instance.flow.target
        document.status = 'published'
        document.published_at = timezone.now()
        document.save()
        
        # Send publication notification
        send_mail(
            subject=f'Document "{document.title}" Published',
            message='Your document has been approved and published.',
            from_email='noreply@company.com',
            recipient_list=[document.author.email],
        )
    
    def before_reject(self, instance):
        """Called before rejection processing."""
        # Log rejection attempt
        logger.info(f"Document {instance.flow.target.id} about to be rejected")
        
    def after_reject(self, instance):
        """Called after workflow is rejected and terminated."""
        document = instance.flow.target
        document.status = 'rejected'
        document.rejection_reason = instance.comment
        document.save()
        
        # Notify author of rejection
        send_mail(
            subject=f'Document "{document.title}" Rejected',
            message=f'Your document was rejected: {instance.comment}',
            from_email='noreply@company.com',
            recipient_list=[document.author.email],
        )
    
    def on_resubmission(self, instance):
        """Called when resubmission is requested."""
        document = instance.flow.target
        document.status = 'needs_revision'
        document.revision_requested_at = timezone.now()
        document.save()
        
        # Create revision task
        RevisionTask.objects.create(
            document=document,
            requested_by=instance.action_user,
            reason=instance.comment,
            due_date=timezone.now() + timedelta(days=7)
        )
```

### 🎯 Complete Hook System

**Available Hook Methods:**
- `before_approve(instance)` - Called before approval starts
- `on_approve(instance)` - Called during approval processing  
- `after_approve(instance)` - Called after workflow completes successfully
- `before_reject(instance)` - Called before rejection starts
- `on_reject(instance)` - Called during rejection processing
- `after_reject(instance)` - Called after workflow is rejected and terminated
- `before_resubmission(instance)` - Called before resubmission starts
- `on_resubmission(instance)` - Called during resubmission processing
- `after_resubmission(instance)` - Called after resubmission workflow completes
- `before_delegate(instance)` - Called before delegation starts
- `on_delegate(instance)` - Called during delegation processing
- `after_delegate(instance)` - Called after delegated workflow completes
- `before_escalate(instance)` - Called before escalation starts
- `on_escalate(instance)` - Called during escalation processing
- `after_escalate(instance)` - Called after escalated workflow completes
- `on_final_approve(instance)` - Called when final step is approved

### 🎭 Role-Based Workflows

Create sophisticated role-based approval workflows:

```python
from approval_workflow.services import start_flow
from approval_workflow.choices import RoleSelectionStrategy

# Get role instances
manager_role = Role.objects.get(name="Manager")
director_role = Role.objects.get(name="Director")

# Create role-based workflow with different strategies
flow = start_flow(
    obj=document,
    steps=[
        {
            "step": 1,
            "assigned_role": manager_role,
            "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            # Any manager can approve this step
        },
        {
            "step": 2,
            "assigned_role": director_role,
            "role_selection_strategy": RoleSelectionStrategy.CONSENSUS,
            # All directors must approve this step
        }
    ]
)

# Mixed role-based and user-based workflow
mixed_flow = start_flow(
    obj=document,
    steps=[
        {"step": 1, "assigned_to": specific_user},  # User-based step
        {
            "step": 2,
            "assigned_role": manager_role,
            "role_selection_strategy": RoleSelectionStrategy.ROUND_ROBIN,
            # Automatically assigns to manager with least workload
        }
    ]
)

# The new advance_flow automatically handles role-based permissions
advance_flow(document, 'approved', manager_with_role)  # ✅ Works if user has the role
advance_flow(document, 'approved', user_without_role)  # ❌ Raises PermissionError
```

**Role Selection Strategies (Supported):**
- `ANYONE`: Any user with the role can approve (first approval completes the step)
- `CONSENSUS`: All users with the role must approve before advancing
- `ROUND_ROBIN`: Automatically assigns to the user with the least current assignments
- `QUORUM`: Require N approvals out of M users
- `MAJORITY`: Require >50% approvals
- `PERCENTAGE`: Require a specific percentage (inclusive) of approvals
- `HIERARCHY_UP`: Approvals from N levels up in a role hierarchy
- `HIERARCHY_CHAIN`: Approvals from the base user plus N levels up

**Note:** Additional strategy labels like `MANAGEMENT_PATH`, `DYNAMIC_*`, `LEAD_ONLY`, `SENIORITY_BASED`, and `WORKLOAD_BALANCED` are reserved for future support and are rejected at validation time.

### 🚀 Enhanced Role-Based Approval Strategies

The package includes advanced approval strategies for enterprise use cases:

#### ✅ Quorum-Based Approval

Require a specific number of approvals from a group:

```python
from approval_workflow.choices import RoleSelectionStrategy
from datetime import datetime, timedelta

# Example: 2 out of 5 committee members must approve
flow = start_flow(
    obj=expense_request,
    steps=[
        {
            "step": 1,
            "assigned_role": committee_role,
            "role_selection_strategy": RoleSelectionStrategy.QUORUM,
            "quorum_count": 2,  # Need 2 approvals
            "quorum_total": 5,  # Out of 5 total users
            "due_date": datetime.now() + timedelta(days=3),
            "escalation_on_timeout": True,
            "timeout_action": "escalate",
        }
    ]
)

# First committee member approves
advance_flow(expense_request, 'approved', committee_member1)
# Status: Still CURRENT (1/2 approvals)

# Second committee member approves
advance_flow(expense_request, 'approved', committee_member2)
# Status: APPROVED! (2/2 reached - remaining instances auto-cancelled)
```

**Real-World Use Case: Purchase Request Approval**
```python
# Purchase requests over $10,000 need 2 out of 5 finance committee approvals
def create_purchase_request_workflow(purchase_request):
    if purchase_request.amount > 10000:
        return start_flow(
            obj=purchase_request,
            steps=[
                {
                    "step": 1,
                    "assigned_role": finance_committee_role,
                    "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                    "quorum_count": 2,
                    "quorum_total": 5,
                    "due_date": datetime.now() + timedelta(days=5),
                    "timeout_action": "escalate",
                    "escalation_on_timeout": True,
                }
            ]
        )
```

#### 📊 Majority Approval

Require majority (>50%) of role users to approve:

```python
# If role has 5 users, need 3 approvals (majority of 5)
flow = start_flow(
    obj=contract,
    steps=[
        {
            "step": 1,
            "assigned_role": board_members_role,
            "role_selection_strategy": RoleSelectionStrategy.MAJORITY,
            # Automatically calculates >50% requirement
            "due_date": datetime.now() + timedelta(days=7),
        }
    ]
)
```

#### 📈 Percentage-Based Approval

Require specific percentage of approvals:

```python
# Need 2/3 (66.67%) of users to approve
flow = start_flow(
    obj=strategic_plan,
    steps=[
        {
            "step": 1,
            "assigned_role": stakeholders_role,
            "role_selection_strategy": RoleSelectionStrategy.PERCENTAGE,
            "percentage_required": 66.67,  # 2/3 majority
            "due_date": datetime.now() + timedelta(days=14),
        }
    ]
)
```

#### 💰 Sample Flow: Budget Control

An example workflow for budget approvals with thresholds:

```python
from approval_workflow.services import start_flow
from approval_workflow.choices import RoleSelectionStrategy, ApprovalType

def create_budget_control_flow(budget_request):
    steps = [
        # Step 1: Requester submits with a form
        {
            "step": 1,
            "assigned_to": budget_request.requester,
            "approval_type": ApprovalType.SUBMIT,
            "form": budget_request.form,
        },
    ]

    if budget_request.amount <= 5000:
        # Team lead approval
        steps.append(
            {
                "step": 2,
                "assigned_role": budget_request.team_lead_role,
                "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            }
        )
    elif budget_request.amount <= 20000:
        # Finance committee quorum
        steps.append(
            {
                "step": 2,
                "assigned_role": budget_request.finance_committee_role,
                "role_selection_strategy": RoleSelectionStrategy.QUORUM,
                "quorum_count": 2,
                "quorum_total": 5,
            }
        )
    else:
        # Executive chain approval
        steps.append(
            {
                "step": 2,
                "assigned_role": budget_request.requester_role,
                "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                "hierarchy_levels": 2,
                "hierarchy_base_user": budget_request.requester,
            }
        )
        steps.append(
            {
                "step": 3,
                "assigned_role": budget_request.cfo_role,
                "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            }
        )

    return start_flow(obj=budget_request, steps=steps)
```

#### 🏢 Hierarchical Approval (HIERARCHY_UP)

Automatically escalate through organizational hierarchy levels:

```python
# Example: Deal approval - Account Manager → Manager → Director → VP
# The number of levels depends on deal amount

def create_deal_approval_workflow(deal):
    # Determine hierarchy levels based on deal amount
    if deal.amount < 50000:
        levels = 1  # Account Manager → Manager only
    elif deal.amount < 100000:
        levels = 2  # Account Manager → Manager → Director
    else:
        levels = 3  # Account Manager → Manager → Director → VP

    return start_flow(
        obj=deal,
        steps=[
            {
                "step": 1,
                "assigned_role": account_manager_role,
                "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
                "hierarchy_levels": levels,
                "hierarchy_base_user": deal.account_manager,  # Start from this user's role
                "due_date": datetime.now() + timedelta(days=5),
            }
        ]
    )

# Usage:
deal = Deal.objects.create(
    account_manager=account_manager_user,
    amount=75000,
    client="Acme Corp"
)

# This creates approval instances for:
# 1. Manager (1 level up from account_manager)
# 2. Director (2 levels up from account_manager)
flow = create_deal_approval_workflow(deal)

# Account manager approves (not in approval chain, automatically skipped)
# Manager approves
advance_flow(deal, 'approved', manager_user)
# Status: Still CURRENT (waiting for director)

# Director approves
advance_flow(deal, 'approved', director_user)
# Status: APPROVED! All levels completed
```

**How HIERARCHY_UP Works:**
1. Starts from `hierarchy_base_user` (e.g., deal.account_manager)
2. Gets their role using the configured role field (default: `user.role`)
3. Walks up the role hierarchy using MPTT `parent` attribute
4. Creates approval instances for users at each level up
5. All levels must approve before workflow advances

**Role Hierarchy Setup (using MPTT):**
```python
# Create role hierarchy
vp_role = Role.objects.create(name="VP", parent=None)
director_role = Role.objects.create(name="Director", parent=vp_role)
manager_role = Role.objects.create(name="Manager", parent=director_role)
account_manager_role = Role.objects.create(name="Account Manager", parent=manager_role)

# Assign users to roles
account_manager = User.objects.create(username="john_doe", role=account_manager_role)
manager = User.objects.create(username="jane_smith", role=manager_role)
director = User.objects.create(username="bob_johnson", role=director_role)
vp = User.objects.create(username="alice_williams", role=vp_role)

# When deal with hierarchy_levels=2 is created:
# - Manager approves (1 level up)
# - Director approves (2 levels up)
# VP is NOT included (only 2 levels requested)
```

#### 🔄 Full Hierarchy Chain Approval

Require approval from entire chain (base user + all levels up):

```python
flow = start_flow(
    obj=purchase_order,
    steps=[
        {
            "step": 1,
            "assigned_role": employee_role,
            "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_CHAIN,
            "hierarchy_levels": 3,  # Employee + Manager + Director + VP
            "hierarchy_base_user": purchase_order.requester,
        }
    ]
)

# Creates approvals for:
# - Employee (base user)
# - Manager (1 level up)
# - Director (2 levels up)
# - VP (3 levels up)
# ALL must approve before advancing
```

#### ⏰ SLA & Timeout Management

Configure deadlines and automatic actions:

```python
from datetime import datetime, timedelta

flow = start_flow(
    obj=time_sensitive_request,
    steps=[
        {
            "step": 1,
            "assigned_to": manager,
            "due_date": datetime.now() + timedelta(days=2),
            "reminder_sent": False,
            "escalation_on_timeout": True,
            "timeout_action": "escalate",  # or "delegate", "auto_approve", "reject"
        }
    ]
)

# Check for timeout in your management command or cron job
from approval_workflow.models import ApprovalInstance

def check_timeouts():
    """Check for overdue approvals and take action."""
    overdue = ApprovalInstance.objects.filter(
        status=ApprovalStatus.CURRENT,
        due_date__lt=timezone.now()
    )

    for instance in overdue:
        if instance.escalation_on_timeout:
            if instance.timeout_action == "escalate":
                # Escalate to higher authority
                advance_flow(
                    instance.flow.target,
                    'escalated',
                    instance.assigned_to,
                    comment="Auto-escalated due to timeout"
                )
            elif instance.timeout_action == "reject":
                # Auto-reject
                advance_flow(
                    instance.flow.target,
                    'rejected',
                    instance.assigned_to,
                    comment="Auto-rejected due to timeout"
                )
```

#### 🔁 Delegation & Escalation Tracking

Track delegation and escalation history:

```python
# Delegate approval
advance_flow(
    document,
    'delegated',
    manager,
    delegate_to=acting_manager,
    comment="Delegating while on vacation"
)

# The delegation_chain is automatically tracked:
# [
#   {
#     "from_user": "manager",
#     "to_user": "acting_manager",
#     "timestamp": "2024-01-15T10:30:00Z",
#     "reason": "Delegating while on vacation"
#   }
# ]

# Escalate approval
advance_flow(
    document,
    'escalated',
    manager,
    comment="Escalating to director - requires executive review"
)

# Escalation level is tracked:
# escalation_level: 0 → 1 → 2
```

#### 🔀 Parallel Approval Tracks

Run multiple approval tracks simultaneously:

```python
# Parallel approval tracks for different aspects
flow = start_flow(
    obj=project_proposal,
    steps=[
        # Track 1: Technical approval (parallel_group="technical")
        {
            "step": 1,
            "assigned_role": tech_lead_role,
            "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            "parallel_group": "technical",
            "parallel_required": True,  # Must complete before step 2
        },
        # Track 2: Business approval (parallel_group="business")
        {
            "step": 1,
            "assigned_role": product_manager_role,
            "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            "parallel_group": "business",
            "parallel_required": True,  # Must complete before step 2
        },
        # Step 2: Only starts after BOTH parallel tracks complete
        {
            "step": 2,
            "assigned_to": director,
        }
    ]
)

# Both technical and business tracks can approve in parallel
# Step 2 only becomes CURRENT after BOTH are approved
```

#### 🌍 Translation Support

All approval choices are translatable:

```python
from django.utils.translation import gettext_lazy as _

# In your templates or views
from approval_workflow.choices import RoleSelectionStrategy

# Get translated label
strategy_label = RoleSelectionStrategy.QUORUM.label
# Returns: "Require N out of M users to approve (configurable)"
# (or translated version if active language is not English)

# Use in admin or forms
class ApprovalStepForm(forms.Form):
    strategy = forms.ChoiceField(
        choices=[(s.value, s.label) for s in RoleSelectionStrategy]
    )
```

#### 📝 Enhanced Logging

All workflow events are logged with structured, emoji-indicated messages:

```python
# Log format:
# [APPROVAL_WORKFLOW] ✨ NEW INSTANCE CREATED | Flow ID: 123 | Step: 1 | Status: CURRENT | ...
# [APPROVAL_WORKFLOW] ✅ APPROVED | Flow ID: 123 | Step: 1 | Action User: john_doe | ...
# [APPROVAL_WORKFLOW] ❌ REJECTED | Flow ID: 123 | Step: 2 | Action User: jane_smith | ...
# [APPROVAL_WORKFLOW] 🔄 DELEGATED | Flow ID: 123 | From: manager | To: acting_manager | ...
# [APPROVAL_WORKFLOW] ⬆️ ESCALATED | Flow ID: 123 | Level: 1 → 2 | ...

# Configure logging in settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'approvals.log',
        },
    },
    'loggers': {
        'approval_workflow': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

## 🏗️ Advanced Features

### 📝 Dynamic Form Integration

```python
# Create form with validation schema
expense_form = DynamicForm.objects.create(
    name="Expense Approval Form",
    schema={
        "type": "object",
        "properties": {
            "amount": {"type": "number", "minimum": 0},
            "category": {"type": "string", "enum": ["travel", "equipment"]},
            "description": {"type": "string", "minLength": 10}
        },
        "required": ["amount", "category", "description"]
    }
)

# Use in workflow with automatic validation
flow = start_flow(
    obj=expense_request,
    steps=[
        {"step": 1, "assigned_to": manager, "form": expense_form}
    ]
)

# Form data is validated automatically
advance_flow(
    expense_request,
    'approved',
    manager,
    form_data={
        "amount": 750.00,
        "category": "travel", 
        "description": "Conference attendance in NYC"
    }
)
```

### 🧩 Custom Fields Support

```python
# Add custom metadata to approval steps
flow = start_flow(
    obj=document,
    steps=[
        {
            "step": 1,
            "assigned_to": manager,
            "extra_fields": {
                "priority": "high",
                "department": "IT",
                "requires_signature": True,
                "custom_deadline": "2024-12-31",
                "tags": ["urgent", "compliance"]
            }
        }
    ]
)

# Access in handlers
class CustomApprovalHandler(BaseApprovalHandler):
    def on_approve(self, instance):
        priority = instance.extra_fields.get("priority", "normal")
        if priority == "high":
            send_urgent_notification(instance.assigned_to)
```

### ⚡ High-Performance Repository Pattern

```python
from approval_workflow.utils import get_approval_repository, get_approval_summary

# Single optimized query for all operations
repo = get_approval_repository(document)
current = repo.get_current_approval()        # O(1) lookup
next_step = repo.get_next_approval()         # No additional database hit
progress = repo.get_workflow_progress()      # Efficient progress calculation

# Or get comprehensive summary
summary = get_approval_summary(document)
print(f"Progress: {summary['progress_percentage']}%")
print(f"Current step: {summary['current_step'].step_number}")
```

### 🔄 Dynamic Workflow Extension

```python
# Extend existing workflows dynamically
new_instances = extend_flow(
    flow=flow,
    steps=[
        {"step": 3, "assigned_to": legal_reviewer},
        {"step": 4, "assigned_role": director_role, "role_selection_strategy": RoleSelectionStrategy.CONSENSUS}
    ]
)
```

## 🔧 Migration from Old Interface

The package maintains full backward compatibility:

```python
# OLD interface (still works)
current_step = get_current_approval(document)
advance_flow(instance=current_step, action='approved', user=user)

# NEW interface (recommended)
advance_flow(document, 'approved', user)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests (128 tests)
pytest

# Run with coverage
pytest --cov=approval_workflow
```

## 🔧 Configuration Reference

### Required Settings
```python
INSTALLED_APPS = [
    'approval_workflow',
    'mptt',  # For hierarchical roles
]
```

### Optional Settings
```python
# Handler configuration (MIDDLEWARE style)
APPROVAL_HANDLERS = [
    'myapp.handlers.DocumentApprovalHandler',
    'myapp.handlers.TicketApprovalHandler',
]

# Role model configuration
APPROVAL_ROLE_MODEL = "myapp.Role"  # Must inherit from MPTTModel
APPROVAL_ROLE_FIELD = "role"        # Field linking User to Role

# Form integration
APPROVAL_DYNAMIC_FORM_MODEL = "myapp.DynamicForm"
APPROVAL_FORM_SCHEMA_FIELD = "schema"  # Field containing JSON schema

# Escalation configuration
APPROVAL_HEAD_MANAGER_FIELD = "head_manager"  # Direct manager field

# Language/Locale configuration
LANGUAGE_CODE = 'en-us'  # Default language
USE_I18N = True
USE_L10N = True

LOCALE_PATHS = [
    '/path/to/your/project/locale',
    '/path/to/approval_workflow/locale',  # Include package translations
]

LANGUAGES = [
    ('en', 'English'),
    ('ar', 'Arabic'),
    # Add more languages as needed
]
```

### 🌍 Translation Support

The package includes full internationalization support with **Arabic translations** included out of the box:

**Available Languages:**
- 🇺🇸 English (en)
- 🇸🇦 Arabic (ar)

**Using Translations in Your Project:**

1. **Configure Django settings:**
```python
# settings.py
LANGUAGE_CODE = 'ar'  # Set Arabic as default
USE_I18N = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
    BASE_DIR / 'approval_workflow' / 'locale',  # Include package translations
]

MIDDLEWARE = [
    'django.middleware.locale.LocaleMiddleware',  # Add this
    # ... other middleware
]
```

2. **Activate language in views:**
```python
from django.utils.translation import activate, get_language

# Set language to Arabic
activate('ar')

# Or let Django detect from request
# (requires LocaleMiddleware in MIDDLEWARE)
```

3. **Use in templates:**
```django
{% load i18n %}

<!-- Get translated label -->
{% get_current_language as LANGUAGE_CODE %}
<h1>{% trans "Approval Flow" %}</h1>

<!-- Switch language -->
<form action="{% url 'set_language' %}" method="post">
    {% csrf_token %}
    <input name="language" type="hidden" value="ar">
    <input type="submit" value="العربية">
</form>
```

4. **Access translated choices:**
```python
from approval_workflow.choices import RoleSelectionStrategy

# Get translated label based on active language
strategy_label = RoleSelectionStrategy.QUORUM.label
# English: "Require N out of M users to approve (configurable)"
# Arabic: "يتطلب موافقة N من أصل M مستخدمين (قابل للتكوين)"
```

**Adding More Languages:**

To add support for more languages:

1. Create new locale directory:
```bash
mkdir -p approval_workflow/locale/<lang_code>/LC_MESSAGES
```

2. Copy and translate the `django.po` file

3. Compile translations:
```bash
msgfmt -o approval_workflow/locale/<lang_code>/LC_MESSAGES/django.mo \
       approval_workflow/locale/<lang_code>/LC_MESSAGES/django.po
```

**For Arabic users, the package is ready to use out of the box:**

```python
# In your Django settings
LANGUAGE_CODE = 'ar'

# All approval choices, messages, and labels will automatically display in Arabic
```

## 📊 Performance Features

- **O(1) Current Step Lookup**: Uses denormalized CURRENT status for instant access
- **Single Query Strategy**: Repository pattern loads all data with one optimized query
- **Multi-Level Caching**: LRU cache, Django cache, and instance caching
- **Strategic Indexing**: Multiple optimized database indexes for maximum performance
- **Minimal Database Hits**: Designed for high-volume production environments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Mohamed Salah**  
Email: info@codxi.com  
GitHub: [Codxi-Co](https://github.com/Codxi-Co)

---

**Key Improvements in Latest Version:**
- 🎯 **Approval Types**: Four specialized types (APPROVE, SUBMIT, CHECK_IN_VERIFY, MOVE) with smart validation
- ✨ **Simplified Interface**: New `advance_flow(object, action, user)` API
- ⚙️ **MIDDLEWARE-Style Configuration**: Configure handlers in Django settings
- 🎯 **Complete Hook System**: Before/after hooks for full lifecycle control
- 🔐 **Automatic Permission Validation**: Built-in user authorization
- 🔄 **Full Backward Compatibility**: Existing code continues to work
- ✅ **Comprehensive Testing**: 128 tests ensuring reliability
- 🚀 **Enhanced Role Strategies**: QUORUM, MAJORITY, PERCENTAGE, HIERARCHY_UP, HIERARCHY_CHAIN
- ⏰ **SLA Management**: Due dates, timeouts, and automatic escalation/delegation/rejection
- 🔁 **Delegation Tracking**: Full delegation chain history
- 🔀 **Parallel Approvals**: Multiple concurrent approval tracks
- 🌍 **Full i18n Support**: Translated choices and messages
- 📝 **Enhanced Logging**: Structured logging with emoji indicators

For detailed examples and advanced usage, see the [ENHANCED_FEATURES.md](ENHANCED_FEATURES.md) documentation and test files.
