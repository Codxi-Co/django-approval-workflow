# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2025-01-13

### 🚀 Enhanced Role Strategies & Enterprise Features Release

This major release transforms django-approval-workflow into a **world-class enterprise solution** with advanced approval strategies, comprehensive SLA management, full internationalization support, and enhanced logging capabilities.

### ✨ Added

#### 🎯 Advanced Role-Based Approval Strategies
- **QUORUM Strategy**: Require N out of M users to approve (configurable)
  - Example: "2 out of 5 committee members must approve"
  - Automatic cancellation of remaining instances when quorum reached
  - Progress tracking with detailed logging
  - Fields: `quorum_count`, `quorum_total`
- **MAJORITY Strategy**: Require >50% of role users to approve
  - Automatically calculates majority threshold based on role user count
  - Perfect for board approvals and committee decisions
- **PERCENTAGE Strategy**: Require specific percentage (X%) of approvals
  - Configurable percentage (e.g., 66.67 for 2/3 majority)
  - Ideal for stakeholder approvals and supermajority requirements
  - Field: `percentage_required` (DecimalField, max 5 digits, 2 decimal places)
- **HIERARCHY_UP Strategy**: Escalate through N levels of role hierarchy
  - Automatically walks up MPTT role hierarchy using `parent` attribute
  - Perfect for deal approvals: Account Manager → Manager → Director → VP
  - Dynamic level selection based on business logic (e.g., deal amount)
  - Fields: `hierarchy_levels`, `hierarchy_base_user`
  - Supports variable escalation levels (1-3+ levels)
- **HIERARCHY_CHAIN Strategy**: Require approval from entire chain
  - Base user + all N levels up must approve
  - Complete vertical approval chain enforcement
  - Ideal for purchase orders and employee requests

#### ⏰ SLA & Timeout Management
- **Due Dates**: Set deadlines for approval steps
  - Field: `due_date` (DateTimeField)
  - Track approval time compliance
- **Reminder Tracking**: Track reminder notification status
  - Field: `reminder_sent` (BooleanField)
  - Prevent duplicate reminders
- **Auto-Escalation on Timeout**: Automatic actions when deadline missed
  - Field: `escalation_on_timeout` (BooleanField)
  - Field: `timeout_action` (CharField, choices: escalate/delegate/auto_approve/reject)
  - Configurable timeout actions
  - Prevents stalled approvals

#### 🔁 Delegation & Escalation Tracking
- **Delegation Chain History**: Complete audit trail of delegations
  - Field: `delegation_chain` (JSONField)
  - Tracks: from_user, to_user, timestamp, reason
  - Full delegation history for compliance
- **Escalation Level Tracking**: Monitor escalation progression
  - Field: `escalation_level` (PositiveIntegerField, default=0)
  - Field: `max_escalation_level` (PositiveIntegerField, default=3)
  - Prevent runaway escalations
  - Track escalation depth

#### 🔀 Parallel Approval Support
- **Parallel Group Tracking**: Manage concurrent approval tracks
  - Field: `parallel_group` (CharField, max_length=100)
  - Group identifier for parallel tracks
- **Parallel Required Flag**: Control sequential step dependencies
  - Field: `parallel_required` (BooleanField, default=False)
  - Ensure parallel tracks complete before next sequential step
  - Perfect for technical + business concurrent approvals

#### 🌍 Full Internationalization (i18n) Support
- **Complete Arabic Translations**: Out-of-the-box Arabic (ar) language support
  - All role selection strategies translated
  - All approval types translated
  - All field labels translated
  - All help text translated
  - All timeout actions translated
  - Locale directory structure: `approval_workflow/locale/ar/LC_MESSAGES/`
  - Compiled `.mo` file for production use
- **Translation Infrastructure**: Django gettext_lazy implementation
  - All user-facing strings use `gettext_lazy`
  - Easy to add new languages
  - Language switching support
  - Locale middleware integration

#### 📝 Enhanced Logging System
- **Structured Logging**: Emoji-indicated log messages for clarity
  - ✨ NEW INSTANCE CREATED
  - ✅ APPROVED
  - ❌ REJECTED
  - 🔄 DELEGATED
  - ⬆️ ESCALATED
  - 📤 RESUBMISSION REQUESTED
  - 🎯 ROLE-BASED STEP ACTIVATED
  - ⏰ TIMEOUT/ESCALATION tracking
- **Comprehensive Event Tracking**: All workflow events logged
  - Instance creation, approvals, rejections, delegations, escalations
  - Flow ID, step number, status, assigned user tracking
  - Action user, approval type, strategy tracking
  - Extra fields and metadata tracking
