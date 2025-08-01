# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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