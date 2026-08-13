from __future__ import annotations

import pytest

from app.graph.workflow import (
    route_after_human,
    route_after_review,
    route_after_specialists,
    resume_after_human,
)


# ============================================================
# Helpers
# ============================================================


class FakePlan:
    """
    Minimal plan object required by workflow routing helpers.
    """

    def __init__(self, subtasks: list | None = None):
        self.subtasks = subtasks or []


class FakeSubtask:
    def __init__(
        self,
        subtask_id: str,
        dependencies: list[str] | None = None,
    ):
        self.id = subtask_id
        self.dependencies = dependencies or []


class FakeReview:
    def __init__(
        self,
        *,
        approved: bool,
        confidence: float,
    ):
        self.approved = approved
        self.confidence = confidence
        self.feedback = ""


def make_state(**overrides):
    state = {
        "task_id": "phase3-task",
        "description": "Phase 3 integration test",
        "plan": FakePlan(
            [
                FakeSubtask("subtask-1"),
            ]
        ),
        "completed_subtasks": [],
        "specialist_outputs": [],
        "specialist_confidence": 1.0,
        "confidence_threshold": 0.5,
        "failure_reason": "",
        "retry_count": 0,
        "max_retries": 2,
        "human_decision": None,
        "human_decision_status": "pending",
        "human_feedback": None,
        "human_escalation_required": False,
        "escalation_required": False,
        "replan_required": False,
        "resume_node": "post_specialist",
        "resume_subtask_id": None,
    }

    state.update(overrides)

    return state


# ============================================================
# Specialist routing
# ============================================================


def test_specialist_failure_retries_before_failure():
    state = make_state(
        failure_reason="Specialist failed",
        retry_count=0,
        max_retries=2,
    )

    assert route_after_specialists(state) == "retry"


def test_specialist_failure_exhausts_retries():
    state = make_state(
        failure_reason="Specialist failed",
        retry_count=2,
        max_retries=2,
    )

    assert route_after_specialists(state) == "failed"


def test_low_specialist_confidence_escalates():
    state = make_state(
        specialist_confidence=0.2,
        confidence_threshold=0.5,
    )

    assert (
        route_after_specialists(state)
        == "human_escalation"
    )


def test_completed_specialists_go_to_review():
    state = make_state(
        completed_subtasks=["subtask-1"],
    )

    assert route_after_specialists(state) == "review"


def test_incomplete_specialists_dispatch_again():
    state = make_state(
        plan=FakePlan(
            [
                FakeSubtask("subtask-1"),
                FakeSubtask("subtask-2"),
            ]
        ),
        completed_subtasks=["subtask-1"],
    )

    assert route_after_specialists(state) == "dispatch"


# ============================================================
# Review routing
# ============================================================


def test_low_review_confidence_escalates():
    state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.2,
        ),
        confidence_threshold=0.5,
    )

    assert route_after_review(state) == "escalate"


def test_approved_review_goes_to_synthesis():
    state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.9,
        ),
    )

    assert route_after_review(state) == "synthesis"


def test_rejected_review_retries():
    state = make_state(
        review=FakeReview(
            approved=False,
            confidence=0.9,
        ),
        review_retry_count=0,
        max_review_retries=2,
    )

    assert route_after_review(state) == "review_retry"


def test_rejected_review_after_max_retries_fails():
    state = make_state(
        review=FakeReview(
            approved=False,
            confidence=0.9,
        ),
        review_retry_count=2,
        max_review_retries=2,
    )

    assert route_after_review(state) == "review_failed"


def test_missing_review_is_rejected():
    state = make_state(
        review=None,
    )

    with pytest.raises(ValueError):
        route_after_review(state)


# ============================================================
# Granular HITL routing
# ============================================================


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "notify",
        "approve_action",
        "approve_plan",
    ],
)
def test_current_plan_decisions_continue_execution(
    decision,
):
    state = make_state(
        human_decision=decision,
        human_decision_status="decided",
    )

    assert route_after_human(state) == "specialist"


def test_replan_returns_to_planning():
    state = make_state(
        human_decision="replan",
        human_decision_status="decided",
        human_feedback="Please use another approach.",
    )

    assert route_after_human(state) == "planning"


def test_reject_is_terminal():
    state = make_state(
        human_decision="reject",
        human_decision_status="decided",
    )

    assert route_after_human(state) == "rejected"


def test_take_over_is_terminal():
    state = make_state(
        human_decision="take_over",
        human_decision_status="decided",
    )

    assert route_after_human(state) == "human_takeover"


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "notify",
        "approve_action",
        "approve_plan",
    ],
)
def test_decision_without_plan_returns_to_planning(
    decision,
):
    state = make_state(
        plan=None,
        human_decision=decision,
        human_decision_status="decided",
    )

    assert route_after_human(state) == "planning"


def test_approve_after_review_goes_to_synthesis():
    state = make_state(
        human_decision="approve",
        human_decision_status="decided",
        resume_node="post_review",
    )

    assert route_after_human(state) == "synthesis"