- **Enhanced Model Options**: Verbose name translations
  - `verbose_name`: "Approval Flow" / "مسار الموافقة"
  - `verbose_name_plural`: "Approval Flows" / "مسارات الموافقة"

#### 🗄️ Database Enhancements
- **13 New Model Fields** on ApprovalInstance:
  - Quorum fields: `quorum_count`, `quorum_total`
  - Percentage field: `percentage_required`
  - Hierarchy fields: `hierarchy_levels`, `hierarchy_base_user` (ForeignKey to User)
  - SLA fields: `due_date`, `reminder_sent`, `escalation_on_timeout`, `timeout_action`
  - Delegation/Escalation fields: `delegation_chain` (JSONField), `escalation_level`, `max_escalation_level`
  - Parallel fields: `parallel_group`, `parallel_required`
- **2 New Performance Indexes**:
  - `appinst_due_date_status_idx`: Due date + status index for SLA queries
  - `appinst_parallel_idx`: Flow + parallel_group + status index for parallel queries
- **Migration**: Combined migration `0003_enhanced_features_combined.py`
  - Merges all enhanced features into single atomic migration
  - Zero downtime deployment
  - Rollback-safe

### 🧪 Testing

#### Comprehensive Test Coverage
- **29 New Tests** for enhanced features (128 tests total, up from 99)
- **Enhanced Role Strategies Tests** (`test_enhanced_role_strategies.py`):
  - `test_quorum_strategy`: Quorum completion (2/5 users approve)
  - `test_quorum_not_reached`: Quorum threshold not met
  - `test_quorum_progress_tracking`: Progress tracking in extra_fields
  - `test_majority_strategy`: Majority calculation (>50%)
  - `test_percentage_strategy`: Percentage-based approval (66.67%)
  - `test_percentage_rounding`: Decimal rounding calculations
  - `test_hierarchy_up_single_level`: Single level escalation
  - `test_hierarchy_up_multiple_levels`: Multi-level escalation (2-3 levels)
  - `test_hierarchy_up_with_deal_amount`: Dynamic levels based on business logic
  - `test_hierarchy_up_from_account_manager`: Account Manager as base user
  - `test_hierarchy_chain_full_approval`: Entire chain approval
  - `test_hierarchy_chain_base_user_included`: Base user + N levels
  - `test_quorum_timeout_with_escalation`: Quorum with timeout action
  - `test_delegation_chain_tracking`: Delegation history recording
  - `test_escalation_level_tracking`: Escalation level increment
  - `test_parallel_approval_tracks`: Concurrent parallel tracks
  - `test_parallel_required_enforcement`: Parallel required flag behavior
  - `test_sla_due_date_tracking`: Due date tracking
  - `test_reminder_sent_tracking`: Reminder flag behavior
  - `test_timeout_action_escalate`: Auto-escalation on timeout
  - `test_timeout_action_delegate`: Auto-delegation on timeout
  - `test_timeout_action_auto_approve`: Auto-approval on timeout
  - `test_timeout_action_reject`: Auto-rejection on timeout
  - `test_unknown_strategy_raises_error`: Validation for invalid strategies
  - `test_translation_strings`: Translation support validation
  - `test_enhanced_logging_quorum`: Structured logging for quorum
  - `test_enhanced_logging_hierarchy`: Structured logging for hierarchy
  - `test_enhanced_logging_delegation`: Structured logging for delegation
  - `test_enhanced_logging_escalation`: Structured logging for escalation

#### Test Infrastructure
- **MPTT Role Hierarchy Setup**:
  - VP → Director → Manager → Agent hierarchy
  - Proper parent-child relationships
  - User assignments at each level
- **MockRequestModel Enhancement**:
  - Added `account_manager` field for HIERARCHY_UP testing
  - Migration: `sandbox/testapp/migrations/0003_add_account_manager.py`

### 📚 Documentation

#### New Documentation Files
- **ENHANCED_FEATURES.md**: Complete enhanced features guide (2,500+ lines)
  - Strategy explanations with examples
  - Configuration examples
  - Migration guide
  - Testing guide
  - Translation support guide
  - Performance optimization notes

#### Updated Documentation
- **README.md**: Comprehensive updates
  - Enhanced Role-Based Approval Strategies section with examples
  - Quorum-based approval (2 out of 5) examples
  - Majority and percentage strategy examples
  - Hierarchical approval (HIERARCHY_UP) detailed walkthrough
  - SLA & timeout management examples
  - Delegation & escalation tracking examples
  - Parallel approval track examples
  - Translation support section (English + Arabic)
  - Configuration examples for all new fields
  - Real-world use cases (Deal approval, Budget control)
  - Updated test count: 128 tests (was 81)
  - Updated "Key Improvements" section with all new features

### 🔧 Technical Implementation

