import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_approve_resume_continues_execution():
    """
    Human approve should continue unfinished work.
    """
    # Create escalated execution.
    # Create pending human decision.
    # Decide approve.
    # Execute resume task.
    # Assert execution leaves escalated state.
    ...


@pytest.mark.asyncio
async def test_replan_resume_creates_new_plan():
    """
    Human replan should return through planning.
    """
    ...


@pytest.mark.asyncio
async def test_reject_resume_marks_execution_rejected():
    """
    Human reject should terminate the execution.
    """
    ...


@pytest.mark.asyncio
async def test_resume_uses_existing_review():
    """
    Reviewer escalation + approve should continue to synthesis
    instead of rerunning specialists.
    """
    ...


@pytest.mark.asyncio
async def test_resume_restores_completed_subtasks():
    """
    Resume must not lose specialist outputs already produced
    before escalation.
    """
    ...