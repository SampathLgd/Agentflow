import pytest
from uuid import uuid4

from app.db.repositories.execution import (
    ExecutionRepository,
)
from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)
from app.db.repositories.task import TaskRepository
from app.db.session import AsyncSessionLocal
from app.tasks.execution import (
    _execute_agentflow_task,
)


@pytest.mark.asyncio
async def test_execution_persists_escalated_status(
    monkeypatch,
):
    task_id = uuid4()
    execution_id = uuid4()

    class FakeRuntime:
        supervisor = object()
        research_agent = object()
        analysis_agent = object()
        writing_agent = object()
        coding_agent = object()
        reviewer_agent = object()
        working_memory = object()
        long_term_memory = object()
        memory_service = object()

    class FakeWorkflow:
        async def ainvoke(self, state):
            return {
                "execution_status": "escalated",
                "final_output": None,
                "error": None,
                "escalation_required": False,
                "human_escalation_required": True,
                "escalation_reason": (
                    "Specialist confidence 0.30 is "
                    "below the configured threshold 0.50."
                ),
                "specialist_confidence": 0.30,
                "confidence_threshold": 0.50,
                "resume_node": "specialist",
                "resume_subtask_id": None,
            }

    async def fake_build_runtime(settings):
        return FakeRuntime()

    def fake_build_workflow(**kwargs):
        return FakeWorkflow()

    monkeypatch.setattr(
        "app.tasks.execution.build_agent_runtime",
        fake_build_runtime,
    )

    monkeypatch.setattr(
        "app.tasks.execution.build_workflow",
        fake_build_workflow,
    )

    result = await _execute_agentflow_task(
        task_id=str(task_id),
        execution_id=str(execution_id),
        user_id="test-user",
        description="Test escalation",
    )

    # ---------------------------------------------------------
    # Returned result
    # ---------------------------------------------------------

    assert result["status"] == "escalated"
    assert result["final_output"] is None
    assert (
        result["human_escalation_required"]
        is True
    )

    assert (
        result["escalation_reason"]
        is not None
    )

    assert (
        result["specialist_confidence"]
        == 0.30
    )

    assert (
        result["confidence_threshold"]
        == 0.50
    )

    assert (
        result["resume_node"]
        == "specialist"
    )

    # ---------------------------------------------------------
    # Verify database persistence
    # ---------------------------------------------------------

    async with AsyncSessionLocal() as session:
        task_repo = TaskRepository(session)
        execution_repo = ExecutionRepository(
            session
        )
        human_decision_repo = (
            HumanDecisionRepository(session)
        )

        task = await task_repo.get(
            task_id
        )

        assert task is not None

        execution = await execution_repo.get(
            execution_id
        )

        assert execution is not None

        assert (
            execution.status
            == "escalated"
        )

        assert (
            execution.human_escalation_required
            is True
        )

        assert (
            execution.escalation_reason
            is not None
        )

        assert (
            execution.specialist_confidence
            == 0.30
        )

        assert (
            execution.confidence_threshold
            == 0.50
        )

        assert (
            execution.resume_node
            == "specialist"
        )

        assert (
            execution.human_decision_status
            == "pending"
        )

        # -----------------------------------------------------
        # Verify pending HITL decision
        # -----------------------------------------------------

        decision = (
            await human_decision_repo
            .get_pending_for_execution(
                execution_id
            )
        )

        assert decision is not None

        assert (
            decision.execution_id
            == execution_id
        )

        assert decision.status == "pending"
        assert decision.decision is None
        assert decision.feedback is None