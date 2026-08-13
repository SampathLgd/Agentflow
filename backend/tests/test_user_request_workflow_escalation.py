import pytest

from app.graph.workflow import (
    check_user_escalation,
)


def test_explicit_user_request_creates_takeover_escalation():
    state = {
        "task_id": "test-task",
        "user_id": "test-user",
        "description": (
            "I explicitly request human takeover "
            "before this task continues."
        ),
    }

    result = check_user_escalation(state)

    assert result["execution_status"] == "escalated"

    assert (
        result["escalation_required"]
        is True
    )

    assert (
        result["human_escalation_required"]
        is True
    )

    assert (
        result["escalation_trigger"]
        == "user_request"
    )

    assert (
        result["approval_level"]
        == "take_over"
    )

    assert (
        result["proposed_action"]
        == (
            "Transfer execution to human control "
            "before continuing."
        )
    )

    assert (
        result["human_decision_status"]
        == "pending"
    )


def test_normal_user_request_does_not_escalate():
    state = {
        "task_id": "test-task",
        "user_id": "test-user",
        "description": (
            "Research the latest information about "
            "the project."
        ),
    }

    result = check_user_escalation(state)

    assert (
        result["escalation_required"]
        is False
    )

    assert (
        result["human_escalation_required"]
        is False
    )