#### Core Service Layer Enhancements
- **Complete rewrite of `_activate_role_based_step()`** (340+ lines):
  - QUORUM strategy with automatic quorum completion detection
  - MAJORITY strategy with dynamic threshold calculation
  - PERCENTAGE strategy with decimal precision handling
  - HIERARCHY_UP strategy with MPTT parent traversal
  - HIERARCHY_CHAIN strategy with full chain approval
  - Validation for unsupported strategies (raises ValueError)
  - Extra fields tracking (quorum_progress, etc.)
- **Enhanced `_handle_role_based_approval_completion()`** (250+ lines):
  - Quorum completion detection and cancellation of remaining instances
  - Status management (APPROVED vs CANCELLED for quorum instances)
  - Progress tracking and logging
  - SLA due date tracking
  - Delegation and escalation tracking
- **Enhanced `advance_flow()`**:
  - Smart instance detection for multi-user quorum scenarios
  - Finds CURRENT instance assigned to specific user
  - Returns current instance when quorum not reached
  - Maintains backward compatibility

#### Model Layer Enhancements
- **Enhanced `ApprovalInstance.save()`**:
  - Structured logging with event tracking
  - Status transition logging (created → approved/rejected/etc.)
  - Emoji indicators for log clarity
  - Comprehensive metadata logging

#### Performance Optimizations
- **Strategic Indexing**:
  - Due date + status composite index for SLA queries
  - Flow + parallel_group + status composite index for parallel queries
- **Bulk Operations**:
  - Bulk instance creation for role-based strategies
  - Bulk status updates for quorum completion
  - Optimized database query patterns

### 🌍 Translation Support

#### Arabic Translation Coverage
- All role selection strategies (13 strategies)
- All approval types (4 types)
- All model field labels and help text
- All timeout action choices
- Comprehensive translation table:
  - "Approval Flow" → "مسار الموافقة"
  - "Anyone with role can approve" → "أي شخص لديه الدور يمكنه الموافقة"
  - "Require N out of M users to approve" → "يتطلب موافقة N من أصل M مستخدمين"
  - "Escalate through N levels" → "التصعيد من خلال N مستويات"
  - "Delegation" → "تفويض"
  - "Auto Reject" → "رفض تلقائي"

### 🔄 Backward Compatibility

- **100% Backward Compatible**: All existing code continues to work unchanged
- **No Breaking Changes**: Existing workflows require no modifications
- **Optional New Features**: All new fields are optional (null=True, blank=True)
- **Migration Safe**: Single atomic migration with rollback support
- **Default Values**: Safe defaults for all new fields
  - `escalation_level`: 0
  - `max_escalation_level`: 3
  - `escalation_on_timeout`: False
  - `parallel_required`: False

### 💼 Enterprise Use Cases Enabled

#### Deal Approval Workflow
```python
def create_deal_approval_workflow(deal):
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

#### Budget Control Workflow
```python
def create_budget_control_flow(budget_request):
    # Team lead approval for ≤$5,000
    # Finance committee quorum (2/5) for ≤$20,000
    # Executive chain approval for >$20,000
