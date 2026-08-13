import pytest

from app.hitl.approval import (
    ApprovalLevel,
    ApprovalPolicy,
    EscalationTrigger,
)


def test_supervisor_low_confidence_requires_plan_approval():
    policy = ApprovalPolicy()

    assert (
        policy.level_for(
            EscalationTrigger.SUPERVISOR_LOW_CONFIDENCE
        )
        == ApprovalLevel.APPROVE_PLAN
    )


def test_specialist_failure_requires_action_approval():
    policy = ApprovalPolicy()

    assert (
        policy.level_for(
            EscalationTrigger.SPECIALIST_FAILURE
        )
        == ApprovalLevel.APPROVE_ACTION
    )


def test_sensitive_operation_requires_action_approval():
    policy = ApprovalPolicy()

    assert (
        policy.level_for(
            EscalationTrigger.SENSITIVE_OPERATION
        )
        == ApprovalLevel.APPROVE_ACTION
    )


def test_reviewer_low_confidence_requires_action_approval():
    policy = ApprovalPolicy()

    assert (
        policy.level_for(
            EscalationTrigger.REVIEWER_LOW_CONFIDENCE
        )
        == ApprovalLevel.APPROVE_ACTION
    )


def test_explicit_user_request_requires_takeover():
    policy = ApprovalPolicy()

    assert (
        policy.level_for(
            EscalationTrigger.USER_REQUEST
        )
        == ApprovalLevel.TAKE_OVER
    )


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        (
            EscalationTrigger.SUPERVISOR_LOW_CONFIDENCE,
            ApprovalLevel.APPROVE_PLAN,
        ),
        (
            EscalationTrigger.SPECIALIST_FAILURE,
            ApprovalLevel.APPROVE_ACTION,
        ),
        (
            EscalationTrigger.SENSITIVE_OPERATION,
            ApprovalLevel.APPROVE_ACTION,
        ),
        (
            EscalationTrigger.REVIEWER_LOW_CONFIDENCE,
            ApprovalLevel.APPROVE_ACTION,
        ),
        (
            EscalationTrigger.USER_REQUEST,
            ApprovalLevel.TAKE_OVER,
        ),
    ],
)
def test_all_escalation_triggers_have_deterministic_levels(
    trigger,
    expected,
):
    policy = ApprovalPolicy()

    result = policy.evaluate(
        trigger=trigger,
        reason="test escalation",
    )

    assert result.trigger == trigger
    assert result.approval_level == expected
    assert result.reason == "test escalation"


def test_custom_policy_overrides_default_mapping():
    policy = ApprovalPolicy(
        levels={
            EscalationTrigger.USER_REQUEST:
                ApprovalLevel.APPROVE_PLAN,
        }
    )

    assert (
        policy.level_for(
            EscalationTrigger.USER_REQUEST
        )
        == ApprovalLevel.APPROVE_PLAN
    )


def test_custom_policy_can_override_one_trigger():
    policy = ApprovalPolicy(
        levels={
            EscalationTrigger.USER_REQUEST:
                ApprovalLevel.APPROVE_PLAN,
        }
    )

    assert (
        policy.level_for(
            EscalationTrigger.USER_REQUEST
        )
        == ApprovalLevel.APPROVE_PLAN
    )

    # Other triggers retain their defaults.
    assert (
        policy.level_for(
            EscalationTrigger.SPECIALIST_FAILURE
        )
        == ApprovalLevel.APPROVE_ACTION
    )

    assert (
        policy.level_for(
            EscalationTrigger.SUPERVISOR_LOW_CONFIDENCE
        )
        == ApprovalLevel.APPROVE_PLAN
    )
    
def test_blank_reason_gets_default_reason():
    policy = ApprovalPolicy()

    result = policy.evaluate(
        trigger=EscalationTrigger.SENSITIVE_OPERATION,
        reason="   ",
    )

    assert result.reason == (
        "Human review required because "
        "sensitive operation."
    )