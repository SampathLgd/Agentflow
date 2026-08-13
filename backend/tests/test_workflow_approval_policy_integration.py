import pytest

from app.graph.workflow import (
    _apply_escalation_policy,
)


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        (
            "supervisor_low_confidence",
            "approve_plan",
        ),
        (
            "specialist_failure",
            "approve_action",
        ),
        (
            "sensitive_operation",
            "approve_action",
        ),
        (
            "reviewer_low_confidence",
            "approve_action",
        ),
        (
            "user_request",
            "take_over",
        ),
    ],
)
def test_workflow_escalation_uses_approval_policy(
    trigger,
    expected,
):
    result = _apply_escalation_policy(
        {},
        trigger=trigger,
        reason="test escalation",
        proposed_action="test action",
    )

    assert result["escalation_required"] is True
    assert result["human_escalation_required"] is True
    assert result["escalation_trigger"] == trigger
    assert result["approval_level"] == expected
    assert result["proposed_action"] == "test action"