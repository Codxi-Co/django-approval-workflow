# Release Notes - Version 0.9.0

**Release Date:** January 13, 2025

## 🎉 Major Release: Enhanced Role Strategies & Enterprise Features

We're thrilled to announce **django-approval-workflow 0.9.0**, a major milestone release that transforms the package into a **world-class enterprise solution**. This release delivers advanced approval strategies, comprehensive SLA management, full internationalization support with Arabic translations, and production-ready logging capabilities.

---

## 🚀 What's New

### ✨ Advanced Role-Based Approval Strategies

Enterprise workflows often require complex approval logic beyond simple "anyone" or "consensus" rules. This release introduces **5 powerful new strategies**:

#### 🎯 QUORUM Strategy
**"2 out of 5 users must approve"** - Perfect for committee decisions.

```python
start_flow(
    obj=contract,
    steps=[{
        "step": 1,
        "assigned_role": committee_role,
        "role_selection_strategy": RoleSelectionStrategy.QUORUM,
        "quorum_count": 2,  # Need 2 approvals
        "quorum_total": 5,  # Out of 5 users
    }]
)
```

**Features:**
- ✅ Flexible quorum requirements (any N out of M)
- ✅ Automatic cancellation of remaining instances when quorum reached
- ✅ Progress tracking in logs and extra_fields
- ✅ Use cases: Finance committee, procurement board, change control board

#### 📊 MAJORITY Strategy
**">50% of users must approve"** - Ideal for democratic decisions.

```python
start_flow(
    obj=resolution,
    steps=[{
        "step": 1,
        "assigned_role": board_members_role,
        "role_selection_strategy": RoleSelectionStrategy.MAJORITY,
        # Automatically calculates >50% requirement
    }]
)
```

**Features:**
- ✅ Auto-calculates majority threshold based on role user count
- ✅ Works with any group size (3 users = 2 approvals, 5 users = 3 approvals)
- ✅ Use cases: Board approvals, steering committees, governance decisions

#### 📈 PERCENTAGE Strategy
**"66.67% must approve"** - Supermajority requirements.

```python
start_flow(
    obj=strategic_plan,
    steps=[{
        "step": 1,
        "assigned_role": stakeholders_role,
        "role_selection_strategy": RoleSelectionStrategy.PERCENTAGE,
        "percentage_required": 66.67,  # 2/3 supermajority
    }]
)
```

**Features:**
- ✅ Configurable percentage (e.g., 66.67 for 2/3, 75.00 for 3/4)
- ✅ Decimal precision support (up to 2 decimal places)
- ✅ Use cases: Stakeholder approvals, constitutional requirements, supermajority votes

#### 🏢 HIERARCHY_UP Strategy
**"Escalate through N levels of management"** - Perfect for deal approvals.

```python
# Deal approval workflow with dynamic levels
def create_deal_approval_workflow(deal):
    # Determine levels based on deal amount
    if deal.amount < 50000:
        levels = 1  # Manager only
    elif deal.amount < 100000:
        levels = 2  # Manager + Director
    else:
        levels = 3  # Manager + Director + VP

    return start_flow(
        obj=deal,
        steps=[{
            "step": 1,
            "assigned_role": account_manager_role,
            "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
            "hierarchy_levels": levels,
            "hierarchy_base_user": deal.account_manager,
        }]
    )
```

**Features:**
- ✅ Walks up MPTT role hierarchy automatically
- ✅ Dynamic level selection based on business logic
- ✅ Perfect for: Deal approvals, purchase orders, expense reports
- ✅ Eliminates manual workflow definitions for each deal size

#### 🔄 HIERARCHY_CHAIN Strategy
**"Full vertical chain approval"** - Everyone in the chain must approve.

```python
start_flow(
    obj=purchase_order,
    steps=[{
        "step": 1,
        "assigned_role": employee_role,
        "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_CHAIN,
        "hierarchy_levels": 3,  # Employee → Manager → Director → VP
        "hierarchy_base_user": purchase_order.requester,
    }]
)
```

**Features:**
- ✅ Base user + all N levels up must approve
- ✅ Complete vertical approval chain
- ✅ Use cases: Purchase requisitions, travel requests, time-off approvals

---

### ⏰ SLA & Timeout Management

Never miss a deadline with comprehensive SLA tracking and automatic timeout actions.

#### Due Dates
Set deadlines for approval steps:
```python
start_flow(
    obj=request,
    steps=[{
        "step": 1,
        "assigned_to": manager,
        "due_date": datetime.now() + timedelta(days=3),
    }]
)
```

