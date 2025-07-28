# Django Approval Workflow

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-4.0%2B-green)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A powerful, flexible, and reusable Django package for implementing dynamic multi-step approval workflows in your Django applications.

## ✨ Features

- **Dynamic Workflow Creation**: Create approval workflows for any Django model using GenericForeignKey
- **Multi-Step Approval Process**: Support for sequential approval steps with role-based assignments
- **Role-Based Permissions**: Hierarchical role support using MPTT (Modified Preorder Tree Traversal)
- **High-Performance Architecture**: Enterprise-level optimizations with O(1) lookups and intelligent caching
- **Repository Pattern**: Centralized data access with single-query optimizations
- **Flexible Actions**: Approve, reject, or request resubmission at any step
- **REST API Ready**: Built-in REST API endpoints using Django REST Framework
- **Django Admin Integration**: Full admin interface for managing workflows
- **Extensible Handlers**: Custom hook system for workflow events
- **Form Integration**: Optional dynamic form support for approval steps
- **Comprehensive Testing**: Full test suite with pytest

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
```

### Optional Settings

```python
# Custom role model (must inherit from MPTTModel)
APPROVAL_ROLE_MODEL = "myapp.Role"  # Default: None

# Field name linking User to Role model
APPROVAL_ROLE_FIELD = "role"  # Default: "role"

# Custom form model for dynamic forms
APPROVAL_DYNAMIC_FORM_MODEL = "myapp.DynamicForm"  # Default: None
```

### Run Migrations

```bash
python manage.py migrate approval_workflow
```

## 📖 Usage

### Basic Example

```python
from approval_workflow.services import start_flow, advance_flow
from approval_workflow.utils import can_user_approve, get_current_approval, get_next_approval
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

# Get current pending approval
current_step = get_current_approval(document)
if current_step and can_user_approve(current_step, employee):
    # Advance the workflow
    next_step = advance_flow(
        instance=current_step,
        action="approved",
        user=employee,
        comment="Looks good to me!"
    )

# Check what's next in the workflow
next_step = get_next_approval(document)
if next_step:
    print(f"Next approver: {next_step.assigned_to}")
```

### Role-Based Approval

With hierarchical roles (using MPTT):

```python
# models.py
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.auth.models import AbstractUser

class Role(MPTTModel):
    name = models.CharField(max_length=100)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, 
                           null=True, blank=True, related_name='children')

class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)

# Usage
senior_role = Role.objects.create(name="Senior Manager")
junior_role = Role.objects.create(name="Junior Manager", parent=senior_role)

senior_user = User.objects.create(username="senior", role=senior_role)
junior_user = User.objects.create(username="junior", role=junior_role)

# Senior users can approve tasks assigned to junior users
instance = ApprovalInstance.objects.create(assigned_to=junior_user)
assert can_user_approve(instance, senior_user)  # True

# Control higher-level approval behavior
assert can_user_approve(instance, senior_user, allow_higher_level=True)   # True (default)
assert can_user_approve(instance, senior_user, allow_higher_level=False)  # False
assert can_user_approve(instance, junior_user, allow_higher_level=False)  # True (direct assignment)
```

### Permission Control

The `can_user_approve()` function supports fine-grained permission control:

```python
from approval_workflow.utils import can_user_approve

# Default behavior - allows hierarchical approval
can_user_approve(instance, user)  # Same as allow_higher_level=True

# Strict mode - only assigned user can approve
can_user_approve(instance, user, allow_higher_level=False)
```

**Parameters:**
- `instance`: The approval instance to check
- `acting_user`: The user attempting to approve
- `allow_higher_level` (optional): Whether to allow users with higher roles to approve on behalf of assigned users (default: `True`)

**When `allow_higher_level=False`:**
- Only the directly assigned user can approve their step
- Role hierarchy is ignored for approval permissions
- Useful for strict approval workflows where delegation is not allowed

### Resubmission Workflows

Handle cases where additional review or corrections are needed:

```python
from approval_workflow.services import advance_flow

# Current workflow: Document -> Manager Review -> Director Approval
current_step = flow.instances.get(step_number=1)

# Manager requests resubmission with additional legal review
next_step = advance_flow(
    instance=current_step,
    action="resubmission", 
    user=manager,
    comment="Legal review required before approval",
    resubmission_steps=[
        {"step": 2, "assigned_to": legal_reviewer},
        {"step": 3, "assigned_to": director},  # Original director step continues
    ]
)

# Current step is marked as NEEDS_RESUBMISSION
# New steps are added to the workflow
assert current_step.status == ApprovalStatus.NEEDS_RESUBMISSION  
assert next_step.step_number == 2  # First new step
```

### Custom Handlers

Create custom handlers for workflow events:

```python
# myapp/approval.py
from approval_workflow.handlers import BaseApprovalHandler
from django.utils import timezone

class MyDocumentApprovalHandler(BaseApprovalHandler):
    def on_approve(self, instance):
        # Custom logic when a step is approved
        print(f"Step {instance.step_number} approved!")
    
    def on_final_approve(self, instance):
        # Custom logic when workflow is complete
        instance.flow.target.status = 'approved'
        instance.flow.target.save()
    
    def on_reject(self, instance):
        # Custom logic when a step is rejected
        instance.flow.target.status = 'rejected'
        instance.flow.target.save()
    
    def on_resubmission(self, instance):
        # Custom logic when resubmission is requested
        document = instance.flow.target
        document.status = 'needs_revision'
        document.revision_requested_at = timezone.now()
        document.save()
        
        # Send notification to document author
        send_notification(
            user=document.author,
            message=f"Document '{document.title}' needs revision: {instance.comment}",
            type='resubmission_request'
        )
        
        # Log the resubmission event
        AuditLog.objects.create(
            action='resubmission_requested',
            target=document,
            user=instance.action_user,
            details={'step': instance.step_number, 'comment': instance.comment}
        )