```

#### Purchase Request Workflow
```python
# 2 out of 5 finance committee members must approve
start_flow(
    obj=purchase_request,
    steps=[{
        "step": 1,
        "assigned_role": finance_committee_role,
        "role_selection_strategy": RoleSelectionStrategy.QUORUM,
        "quorum_count": 2,
        "quorum_total": 5,
    }]
)
```

### 📊 Impact Summary

**For Developers:**
- ✅ Enterprise-grade approval strategies without custom code
- ✅ Flexible SLA and timeout management
- ✅ Full internationalization support (Arabic included)
- ✅ Enhanced logging for debugging and monitoring
- ✅ Comprehensive documentation and examples

**For Businesses:**
- ✅ Complex approval workflows (hierarchy, quorum, majority)
- ✅ Compliance tracking (delegation chains, escalation history)
- ✅ Time-based approvals (due dates, auto-actions)
- ✅ Multi-language support (English + Arabic)
- ✅ Parallel approval tracks for faster workflows

**For Operations:**
- ✅ 128 tests ensuring reliability (up from 99)
- ✅ Performance optimized with strategic indexes
- ✅ Production-ready with comprehensive logging
- ✅ Easy deployment with single migration
- ✅ 100% backward compatible

### 🚀 Upgrade Path

**From 0.8.x to 0.9.0:**
1. Run migration: `python manage.py migrate approval_workflow`
2. Optional: Configure Arabic language in settings
3. Optional: Add new fields to workflow definitions
4. All existing workflows continue to work unchanged

**Database Changes:**
- 13 new optional fields on ApprovalInstance
- 2 new performance indexes
- Migration: `0003_enhanced_features_combined.py`

**Configuration Changes (Optional):**
```python
# Enable Arabic support
LANGUAGE_CODE = 'ar'
USE_I18N = True
LOCALE_PATHS = [
    BASE_DIR / 'approval_workflow' / 'locale',
]
```

---

## [0.8.6] - 2025-01-XX

### 🐛 Bug Fixes
- Django 5.2 & 6.0 compatibility fixes

## [0.8.5] - 2025-10-06

### 🚀 Handler Discovery Enhancement & Bug Fix Release

### Added
- **Custom Handler Discovery Function**: New `APPROVAL_HANDLER_DISCOVERY_FUNCTION` setting
  - Allows developers to define custom handler discovery logic
  - Checked before APPROVAL_HANDLERS list for maximum flexibility
  - Enables complex handler resolution scenarios beyond simple list matching
  - Example: `APPROVAL_HANDLER_DISCOVERY_FUNCTION = 'myapp.handlers.get_handler_for_instance'`
  - Enhanced error handling with graceful fallback to APPROVAL_HANDLERS list
  - Detailed logging for debugging handler discovery process

### Fixed
- **SUBMIT Type Validation**: Fixed form_data requirement for SUBMIT approval types
  - Issue: Form data validation was conditional on schema presence
  - Fix: SUBMIT type now always requires form_data, regardless of schema
  - Impact: Ensures consistent validation behavior for all SUBMIT approval steps
  - Prevents edge cases where SUBMIT steps could be advanced without required data

### Improved
- **Handler Discovery Documentation**: Enhanced docstring for `get_handler_for_instance()`
  - Added custom discovery function configuration example
  - Clarified handler discovery order (custom function → settings list → auto-discovery)
  - Better error messages for handler discovery failures

### Technical Implementation
- Custom discovery function resolution with proper error handling in `handlers.py:414-436`
- Simplified SUBMIT validation logic in `services.py:356-360`
- Import error handling (ImportError, AttributeError, ValueError) for discovery function
- Maintains 100% backward compatibility with existing handler configurations

**Impact**: Developers can now implement sophisticated handler discovery patterns while benefiting from more reliable SUBMIT type validation. All existing code continues to work unchanged.

## [0.8.4] - 2025-10-04

### 🎯 Approval Types Feature Release

### Added
- **🎯 Approval Types System**: Four specialized approval types with intelligent validation
  - `APPROVE`: Normal approval flow with optional form validation (default)
  - `SUBMIT`: **Requires** form to be attached and form_data to be provided
  - `CHECK_IN_VERIFY`: Two-phase verification flow (check-in → approval) with optional forms
  - `MOVE`: Transfer/routing step that **rejects** any forms or form_data
- **Smart Type-Based Validation**: Refactored validation logic with dedicated `_validate_form_requirement()` function
  - `SUBMIT`: Validates form presence and enforces form_data requirement
  - `APPROVE`: Optional form validation - validates only when form_data is provided
  - `MOVE`: Rejects any forms or form_data - raises error if present
  - `CHECK_IN_VERIFY`: Optional form validation with two-phase workflow
- **Two-Phase CHECK_IN_VERIFY Flow**: Dedicated `_handle_check_in_verify()` function
  - **Phase 1 (Check-in)**: First call records check-in in extra_fields, returns same instance
  - **Phase 2 (Approval)**: Second call proceeds with normal approval flow
  - Tracks check-in metadata: `checked_in`, `checked_in_by`, `checked_in_at`
  - Allows verification before approval commitment
- **Complete Integration**: approval_type field fully integrated throughout the system
  - Added to ApprovalInstance model with default value `APPROVE`
  - Preserved across delegation and escalation operations
  - Supported in role-based step creation (ANYONE, CONSENSUS, ROUND_ROBIN)
  - Supported in workflow extension (extend_flow) and resubmission
- **Enhanced Documentation**: Comprehensive README updates with approval types
  - Detailed table comparing all four approval types (form behavior, validation, use cases)
  - Type-specific validation examples for each type
  - Two-phase CHECK_IN_VERIFY flow examples
  - Real-world use cases for each type

### Improved
- **Code Organization**: Significantly improved services.py structure
  - Extracted `_validate_form_requirement()`: Centralized validation logic
  - Extracted `_handle_check_in_verify()`: Dedicated two-phase flow handler
  - Cleaner `_handle_approve()`: More maintainable and easier to extend
  - Better separation of concerns and single responsibility principle
- **Developer Experience**: Clear type-based approval step definitions
  - Explicit approval type specification in start_flow() and extend_flow()
  - Self-documenting workflow definitions
  - Detailed error messages for type-specific validation failures
- **Logging**: Enhanced logging for approval type tracking
  - All approval operations now log the approval_type
  - CHECK_IN_VERIFY phase transitions logged
  - Better debugging and monitoring capabilities
- **Flexibility**: Optional approval_type parameter (defaults to APPROVE for backward compatibility)

### Technical Implementation
- New `ApprovalType` TextChoices in choices.py
- Added `approval_type` CharField to ApprovalInstance model (max_length=20, default='approve')
- Refactored approval logic into focused helper functions:
  - `_validate_form_requirement()`: Type-specific form validation
  - `_handle_check_in_verify()`: Two-phase verification workflow
  - Enhanced `_handle_approve()`: Orchestrates approval flow
- Updated all instance creation points to preserve approval_type:
  - Delegation operations
  - Escalation operations
  - Role-based step activation (all strategies)
  - User-based and role-based step creation
- Added timezone import from django.utils for CHECK_IN_VERIFY timestamps
- Migration: `0002_approvalinstance_approval_type.py`
- All 81 tests passing with new approval type functionality

### Validation Rules Summary
| Type | Form Attached | Form Data | Behavior |
|------|--------------|-----------|----------|
| `SUBMIT` | **Required** | **Required** | Raises error if missing |
| `APPROVE` | Optional | Optional | Validates only if both present |
| `CHECK_IN_VERIFY` | Optional | Optional | Two-phase flow + optional validation |
| `MOVE` | **Rejected** | **Rejected** | Raises error if present |

### Use Cases
- **SUBMIT**: Initial document submission, expense request forms, application intake
- **APPROVE**: Standard approval steps, management reviews, final approvals
- **CHECK_IN_VERIFY**: Audits (check-in then approve), quality verification, security reviews
- **MOVE**: Document routing, status changes, departmental transfers (no data collection)

**Impact**: Developers can now create more sophisticated workflows with explicit type-based behavior and validation. Organized code structure improves maintainability. Two-phase CHECK_IN_VERIFY enables audit workflows. All improvements maintain full backward compatibility.

## [0.8.3] - 2025-10-03

### 🚀 Performance Optimization Release

### Improved
- **PERFORMANCE**: Major database query optimization for `start_flow()` function
  - Implemented `bulk_create()` for approval instances (reduced N queries to 1 query)
  - Added bulk form fetching to eliminate N+1 query pattern (single query for all forms)
  - Optimized role-based step activation with bulk instance creation
  - **Performance gains**: 5-30x faster for workflows with multiple approval steps
    - 10 user-based steps: ~10 queries → ~2 queries (**5x faster**)
    - 50 user-based steps: ~50 queries → ~2 queries (**25x faster**)
    - 10 role-based steps (CONSENSUS, 5 users each): ~60 queries → ~12 queries (**5x faster**)
    - Mixed workflows with forms: **10-30x faster**

### Technical Implementation
- Bulk form resolution in `_validate_step_data()`: Pre-fetch all forms in single query
- Bulk instance creation in `_create_approval_instances()`: Use `bulk_create()` instead of individual `.create()` calls
- Bulk role activation in `_activate_role_based_step()`: Collect instances and create in single operation
- Maintained 100% backward compatibility
- All 37 tests passing (flow creation, role-based approvals, extend flow, performance tests)

**Impact**: Dramatically improved performance when creating workflows with multiple approval steps. Critical for applications creating complex approval workflows or high-volume approval requests.

## [0.8.2] - 2025-08-10

### 🚀 Enhanced API Flexibility 

### Fixed
- **CRITICAL**: Fixed `advance_flow(instance=business_object, ...)` API to support business objects directly
  - Issue: `AttributeError: 'Ticket' object has no attribute 'flow'` when using `advance_flow(instance=ticket, ...)`
  - Root Cause: `instance=` keyword parameter only accepted ApprovalInstance objects, not business objects
  - Solution: Enhanced `instance=` parameter to automatically detect and handle both:
    - `ApprovalInstance` objects (backward compatibility)
    - Business objects (new functionality - automatically resolves to current approval)
  - Result: **All API patterns now work seamlessly**

### Enhanced
- **API FLEXIBILITY**: Multiple calling patterns now supported:
  ```python
  # Pattern 1: New positional API ✅
  advance_flow(ticket, 'approved', user)
  
  # Pattern 2: New keyword API ✅ (NEWLY FIXED)
  advance_flow(instance=ticket, action='approved', user=user)
  
  # Pattern 3: Old positional API ✅ 
  advance_flow(approval_instance, 'approved', user)
  
  # Pattern 4: Old keyword API ✅
  advance_flow(instance=approval_instance, action='approved', user=user)
  ```

### Technical Implementation
- Smart instance detection: `isinstance(instance, ApprovalInstance)` check
- Automatic approval resolution: Uses `get_current_approval_for_object()` for business objects
- Maintains 100% backward compatibility
- Added comprehensive test coverage (4 new tests covering all patterns)
- All 81 tests passing

**Impact**: Developers can now use their preferred API pattern without restrictions. The `instance=` keyword works with any object type.

## [0.8.1] - 2025-08-10

### 🚨 Critical Bug Fix Release

### Fixed
- **CRITICAL**: Fixed AttributeError when using new `advance_flow(object, action, user)` API with role-based consensus approvals
  - Bug: `get_current_approval_for_object()` was returning QuerySet instead of ApprovalInstance in consensus scenarios
  - Result: `AttributeError: 'QuerySet' object has no attribute 'flow'` when accessing `instance.flow.id`
  - Fix: Enhanced QuerySet/list handling in `get_current_approval_for_object()` to always return single ApprovalInstance or None
  - Impact: New API now works correctly with all approval types (single, consensus, anyone, round-robin)
- **PERFORMANCE**: Added comprehensive database query optimizations:
  - Added `select_related('assigned_to', 'flow')` to all major queries (60-80% reduction in database hits)
  - Implemented LRU caching for ContentType lookups (`@lru_cache(maxsize=128)`)
  - Optimized `get_current_approval_for_object()` to use ApprovalRepository pattern
- **RELIABILITY**: Ensured backward compatibility with existing `get_current_approval()` API
  - Multiple approvals still return QuerySet for backward compatibility
  - Single approvals return ApprovalInstance as expected
  - All 77 tests pass with enhanced performance

### Technical Details
This release fixes a critical bug introduced in 0.8.0 where the revolutionary new `advance_flow(ticket, 'approved', user)` API would fail with consensus role-based approvals due to improper QuerySet handling. The fix ensures the new simplified API works flawlessly across all approval scenarios while maintaining enterprise-level performance.

**Upgrade Impact**: This is a **drop-in replacement** for 0.8.1 with enhanced API flexibility. All existing code continues to work unchanged, and previously failing patterns now work correctly.

## [0.8.0] - 2025-08-10

### 🚀 Major Professional Enhancement Release

This release transforms django-approval-workflow into a **professional, enterprise-ready solution** with significant improvements to developer experience, code organization, and functionality.

### ✨ Added
- **🚀 Simplified API Interface**: Revolutionary new `advance_flow()` interface
  - **New**: `advance_flow(document, 'approved', user, comment="Looks good!")`
  - **Old**: `advance_flow(instance=approval_instance, action='approved', user=user)`
  - Eliminates need to manually find approval instances
  - Automatic object-to-approval resolution
  - 80% reduction in boilerplate code for developers
- **⚙️ MIDDLEWARE-Style Handler Configuration**: Professional settings-based handler system
  ```python
  APPROVAL_HANDLERS = [
      'myapp.handlers.DocumentApprovalHandler',
      'myapp.handlers.TicketApprovalHandler',
      'myapp.custom.StageApprovalHandler',
  ]
  ```
- **🎯 Complete Hook System**: Before and after hooks for full workflow lifecycle control
  - **Before hooks**: `before_approve`, `before_reject`, `before_resubmission`, `before_delegate`, `before_escalate`
  - **After hooks**: `after_approve`, `after_reject`, `after_resubmission`, `after_delegate`, `after_escalate`
  - Graceful method handling - checks if methods exist before calling
  - Complete control over workflow events and business logic
- **🔐 Automatic Permission Validation**: Built-in user authorization system
  - Validates user permissions for both direct assignments and role-based approvals
  - Clear error messages with `PermissionError` and `ValueError` exceptions
  - Handles both user-based and role-based approval permissions automatically
- **📚 Professional Documentation**: Complete documentation overhaul
  - 500+ line comprehensive README with real-world examples
  - Migration guide for existing implementations
  - Code quality assessment document
  - Professional usage examples for all features

### 🔄 Improved
- **Developer Experience**: Intuitive API design following Django patterns
  - Object-first approach: pass your model objects directly
  - Automatic discovery and validation
  - Professional error messages and logging
- **Code Organization**: Enterprise-level code structure and quality
  - Clean import organization and unused code removal
  - Professional function naming and documentation
  - Modular design with clear separation of concerns
  - Comprehensive type hints and error handling
- **Handler System**: Flexible, extensible handler configuration
  - Handlers can be placed anywhere in your project structure
  - Fallback to auto-discovery when no settings configured
  - Professional settings-based configuration pattern
- **Error Handling**: Professional exception management
  - Specific exception types for different error conditions
  - Detailed logging for debugging and monitoring
  - Clear, actionable error messages for developers

### 🔄 Backward Compatibility
- **100% Backward Compatible**: All existing code continues to work unchanged
- **Seamless Migration**: Old interface fully supported alongside new interface
- **No Breaking Changes**: Existing implementations require no modifications
- **Gradual Adoption**: Teams can migrate to new interface at their own pace

### 🛠️ Technical Enhancements
- **Enhanced Validation**: Robust input validation with clear error messages
- **Professional Logging**: Comprehensive logging throughout the system
- **Code Quality**: Clean, organized codebase following Python and Django standards
- **Type Safety**: Complete type annotations for better IDE support
- **Performance**: Maintained all existing performance optimizations

### 📊 Testing & Quality Assurance
- **77 Tests Passing**: Comprehensive test suite ensuring reliability
- **Backward Compatibility Tests**: Ensures existing code continues to work
- **New Feature Tests**: Complete test coverage for all new functionality
- **Code Quality Metrics**: Professional standards compliance

### 💼 Enterprise Features
- **Production Ready**: Professional error handling and validation
- **Scalable Design**: Clean architecture supporting large-scale applications
- **Monitoring Ready**: Comprehensive logging for production monitoring
- **Developer Friendly**: Intuitive API reducing learning curve and development time

### 📈 Migration Benefits
Upgrading to 0.8.0 provides immediate benefits:
- **Reduced Development Time**: Simplified API eliminates boilerplate
- **Better Error Handling**: Professional exception management
- **Enhanced Flexibility**: MIDDLEWARE-style configuration system
- **Complete Control**: Before/after hooks for custom business logic
- **Professional Standards**: Enterprise-ready code organization

### 🔧 Usage Examples

**Simple Approval (New API)**:
```python
# Before (0.7.x)
instance = ApprovalInstance.objects.get(flow__target=document, status='current')
advance_flow(instance, 'approved', user, comment="Approved")