#### Auto-Escalation on Timeout
Configure automatic actions when deadlines are missed:
```python
start_flow(
    obj=request,
    steps=[{
        "step": 1,
        "assigned_to": manager,
        "due_date": datetime.now() + timedelta(days=2),
        "escalation_on_timeout": True,
        "timeout_action": "escalate",  # or "delegate", "auto_approve", "reject"
    }]
)
```

**Features:**
- ✅ Due date tracking for compliance
- ✅ Reminder flag to prevent duplicate notifications
- ✅ Auto-escalation on timeout
- ✅ Configurable timeout actions (escalate/delegate/auto_approve/reject)
- ✅ Prevents stalled approvals

---

### 🔁 Delegation & Escalation Tracking

Full audit trail for compliance and reporting.

#### Delegation Chain History
Track every delegation with complete history:
```python
# Delegate approval
advance_flow(
    document,
    'delegated',
    manager,
    delegate_to=acting_manager,
    comment="Delegating while on vacation"
)

# Delegation chain is automatically tracked:
# [
#   {
#     "from_user": "manager",
#     "to_user": "acting_manager",
#     "timestamp": "2024-01-15T10:30:00Z",
#     "reason": "Delegating while on vacation"
#   }
# ]
```

#### Escalation Level Tracking
Monitor escalation progression:
```python
# Tracks escalation level: 0 → 1 → 2 → 3
# Prevents runaway escalations with max_escalation_level
```

**Features:**
- ✅ Complete delegation history (from_user, to_user, timestamp, reason)
- ✅ Escalation level tracking (current + max)
- ✅ JSONField storage for flexible data structures
- ✅ Compliance-ready audit trails

---

### 🔀 Parallel Approval Support

Run multiple approval tracks simultaneously for faster workflows.

```python
start_flow(
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
```

**Features:**
- ✅ Concurrent approval tracks
- ✅ Parallel group tracking
- ✅ Configurable parallel requirements
- ✅ Use cases: Technical + business approval, legal + finance review

---

### 🌍 Full Internationalization (i18n) Support

**✅ Arabic Translations Included Out of the Box!**

We're proud to include complete Arabic translations, making django-approval-workflow accessible to Arabic-speaking developers and users worldwide.

#### Available Languages
- 🇺🇸 English (en) - Default
- 🇸🇦 Arabic (ar) - Complete translation included

#### Example Arabic Translations

| English | Arabic |
|---------|---------|
| "Approval Flow" | "مسار الموافقة" |
| "Anyone with role can approve" | "أي شخص لديه الدور يمكنه الموافقة" |
| "Require N out of M users to approve" | "يتطلب موافقة N من أصل M مستخدمين" |
| "Escalate through N levels" | "التصعيد من خلال N مستويات" |
| "Delegation" | "تفويض" |
| "Auto Reject" | "رفض تلقائي" |

#### Configuration

```python
# settings.py
LANGUAGE_CODE = 'ar'  # Set Arabic as default
USE_I18N = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
    BASE_DIR / 'approval_workflow' / 'locale',
]

MIDDLEWARE = [
    'django.middleware.locale.LocaleMiddleware',  # Enable language switching
]
```

#### Adding More Languages

Easy to extend with additional languages:
1. Create locale directory: `approval_workflow/locale/<lang_code>/LC_MESSAGES/`
2. Copy and translate the `django.po` file
3. Compile: `msgfmt -o django.mo django.po`

**Features:**
- ✅ All role selection strategies translated (13 strategies)
- ✅ All approval types translated (4 types)
- ✅ All field labels and help text translated
- ✅ All timeout actions translated
- ✅ Django gettext_lazy implementation
- ✅ Easy language switching
- ✅ Locale middleware integration

---

### 📝 Enhanced Logging System

Production-ready logging with emoji indicators for clarity.

#### Structured Log Format

```python
# Log examples:
[APPROVAL_WORKFLOW] ✨ NEW INSTANCE CREATED | Flow ID: 123 | Step: 1 | Status: CURRENT | ...
[APPROVAL_WORKFLOW] ✅ APPROVED | Flow ID: 123 | Step: 1 | Action User: john_doe | ...
[APPROVAL_WORKFLOW] ❌ REJECTED | Flow ID: 123 | Step: 2 | Action User: jane_smith | ...
[APPROVAL_WORKFLOW] 🔄 DELEGATED | Flow ID: 123 | From: manager | To: acting_manager | ...
[APPROVAL_WORKFLOW] ⬆️ ESCALATED | Flow ID: 123 | Level: 1 → 2 | ...
```

