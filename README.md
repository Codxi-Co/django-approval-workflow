# Django Approval Workflow

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-5.2%2B-green)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A powerful, flexible, and reusable Django package for implementing dynamic multi-step approval workflows in your Django applications.

## ✨ Features

- **Dynamic Workflow Creation**: Create approval workflows for any Django model using GenericForeignKey
- **Multi-Step Approval Process**: Support for sequential approval steps with role-based assignments
- **Role-Based Permissions**: Hierarchical role support using MPTT (Modified Preorder Tree Traversal)
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
from approval_workflow.utils import can_user_approve
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

# Check if user can approve
first_step = flow.instances.get(step_number=1)
if can_user_approve(first_step, employee):
    # Advance the workflow
    next_step = advance_flow(
        instance=first_step,
        action="approved",
        user=employee,
        comment="Looks good to me!"
    )
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
```


### Custom Handlers

Create custom handlers for workflow events:

```python
# myapp/approval.py
from approval_workflow.handlers import BaseApprovalHandler

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
```

## 🏗️ Models

### ApprovalFlow
Central model that links to any Django model via GenericForeignKey.

### ApprovalInstance
Represents individual steps in the approval process with status tracking.

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