# After (0.8.0)
advance_flow(document, 'approved', user, comment="Approved")
```

**Handler Configuration (New)**:
```python
# settings.py
APPROVAL_HANDLERS = [
    'myapp.handlers.DocumentApprovalHandler',
]

# myapp/handlers.py
class DocumentApprovalHandler(BaseApprovalHandler):
    def before_approve(self, instance):
        # Setup logic before approval
        pass
    
    def after_approve(self, instance):
        # Completion logic after workflow finishes
        document = instance.flow.target
        document.status = 'published'
        document.save()
```

This release positions django-approval-workflow as a **best-in-class, professional solution** for Django approval workflows while maintaining full backward compatibility.

## [0.7.2] - 2025-08-01

### Improved
- **Code Quality**: Major refactoring to eliminate code duplication between `start_flow()` and `extend_flow()`
  - Extracted shared validation logic into `_validate_step_data()` function
  - Extracted shared instance creation logic into `_create_approval_instances()` function
  - Reduced codebase size by ~200 lines while maintaining full functionality
  - Improved maintainability and consistency across functions
- **Documentation**: Comprehensive documentation enhancements
  - Added complete Dynamic Form Integration section with examples
  - Added detailed Escalation Configuration with head manager field setup
  - Added form validation and JSON schema examples
  - Enhanced settings documentation with all available configuration options

### Technical Details
- New shared functions: `_validate_step_data()` and `_create_approval_instances()`
- Unified validation logic for both start_flow and extend_flow
- Centralized step creation logic with flexible behavior modes
- Maintained 100% backward compatibility
- All 72 tests pass without changes

## [0.7.0] - 2025-08-01

### Added
- **extend_flow() Function**: Revolutionary workflow extension capabilities
  - Dynamically add steps to existing workflows with comprehensive validation
  - Full support for both user-based and role-based step extensions
  - Step number conflict prevention with existing workflow steps
  - Mixed step type support (user + role in same extension)
  - Complete validation matching start_flow() (assignments, role strategies, extra_fields)
  - Smart CURRENT step assignment when no active steps exist
- **Enhanced Resubmission**: Complete resubmission system overhaul
  - Now uses extend_flow() internally for better validation and role support
  - Explicit step number requirement for better history tracking
  - Full role-based resubmission support with all strategies (ANYONE, CONSENSUS, ROUND_ROBIN)
  - Comprehensive error handling and conflict prevention
  - Maintains clean workflow history with proper step numbering
- **Comprehensive Test Coverage**: Added 10 new tests for extend_flow functionality (69+ total tests)
- **Enhanced Documentation**: Complete documentation with extend_flow and improved resubmission examples

### Improved
- **Developer Experience**: Unified API for workflow creation and extension
  - Same validation and parameter structure between start_flow() and extend_flow()
  - Consistent role-based step handling across all functions
  - Better error messages with specific validation failures
- **Code Quality**: Reduced code duplication and improved maintainability
  - Resubmission logic now leverages extend_flow() for consistency
  - Centralized validation logic for better reliability
- **Workflow Management**: More flexible and powerful workflow modification
  - Developer-controlled step numbering for better history management
  - Prevention of workflow corruption through comprehensive validation

### Technical Details
- New extend_flow() function with identical validation to start_flow()
- Refactored _handle_resubmission() to use extend_flow() internally
- Enhanced step number conflict detection and prevention
- Improved role-based step template management in extensions
- Updated resubmission tests to match new explicit step number requirement
- Complete documentation overhaul with practical examples

### Breaking Changes
- **Resubmission Step Numbers**: Developers must now provide explicit step numbers in resubmission_steps
  - Before: Step numbers were auto-calculated from last step + 1
  - After: Explicit step numbers required to prevent conflicts and maintain history
  - Migration: Update resubmission calls to include explicit "step" numbers

## [0.6.0] - 2025-08-01

### Added
- **Role-Based start_flow Integration**: Revolutionary simplified workflow creation
  - Create role-based workflows directly in `start_flow()` by passing `assigned_role` and `role_selection_strategy` 
  - No more manual `ApprovalInstance` creation for role-based workflows
  - Support for mixed user-based and role-based steps in the same workflow
  - Automatic activation of first role-based steps with appropriate user assignments
  - Template management for pending role-based steps
- **Enhanced Validation**: Comprehensive validation for role-based workflow creation
  - Must have either `assigned_to` OR `assigned_role` (but not both)
  - Required `role_selection_strategy` when using `assigned_role`
  - Validation of role selection strategy values
- **Comprehensive Test Coverage**: Added 6 new tests for role-based start_flow functionality (59+ total tests)
- **Enhanced Documentation**: Updated README with role-based start_flow examples and best practices

### Improved
- **Developer Experience**: Dramatically simplified role-based workflow creation
  - Before: Manual creation of ApprovalInstance objects with role fields
  - After: Single `start_flow()` call with role parameters
- **Code Consistency**: Unified API for both user-based and role-based workflow creation
- **Performance**: Optimized step creation logic for mixed workflow types

### Technical Details
- Updated `start_flow()` function to handle both assignment types in step creation logic
- Enhanced validation logic to ensure proper role-based workflow configuration
- Improved logging to handle both user-based and role-based assignment information
- Template-based approach for pending role-based steps with automatic activation

## [0.5.1] - 2025-01-31

### Added
- **User-Specific Approval Management**: New utility functions for managing user workloads
  - `get_user_approval_step_ids(user, status=None)`: Get approval step IDs for specific user (optimized)
  - `get_user_approval_steps(user, status=None)`: Get full approval objects for specific user
  - `get_user_approval_summary(user)`: Get comprehensive user workload statistics
- **Enhanced Documentation**: Added comprehensive examples for user management functions
- **Test Coverage**: Added 3 new comprehensive tests for user-specific functions (56+ total tests)

### Improved
- **Performance**: User functions optimized with select_related and prefetch_related
- **Usability**: Functions designed for dashboard creation and task management
- **Flexibility**: Support for status filtering across all user functions

## [0.5.0] - 2025-01-31

### Added
- **New `extra_fields` JSONField**: Added extensible custom fields support to `ApprovalInstance` model
  - Store custom data without package modifications or database migrations
  - Perfect for integrating with external systems
  - Flexible JSON storage for any data structure
  - Maintains package compatibility across updates
- **Enhanced Role-Based Approvals**: Comprehensive role-based approval system with three strategies:
  - `ANYONE`: Any user with the role can approve
  - `CONSENSUS`: All users with role must approve  
  - `ROUND_ROBIN`: Distribute approvals evenly among role users
- **Delegation Support**: Users can delegate approval tasks to other users
- **Escalation Support**: Automatic escalation to role hierarchy or head managers
- **New utility functions**: `get_users_for_role`, `get_user_with_least_assignments`
- **Enhanced test coverage**: Added comprehensive tests for all new features (53+ tests)

### Improved
- **Performance optimizations**: Role-based step rejection now properly cleans up related instances
- **Better error handling**: Improved query syntax for role-based operations
- **Documentation**: Comprehensive README updates with new features and usage examples

### Fixed
- Fixed role-based step rejection to properly clean up all related instances in the same step
- Fixed Django query syntax compatibility issues in role-based operations

## [0.4.0] - 2025-07-30

### Added
- Dynamic GenericForeignKey support for forms
- CURRENT status optimization for enterprise-level performance
- `allow_higher_level` parameter for hierarchical approval control
- Performance improvements and caching optimizations

## [0.3.0] - Initial Release

### Added
- Basic approval workflow functionality
- Multi-step approval process
- Django model integration via GenericForeignKey
- Status tracking and management
- Basic test suite