#### Emoji Indicators
- ✨ NEW INSTANCE CREATED
- ✅ APPROVED
- ❌ REJECTED
- 🔄 DELEGATED
- ⬆️ ESCALATED
- 📤 RESUBMISSION REQUESTED
- 🎯 ROLE-BASED STEP ACTIVATED
- ⏰ TIMEOUT/ESCALATION tracking

**Features:**
- ✅ Comprehensive event tracking
- ✅ Flow ID, step number, status, assigned user tracking
- ✅ Action user, approval type, strategy tracking
- ✅ Extra fields and metadata tracking
- ✅ Perfect for debugging and monitoring

---

## 🗄️ Database Changes

### 13 New Model Fields on ApprovalInstance

**Quorum Fields:**
- `quorum_count` (PositiveIntegerField) - Number of approvals required
- `quorum_total` (PositiveIntegerField) - Total number of users for quorum calculation

**Percentage Field:**
- `percentage_required` (DecimalField, max 5 digits, 2 decimal places) - Percentage required

**Hierarchy Fields:**
- `hierarchy_levels` (PositiveIntegerField) - Number of hierarchy levels to escalate
- `hierarchy_base_user` (ForeignKey to User) - Base user for hierarchical approval

**SLA & Timeout Fields:**
- `due_date` (DateTimeField) - Deadline for approval step
- `reminder_sent` (BooleanField) - Whether reminder notification has been sent
- `escalation_on_timeout` (BooleanField) - Whether to auto-escalate on timeout
- `timeout_action` (CharField) - Action to take when timeout is reached

**Delegation & Escalation Fields:**
- `delegation_chain` (JSONField) - Track delegation history
- `escalation_level` (PositiveIntegerField, default=0) - Current escalation level
- `max_escalation_level` (PositiveIntegerField, default=3) - Maximum escalation level

**Parallel Approval Fields:**
- `parallel_group` (CharField, max_length=100) - Group identifier for parallel tracks
- `parallel_required` (BooleanField, default=False) - Whether this step must complete

### 2 New Performance Indexes

- `appinst_due_date_status_idx` - Due date + status index for SLA queries
- `appinst_parallel_idx` - Flow + parallel_group + status index for parallel queries

### Migration

**Single Atomic Migration:** `0003_enhanced_features_combined.py`
- Zero downtime deployment
- Rollback-safe
- All new fields are optional (null=True, blank=True)

---

## 🧪 Testing

### 29 New Tests (128 Total Tests, Up from 99)

Comprehensive test coverage for all new features:

- ✅ Quorum strategy completion and progress tracking
- ✅ Majority strategy calculation
- ✅ Percentage strategy with decimal precision
- ✅ Hierarchy escalation (single and multiple levels)
- ✅ Hierarchy chain approval
- ✅ Delegation chain tracking
- ✅ Escalation level tracking
- ✅ Parallel approval tracks
- ✅ SLA due date tracking
- ✅ Timeout actions (escalate, delegate, auto_approve, reject)
- ✅ Translation support validation
- ✅ Enhanced logging verification

**All 128 tests passing!** ✅

---

## 📚 Documentation

### New Documentation

- **ENHANCED_FEATURES.md** (2,500+ lines)
  - Complete strategy explanations with examples
  - Configuration examples for all features
  - Migration guide
  - Testing guide
  - Translation support guide
  - Performance optimization notes

### Updated Documentation

- **README.md** - Comprehensive updates:
  - Enhanced Role-Based Approval Strategies section
  - Real-world use cases (Deal approval, Budget control)
  - SLA & timeout management examples
  - Translation support section (English + Arabic)
  - Updated test count: 128 tests
  - Updated "Key Improvements" section

---

## 💼 Enterprise Use Cases

### Deal Approval Workflow

```python
def create_deal_approval_workflow(deal):
    # Dynamic levels based on deal amount
    levels = 1 if deal.amount < 50000 else 2 if deal.amount < 100000 else 3

    return start_flow(
        obj=deal,
        steps=[{
            "step": 1,
            "assigned_role": account_manager_role,
            "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
            "hierarchy_levels": levels,
            "hierarchy_base_user": deal.account_manager,
        }]
    )
```

**Benefits:**
- ✅ Automatic routing based on deal size
- ✅ No manual workflow definitions for each tier
- ✅ Scalable to any deal amount range

### Budget Control Workflow

