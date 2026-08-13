import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_resume_rejects_execution(
    monkeypatch,
):
    from app.tasks.resume import (
        _resume_agentflow_execution,
    )

    execution_id = uuid4()
    decision_id = uuid4()

    # Use different variable names so that the values can
    # safely be referenced from the fake class definitions.
    expected_execution_id = execution_id
    expected_decision_id = decision_id

    class FakeTask:
        id = uuid4()
        user_id = "test-user"
        description = "Test execution"

    class FakeExecution:
        id = expected_execution_id
        status = "escalated"
        task = FakeTask()

        escalation_reason = "Needs human review"
        specialist_confidence = 0.30
        confidence_threshold = 0.50

        human_decision_status = "decided"
        human_escalation_required = True
        escalation_required = True

        resume_node = "post_specialist"
        resume_subtask_id = None

    class FakeDecision:
        id = expected_decision_id
        execution_id = expected_execution_id
        status = "decided"
        decision = "reject"
        feedback = "Reject this execution."

    class FakeExecutionRepository:

        def __init__(self, session):
            self.session = session

        async def get(self, requested_execution_id):
            assert (
                requested_execution_id
                == expected_execution_id
            )

            return FakeExecution()

        async def update_status(
            self,
            requested_execution_id,
            status,
        ):
            assert (
                requested_execution_id
                == expected_execution_id
            )

            assert status == "rejected"

            return FakeExecution()

    class FakeDecisionRepository:

        def __init__(self, session):
            self.session = session

        async def get(self, requested_decision_id):
            assert (
                requested_decision_id
                == expected_decision_id
            )

            return FakeDecision()

    class FakeSession:

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

    class FakeSessionContext:

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

    monkeypatch.setattr(
        "app.tasks.resume.AsyncSessionLocal",
        lambda: FakeSessionContext(),
    )

    monkeypatch.setattr(
        "app.tasks.resume.ExecutionRepository",
        FakeExecutionRepository,
    )

    monkeypatch.setattr(
        "app.tasks.resume.HumanDecisionRepository",
        FakeDecisionRepository,
    )

    result = await _resume_agentflow_execution(
        execution_id=str(
            expected_execution_id
        ),
        decision_id=str(
            expected_decision_id
        ),
    )

    assert result["execution_id"] == str(
        expected_execution_id
    )

    assert result["status"] == "rejected"

    assert result["final_output"] is None

    assert result["error"] == (
        "Execution was rejected by "
        "the human reviewer."
    )