def test_invalid_human_decision_is_rejected():
    state = make_state(
        human_decision="invalid",
        human_decision_status="decided",
    )

    with pytest.raises(ValueError):
        route_after_human(state)


# ============================================================
# Human state normalization
# ============================================================


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "replan",
        "reject",
        "notify",
        "approve_action",
        "approve_plan",
        "take_over",
    ],
)
def test_resume_after_human_accepts_all_granular_decisions(
    decision,
):
    state = make_state(
        human_decision=decision,
        human_decision_status="decided",
    )

    result = resume_after_human(state)

    assert isinstance(result, dict)


def test_resume_after_human_reject_sets_rejected_state():
    state = make_state(
        human_decision="reject",
        human_decision_status="decided",
    )

    result = resume_after_human(state)

    assert result["execution_status"] == "rejected"
    assert result["human_escalation_required"] is False
    assert result["escalation_required"] is False


def test_resume_after_human_replan_sets_replan():
    state = make_state(
        human_decision="replan",
        human_decision_status="decided",
        human_feedback="Change the plan.",
    )

    result = resume_after_human(state)

    assert result["execution_status"] == "running"
    assert result["replan_required"] is True
    assert result["review_feedback"] == "Change the plan."


def test_resume_after_human_takeover_sets_takeover():
    state = make_state(
        human_decision="take_over",
        human_decision_status="decided",
    )

    result = resume_after_human(state)

    assert result["execution_status"] == "human_takeover"


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "notify",
        "approve_action",
        "approve_plan",
    ],
)
def test_resume_after_human_approval_continues_execution(
    decision,
):
    state = make_state(
        human_decision=decision,
        human_decision_status="decided",
    )

    result = resume_after_human(state)

    assert result["execution_status"] == "running"
    assert result["human_escalation_required"] is False
    assert result["escalation_required"] is False
    assert result["replan_required"] is False


def test_resume_after_human_rejects_invalid_decision():
    state = make_state(
        human_decision="invalid",
        human_decision_status="decided",
    )

    with pytest.raises(ValueError):
        resume_after_human(state)


# ============================================================
# Phase 3 lifecycle
# ============================================================


def test_phase3_reviewer_escalation_to_human_approval():
    """
    Reviewer:
        low confidence
            ↓
        escalation
            ↓
        human approve
            ↓
        synthesis
    """

    review_state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.2,
        ),
        confidence_threshold=0.5,
    )

    assert route_after_review(review_state) == "escalate"

    human_state = make_state(
        human_decision="approve",
        human_decision_status="decided",
        resume_node="post_review",
    )

    assert route_after_human(human_state) == "synthesis"


def test_phase3_reviewer_escalation_to_replan():
    """
    Reviewer:
        low confidence
            ↓
        escalation
            ↓
        human replan
            ↓
        planning
    """

    review_state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.2,
        ),
        confidence_threshold=0.5,
    )

    assert route_after_review(review_state) == "escalate"

    human_state = make_state(
        human_decision="replan",
        human_decision_status="decided",
    )

    assert route_after_human(human_state) == "planning"


def test_phase3_reviewer_escalation_to_rejection():
    review_state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.2,
        ),
        confidence_threshold=0.5,
    )

    assert route_after_review(review_state) == "escalate"

    human_state = make_state(
        human_decision="reject",
        human_decision_status="decided",
    )

    assert route_after_human(human_state) == "rejected"


def test_phase3_reviewer_escalation_to_takeover():
    review_state = make_state(
        review=FakeReview(
            approved=True,
            confidence=0.2,
        ),
        confidence_threshold=0.5,
    )

    assert route_after_review(review_state) == "escalate"

    human_state = make_state(
        human_decision="take_over",
        human_decision_status="decided",
    )

    assert route_after_human(human_state) == "human_takeover"


def test_phase3_specialist_escalation_to_human_approval():
    state = make_state(
        specialist_confidence=0.2,
        confidence_threshold=0.5,
    )

    assert (
        route_after_specialists(state)
        == "human_escalation"
    )

    approved_state = make_state(
        human_decision="approve_action",
        human_decision_status="decided",
    )

    assert route_after_human(approved_state) == "specialist"


def test_phase3_specialist_escalation_to_replan():
    state = make_state(
        specialist_confidence=0.2,
        confidence_threshold=0.5,
    )

    assert (
        route_after_specialists(state)
        == "human_escalation"
    )

    replan_state = make_state(
        human_decision="replan",
        human_decision_status="decided",
    )

    assert route_after_human(replan_state) == "planning"


def test_phase3_specialist_escalation_to_rejection():
    state = make_state(
        specialist_confidence=0.2,
        confidence_threshold=0.5,
    )

    assert (
        route_after_specialists(state)
        == "human_escalation"
    )

    reject_state = make_state(
        human_decision="reject",
        human_decision_status="decided",
    )

    assert route_after_human(reject_state) == "rejected"