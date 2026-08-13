from __future__ import annotations

import pytest

from app.graph.workflow import route_after_human


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
    decision: str,
):
    state = {
        "human_decision": decision,
        "plan": object(),
        "resume_node": "post_specialist",
        "completed_subtasks": [],
    }

    assert route_after_human(state) == "specialist"


def test_replan_returns_to_planning():
    state = {
        "human_decision": "replan",
        "plan": object(),
    }

    assert route_after_human(state) == "planning"


def test_reject_is_terminal():
    state = {
        "human_decision": "reject",
    }

    assert route_after_human(state) == "rejected"


def test_take_over_is_terminal():
    state = {
        "human_decision": "take_over",
    }

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
    decision: str,
):
    state = {
        "human_decision": decision,
        "plan": None,
    }

    assert route_after_human(state) == "planning"


def test_approve_after_review_goes_to_synthesis():
    state = {
        "human_decision": "approve",
        "plan": object(),
        "resume_node": "post_review",
        "review": object(),
        "completed_subtasks": [],
    }

    # The public helper represents the logical destination.
    assert route_after_human(state) == "synthesis"


def test_invalid_human_decision_is_rejected():
    state = {
        "human_decision": "something_invalid",
        "plan": object(),
    }

    with pytest.raises(ValueError):
        route_after_human(state)