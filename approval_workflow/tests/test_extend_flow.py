"""Tests for extend_flow functionality and resubmission with extend_flow."""

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from approval_workflow.models import ApprovalFlow, ApprovalInstance
from approval_workflow.services import start_flow, extend_flow, advance_flow
from approval_workflow.choices import ApprovalStatus, RoleSelectionStrategy
from approval_workflow.utils import get_current_approval

User = get_user_model()


@pytest.mark.django_db
def test_extend_flow_basic_functionality(setup_roles_and_users):
    """Test basic extend_flow functionality with user-based steps."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Extend Flow Test", description="Testing extend_flow"
    )

    # Create initial flow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Extend with additional steps
    new_instances = extend_flow(
        flow,
        [
            {"step": 3, "assigned_to": specialist},
            {"step": 4, "assigned_to": manager},
        ],
    )

    # Verify extension
    assert len(new_instances) == 2
    assert new_instances[0].step_number == 3
    assert new_instances[0].assigned_to == specialist
    assert new_instances[0].status == ApprovalStatus.PENDING

    assert new_instances[1].step_number == 4
    assert new_instances[1].assigned_to == manager
    assert new_instances[1].status == ApprovalStatus.PENDING

    # Verify total steps in flow
    total_steps = ApprovalInstance.objects.filter(flow=flow).count()
    assert total_steps == 4


@pytest.mark.django_db
def test_extend_flow_with_role_based_steps(setup_roles_and_users):
    """Test extend_flow with role-based steps."""
    manager, employee = setup_roles_and_users
    manager_role = manager.role

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Role Extend Test", description="Testing role-based extend_flow"
    )

    # Create initial flow
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Extend with role-based steps
    new_instances = extend_flow(
        flow,
        [
            {
                "step": 2,
                "assigned_role": manager_role,
                "role_selection_strategy": RoleSelectionStrategy.ANYONE,
            },
            {
                "step": 3,
                "assigned_role": manager_role,
                "role_selection_strategy": RoleSelectionStrategy.CONSENSUS,
            },
        ],
    )

    # First role-based step should remain as template (PENDING)
    assert len(new_instances) == 2
    assert new_instances[0].step_number == 2
    assert new_instances[0].assigned_to is None  # Template
    assert new_instances[0].status == ApprovalStatus.PENDING
    assert new_instances[0].role_selection_strategy == RoleSelectionStrategy.ANYONE

    assert new_instances[1].step_number == 3
    assert new_instances[1].assigned_to is None  # Template
    assert new_instances[1].status == ApprovalStatus.PENDING
    assert new_instances[1].role_selection_strategy == RoleSelectionStrategy.CONSENSUS


@pytest.mark.django_db
def test_extend_flow_makes_first_step_current_when_no_current_exists(
    setup_roles_and_users,
):
    """Test that extend_flow makes first new step CURRENT when no current step exists."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Current Step Test", description="Testing current step logic"
    )

    # Create initial flow and complete all steps
    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Complete the only step
    current_step = get_current_approval(dummy)
    advance_flow(current_step, action="approved", user=employee)

    # Now no CURRENT step exists, extend_flow should make first new step CURRENT
    new_instances = extend_flow(
        flow,
        [
            {"step": 2, "assigned_to": manager},
            {"step": 3, "assigned_to": employee},
        ],
    )

    # First new step should be CURRENT
    assert new_instances[0].step_number == 2
    assert new_instances[0].status == ApprovalStatus.CURRENT

    # Second new step should be PENDING
    assert new_instances[1].step_number == 3
    assert new_instances[1].status == ApprovalStatus.PENDING


