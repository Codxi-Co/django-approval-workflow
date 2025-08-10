# Django Approval Workflow

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-4.0%2B-green)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-77%20passing-green)]()

A powerful, flexible, and reusable Django package for implementing dynamic multi-step approval workflows in your Django applications.

## ✨ Features

- **🚀 Simplified Interface**: New developer-friendly `advance_flow` API that takes objects directly
- **⚙️ MIDDLEWARE-Style Configuration**: Configure handlers in settings just like Django MIDDLEWARE
- **🔄 Dynamic Workflow Creation**: Create approval workflows for any Django model using GenericForeignKey
- **👥 Multi-Step Approval Process**: Support for sequential approval steps with role-based assignments
- **🎭 Role-Based Approvals**: Three strategies (ANYONE, CONSENSUS, ROUND_ROBIN) for dynamic role-based approvals
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
- **✅ Comprehensive Testing**: Full test suite with pytest (77+ tests passing)
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

**Role Selection Strategies:**
- `ANYONE`: Any user with the role can approve (first approval completes the step)
- `CONSENSUS`: All users with the role must approve before advancing
- `ROUND_ROBIN`: Automatically assigns to the user with the least current assignments

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

# Run all tests (77 tests)
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
```

## 📊 Performance Features

- **O(1) Current Step Lookup**: Uses denormalized CURRENT status for instant access
- **Single Query Strategy**: Repository pattern loads all data with one optimized query
- **Multi-Level Caching**: LRU cache, Django cache, and instance caching
- **Strategic Indexing**: Only 3 optimized database indexes for maximum performance
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
- ✨ **Simplified Interface**: New `advance_flow(object, action, user)` API
- ⚙️ **MIDDLEWARE-Style Configuration**: Configure handlers in Django settings
- 🎯 **Complete Hook System**: Before/after hooks for full lifecycle control
- 🔐 **Automatic Permission Validation**: Built-in user authorization
- 🔄 **Full Backward Compatibility**: Existing code continues to work
- ✅ **Comprehensive Testing**: 77 tests ensuring reliability

For detailed examples and advanced usage, see the documentation and test files.