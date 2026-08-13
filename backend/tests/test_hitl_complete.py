from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_approve_specialist_escalation_resumes():
    from app.graph.workflow import route_after_human

    state = {
        "human_decision": "approve",
        "plan": None,
        "completed_subtasks": [],
    }

    # No plan means the workflow must safely re-enter planning.
    assert route_after_human(state) == "planning"


@pytest.mark.asyncio
async def test_replan_routes_to_planning():
    from app.graph.workflow import route_after_human

    state = {
        "human_decision": "replan",
    }

    assert (
        route_after_human(state)
        == "planning"
    )


@pytest.mark.asyncio
async def test_reject_routes_to_terminal():
    from app.graph.workflow import route_after_human

    state = {
        "human_decision": "reject",
    }

    assert (
        route_after_human(state)
        == "rejected"
    )


@pytest.mark.asyncio
async def test_invalid_human_decision_is_rejected():
    from app.graph.workflow import (
        resume_after_human,
    )

    state = {
        "human_decision": "something_else",
    }

    with pytest.raises(ValueError):
        resume_after_human(state)


@pytest.mark.asyncio
async def test_approve_clears_escalation():
    from app.graph.workflow import (
        resume_after_human,
    )

    result = resume_after_human(
        {
            "human_decision": "approve",
        }
    )

    assert (
        result["execution_status"]
        == "running"
    )

    assert (
        result["human_escalation_required"]
        is False
    )

    assert (
        result["escalation_required"]
        is False
    )


@pytest.mark.asyncio
async def test_replan_preserves_feedback():
    from app.graph.workflow import (
        resume_after_human,
    )

    result = resume_after_human(
        {
            "human_decision": "replan",
            "human_feedback": (
                "Use a more reliable research approach."
            ),
        }
    )

    assert (
        result["replan_required"]
        is True
    )

    assert (
        result["review_feedback"]
        == "Use a more reliable research approach."
    )


@pytest.mark.asyncio
async def test_reject_sets_terminal_state():
    from app.graph.workflow import (
        resume_after_human,
    )

    result = resume_after_human(
        {
            "human_decision": "reject",
        }
    )

    assert (
        result["execution_status"]
        == "rejected"
    )

    assert (
        result["human_escalation_required"]
        is False
    )

    assert (
        result["escalation_required"]
        is False
    )