@pytest.mark.django_db
def test_extend_flow_validation_step_number_conflict(setup_roles_and_users):
    """Test that extend_flow prevents step number conflicts."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Conflict Test", description="Testing step number conflicts"
    )

    # Create initial flow
    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Try to extend with conflicting step number
    with pytest.raises(ValueError, match="Step number 2 .* already exists in the flow"):
        extend_flow(flow, [{"step": 2, "assigned_to": employee}])


@pytest.mark.django_db
def test_extend_flow_validation_assigned_to_or_assigned_role():
    """Test validation that steps must have either assigned_to OR assigned_role."""
    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Validation Test", description="Testing validation"
    )

    flow = start_flow(
        dummy, [{"step": 1, "assigned_to": User.objects.create(username="user1")}]
    )

    # Test missing both assigned_to and assigned_role
    with pytest.raises(
        ValueError, match="must have either 'assigned_to' or 'assigned_role'"
    ):
        extend_flow(flow, [{"step": 2}])

    # Test having both assigned_to and assigned_role
    manager = User.objects.create(username="manager")
    manager_role = type("Role", (), {"pk": 1, "name": "Manager"})()

    with pytest.raises(
        ValueError, match="cannot have both 'assigned_to' and 'assigned_role'"
    ):
        extend_flow(
            flow,
            [
                {
                    "step": 2,
                    "assigned_to": manager,
                    "assigned_role": manager_role,
                    "role_selection_strategy": RoleSelectionStrategy.ANYONE,
                }
            ],
        )


@pytest.mark.django_db
def test_extend_flow_with_extra_fields(setup_roles_and_users):
    """Test extend_flow with extra_fields support."""
    manager, employee = setup_roles_and_users

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Extra Fields Test", description="Testing extra fields in extend_flow"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Extend with extra_fields
    extra_data = {
        "priority": "urgent",
        "department": "Legal",
        "metadata": {"requires_documentation": True},
    }

    new_instances = extend_flow(
        flow, [{"step": 2, "assigned_to": manager, "extra_fields": extra_data}]
    )

    # Verify extra_fields are stored
    assert new_instances[0].extra_fields == extra_data


@pytest.mark.django_db
def test_resubmission_uses_extend_flow(setup_roles_and_users):
    """Test that resubmission now uses extend_flow internally."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Resubmission Test", description="Testing resubmission with extend_flow"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Request resubmission from first step with explicit step numbers
    first_step = get_current_approval(dummy)
    new_steps = [
        {"step": 3, "assigned_to": specialist},  # Explicit step number
        {"step": 4, "assigned_to": manager},  # Explicit step number
    ]

    next_step = advance_flow(
        first_step,
        action="resubmission",
        user=employee,
        comment="Additional review needed",
        resubmission_steps=new_steps,
    )

    # Verify original step is marked for resubmission
    first_step.refresh_from_db()
    assert first_step.status == ApprovalStatus.NEEDS_RESUBMISSION
    assert first_step.comment == "Additional review needed"

    # Verify new steps are created with correct step numbers
    assert next_step.step_number == 3  # Explicit step number
    assert next_step.assigned_to == specialist
    assert next_step.status == ApprovalStatus.CURRENT

    # Verify second new step
    step_4 = ApprovalInstance.objects.get(flow=flow, step_number=4)
    assert step_4.assigned_to == manager
    assert step_4.status == ApprovalStatus.PENDING

    # Verify step 2 was deleted (remaining step)
    assert not ApprovalInstance.objects.filter(flow=flow, step_number=2).exists()

    # Verify total steps: 1 (resubmitted) + 2 (new) = 3
    total_steps = ApprovalInstance.objects.filter(flow=flow).count()
    assert total_steps == 3


@pytest.mark.django_db
def test_resubmission_with_role_based_steps(setup_roles_and_users):
    """Test resubmission with role-based steps using extend_flow."""
    manager, employee = setup_roles_and_users
    manager_role = manager.role

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Role Resubmission Test", description="Testing role-based resubmission"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Request resubmission with role-based step
    first_step = get_current_approval(dummy)
    role_based_steps = [
        {
            "step": 2,
            "assigned_role": manager_role,
            "role_selection_strategy": RoleSelectionStrategy.CONSENSUS,
        }
    ]

    next_step = advance_flow(
        first_step,
        action="resubmission",
        user=employee,
        comment="Need consensus from all managers",
        resubmission_steps=role_based_steps,
    )

    # Verify role-based step was created and activated
    assert next_step.step_number == 2
    assert next_step.assigned_to == manager  # Should be activated
    assert next_step.status == ApprovalStatus.CURRENT
    assert next_step.role_selection_strategy == RoleSelectionStrategy.CONSENSUS


@pytest.mark.django_db
def test_resubmission_step_number_conflict_prevention():
    """Test that resubmission with conflicting step numbers raises error."""
    employee = User.objects.create(username="employee")
    manager = User.objects.create(username="manager")

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Conflict Prevention Test", description="Testing step number conflicts"
    )

    flow = start_flow(
        dummy,
        [
            {"step": 1, "assigned_to": employee},
            {"step": 2, "assigned_to": manager},
        ],
    )

    # Try resubmission with conflicting step number
    first_step = get_current_approval(dummy)
    conflicting_steps = [
        {"step": 1, "assigned_to": manager}  # Conflicts with existing step 1
    ]

    with pytest.raises(ValueError, match="Resubmission failed: Step number 1"):
        advance_flow(
            first_step,
            action="resubmission",
            user=employee,
            resubmission_steps=conflicting_steps,
        )


@pytest.mark.django_db
def test_extend_flow_mixed_user_and_role_steps(setup_roles_and_users):
    """Test extend_flow with mixed user-based and role-based steps."""
    manager, employee = setup_roles_and_users
    specialist = User.objects.create(username="specialist")
    manager_role = manager.role

    MockRequestModel = apps.get_model("testapp", "MockRequestModel")
    dummy = MockRequestModel.objects.create(
        title="Mixed Steps Test", description="Testing mixed step types"
    )

    flow = start_flow(dummy, [{"step": 1, "assigned_to": employee}])

    # Extend with mixed steps
    new_instances = extend_flow(
        flow,
        [
            {"step": 2, "assigned_to": specialist},  # User-based
            {
                "step": 3,
                "assigned_role": manager_role,
                "role_selection_strategy": RoleSelectionStrategy.ROUND_ROBIN,
            },  # Role-based
            {"step": 4, "assigned_to": manager},  # User-based
        ],
    )

    # Verify mixed steps
    assert len(new_instances) == 3

    # Step 2: User-based
    assert new_instances[0].step_number == 2
    assert new_instances[0].assigned_to == specialist
    assert new_instances[0].assigned_role_content_type is None

    # Step 3: Role-based (template)
    assert new_instances[1].step_number == 3
    assert new_instances[1].assigned_to is None
    assert new_instances[1].assigned_role_content_type is not None
    assert new_instances[1].role_selection_strategy == RoleSelectionStrategy.ROUND_ROBIN

    # Step 4: User-based
    assert new_instances[2].step_number == 4
    assert new_instances[2].assigned_to == manager
    assert new_instances[2].assigned_role_content_type is None