```python
def create_budget_control_flow(budget_request):
    steps = [
        {
            "step": 1,
            "assigned_to": budget_request.requester,
            "approval_type": ApprovalType.SUBMIT,
            "form": budget_request.form,
        }
    ]

    if budget_request.amount <= 5000:
        # Team lead approval
        steps.append({
            "step": 2,
            "assigned_role": team_lead_role,
            "role_selection_strategy": RoleSelectionStrategy.ANYONE,
        })
    elif budget_request.amount <= 20000:
        # Finance committee quorum (2 out of 5)
        steps.append({
            "step": 2,
            "assigned_role": finance_committee_role,
            "role_selection_strategy": RoleSelectionStrategy.QUORUM,
            "quorum_count": 2,
            "quorum_total": 5,
        })
    else:
        # Executive chain approval
        steps.append({
            "step": 2,
            "assigned_role": requester_role,
            "role_selection_strategy": RoleSelectionStrategy.HIERARCHY_UP,
            "hierarchy_levels": 2,
            "hierarchy_base_user": budget_request.requester,
        })

    return start_flow(obj=budget_request, steps=steps)
```

**Benefits:**
- ✅ Multi-tier approval based on amount
- ✅ Quorum-based checks for mid-range budgets
- ✅ Executive oversight for large budgets
- ✅ Flexible and maintainable

---

## 🔄 Backward Compatibility

**100% Backward Compatible** - All existing code continues to work unchanged.

- ✅ No breaking changes
- ✅ All new fields are optional (null=True, blank=True)
- ✅ Migration is rollback-safe
- ✅ Default values for all new fields
- ✅ Existing workflows require no modifications

---

## 🚀 Upgrade Path

### From 0.8.x to 0.9.0

**Step 1: Update the package**
```bash
pip install django-approval-workflow==0.9.0
```

**Step 2: Run migrations**
```bash
python manage.py migrate approval_workflow
```

**Step 3: Optional - Enable Arabic support**
```python
# settings.py
LANGUAGE_CODE = 'ar'  # Optional: Set Arabic as default
USE_I18N = True

LOCALE_PATHS = [
    BASE_DIR / 'approval_workflow' / 'locale',
]
```

**Step 4: Optional - Add new fields to workflows**
```python
# Existing workflows continue to work
# New features can be adopted gradually
```

**That's it!** Your existing workflows will continue to work unchanged.

---

## 📊 Impact Summary

### For Developers ✅

- ✅ Enterprise-grade approval strategies without custom code
- ✅ Flexible SLA and timeout management
- ✅ Full internationalization support (Arabic included)
- ✅ Enhanced logging for debugging and monitoring
- ✅ Comprehensive documentation and examples
- ✅ 128 tests ensuring reliability

### For Businesses ✅

- ✅ Complex approval workflows (hierarchy, quorum, majority)
- ✅ Compliance tracking (delegation chains, escalation history)
- ✅ Time-based approvals (due dates, auto-actions)
- ✅ Multi-language support (English + Arabic)
- ✅ Parallel approval tracks for faster workflows
- ✅ Production-ready with comprehensive logging

### For Operations ✅

- ✅ Performance optimized with strategic indexes
- ✅ Easy deployment with single migration
- ✅ 100% backward compatible
- ✅ Zero downtime deployment
- ✅ Rollback-safe migration

---

## 🙏 Acknowledgments

This release represents a significant milestone for django-approval-workflow. We've listened to your feedback and built enterprise-grade features that address real-world approval workflow challenges.

**Special thanks to:**
- All users who provided feedback on role-based approval strategies
- The community for testing and reporting issues
- Contributors who helped with translations and documentation

---

## 📞 Support

- **Documentation**: [README.md](README.md) and [ENHANCED_FEATURES.md](ENHANCED_FEATURES.md)
- **Issues**: [GitHub Issues](https://github.com/Codxi-Co/django-approval-workflow/issues)
- **Email**: info@codxi.com

---

## 🔮 What's Next

Looking ahead to future releases:

- **v0.10.0**: Enhanced analytics and reporting dashboard
- **v0.11.0**: Integration with popular notification systems (Slack, Teams, Email)
- **v0.12.0**: Workflow templates and visual workflow builder

**Stay tuned!** 🚀

---

**Version:** 0.9.0
**Release Date:** January 13, 2025
**Author:** Mohamed Salah
**Email:** info@codxi.com
**GitHub**: [Codxi-Co](https://github.com/Codxi-Co)

---

**Happy Approving!** ✅
