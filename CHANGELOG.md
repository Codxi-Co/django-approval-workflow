# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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