```

**Handler Methods:**
- `on_approve(instance)`: Called when any step is approved
- `on_final_approve(instance)`: Called when the final step is approved (workflow complete)
- `on_reject(instance)`: Called when any step is rejected
- `on_resubmission(instance)`: Called when resubmission is requested

### Approval Utilities

The package provides convenient utility functions to query approval states for any Django object:

```python
from approval_workflow.utils import (
    get_current_approval,
    get_next_approval, 
    get_full_approvals,
    get_approval_flow
)

document = Document.objects.get(id=1)

# Get the current pending approval step
current = get_current_approval(document)
if current:
    print(f"Waiting for: {current.assigned_to}")
    print(f"Step: {current.step_number}")

# Get the next step in the workflow  
next_step = get_next_approval(document)
if next_step:
    print(f"After current: {next_step.assigned_to}")

# Get complete approval history
all_approvals = get_full_approvals(document)
for approval in all_approvals:
    print(f"Step {approval.step_number}: {approval.status} "
          f"by {approval.assigned_to}")

# Get the approval flow itself
flow = get_approval_flow(document)
if flow:
    print(f"Flow created: {flow.created_at}")
    print(f"Total steps: {flow.instances.count()}")
```

**Utility Functions:**
- `get_current_approval(obj)`: Returns current pending approval step
- `get_next_approval(obj)`: Returns next pending step after current
- `get_full_approvals(obj)`: Returns all approval instances (complete history)
- `get_approval_flow(obj)`: Returns the ApprovalFlow instance for the object

These functions work with any Django model object and return `None` or empty lists if no workflow exists.

### High-Performance Repository Pattern

For enterprise applications with high-volume workflows, use the repository pattern for optimal performance:

```python
from approval_workflow.utils import get_approval_repository, get_approval_summary

document = Document.objects.get(id=1)

# Single repository instance for multiple operations (recommended)
repo = get_approval_repository(document)

# All these calls use cached data from a single optimized query
current = repo.get_current_approval()        # O(1) lookup using CURRENT status
next_step = repo.get_next_approval()         # No additional database hit
all_steps = repo.instances                   # Complete workflow data
flow = repo.flow                             # Flow information
pending_count = len(repo.get_pending_approvals())  # Efficient counting
progress = repo.get_workflow_progress()      # Comprehensive progress data

# Or get everything at once
summary = get_approval_summary(document)
print(f"Progress: {summary['progress_percentage']}%")
print(f"Current step: {summary['current_step'].step_number}")
```

**Performance Benefits:**
- **O(1) Current Step Lookup**: Uses denormalized CURRENT status for instant access
- **Single Query Strategy**: Repository loads all data with one optimized database query
- **Multi-Level Caching**: LRU cache, Django cache, and instance caching for maximum speed
- **Minimal Database Hits**: Designed for high-volume production environments

## 🏗️ Models

### ApprovalFlow
Central model that links to any Django model via GenericForeignKey.

### ApprovalInstance
Represents individual steps in the approval process with status tracking.

**Status Types:**
- `PENDING`: Future steps waiting to be processed
- `CURRENT`: Active step requiring approval (optimized for O(1) lookups)
- `APPROVED`: Completed and approved steps
- `REJECTED`: Rejected steps (workflow terminates)
- `NEEDS_RESUBMISSION`: Steps requiring resubmission with additional review
- `CANCELLED`: Cancelled steps
- `COMPLETED`: Final workflow completion status

## 🔧 Configuration

### Role Model Requirements
If using role-based approvals, your role model must:
- Inherit from `MPTTModel`
- Implement hierarchical relationships
- Be linked to your User model

### Custom Form Integration
For dynamic forms in approval steps:
- Configure `APPROVAL_DYNAMIC_FORM_MODEL`
- Form model should have a `schema` field for validation

## ⚡ Performance Considerations

### Database Optimization
The package is optimized for high-volume production environments:

- **Strategic Indexing**: Only 3 optimized database indexes for maximum performance
- **CURRENT Status**: Denormalized design eliminates complex queries for active step lookup
- **Repository Pattern**: Single-query strategy with intelligent caching reduces database load
- **Unique Constraints**: Database-level enforcement ensures data integrity

### Best Practices for High-Volume Workflows

```python
# ✅ RECOMMENDED: Use repository pattern for multiple operations
repo = get_approval_repository(document)
current = repo.get_current_approval()  # O(1) lookup
progress = repo.get_workflow_progress()  # No additional queries

# ✅ RECOMMENDED: Batch operations when possible
summary = get_approval_summary(document)  # Single call for complete data

# ❌ AVOID: Multiple individual utility calls
current = get_current_approval(document)    # Query 1
next_step = get_next_approval(document)     # Query 2  
flow = get_approval_flow(document)          # Query 3
```

### Cache Management
The system includes multi-level caching:
- **LRU Cache**: For ContentType lookups (128 entries)
- **Django Cache**: For flow data (5-minute TTL)
- **Instance Cache**: Within repository objects

```python
# Clear cache when needed (testing/debugging)
from approval_workflow.utils import ApprovalRepository
ApprovalRepository.clear_cache_for_object(document)
```

## 🧪 Testing

Run the test suite:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest
```

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

## 🙏 Acknowledgments

- Django team for the amazing framework
- MPTT library for hierarchical model support
- Django REST Framework for API capabilities

---

For more detailed documentation and examples, visit our [documentation](https://github.com/Codxi-Co/django-approval-workflow).