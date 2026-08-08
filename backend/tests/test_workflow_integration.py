from uuid import uuid4

import pytest
from app.schemas.review import ReviewResult
from app.graph.workflow import build_workflow
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import (
    Complexity,
    ExecutionPlan,
    Specialist,
    SubTask,
)


class FakeSupervisor:
    """
    Deterministic Supervisor used for graph integration testing.

    No real LLM call is made.
    """

    def __init__(self, plan: ExecutionPlan) -> None:
        self.plan = plan

    async def create_plan(
        self,
        agent_input: AgentInput,
    ) -> ExecutionPlan:
        return self.plan


class FakeSpecialistAgent:
    """
    Deterministic specialist used for graph integration testing.
    """

    def __init__(
        self,
        specialist: Specialist,
        content: str,
    ) -> None:
        self.specialist = specialist
        self.content = content
        self.calls: list[AgentInput] = []

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:

        self.calls.append(agent_input)

        return AgentOutput(
            agent=self.specialist.value,
            specialist=self.specialist,
            subtask_id=agent_input.subtask_id,
            content=self.content,
            success=True,
        )


class FakeReviewer:
    """
    Deterministic reviewer used for graph integration testing.

    Returns the same structured review contract that the real
    ReviewerAgent now produces.
    """

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:

        review = ReviewResult(
            approved=True,
            quality_score=0.95,
            confidence=0.95,
            feedback="",
            issues=[],
        )

        return AgentOutput(
            agent="reviewer",
            subtask_id=agent_input.subtask_id,
            content=review.model_dump_json(),
            success=True,
            confidence=review.confidence,
            metadata={
                "review": review.model_dump(
                    mode="json"
                ),
            },
        )


def create_plan(task_id):
    subtask = SubTask(
        id=uuid4(),
        description="Research the topic",
        assigned_specialist=Specialist.RESEARCH,
        required_inputs=[],
        expected_output="Research findings",
        estimated_complexity=Complexity.MEDIUM,
    )

    return ExecutionPlan(
        task_id=task_id,
        subtasks=[subtask],
    )


@pytest.mark.asyncio
async def test_compiled_workflow_runs_end_to_end():

    task_id = uuid4()

    plan = create_plan(task_id)

    supervisor = FakeSupervisor(plan)

    research_agent = FakeSpecialistAgent(
        specialist=Specialist.RESEARCH,
        content="Research completed successfully.",
    )

    analysis_agent = FakeSpecialistAgent(
        specialist=Specialist.DATA_ANALYSIS,
        content="Analysis completed successfully.",
    )

    writing_agent = FakeSpecialistAgent(
        specialist=Specialist.WRITING,
        content="Writing completed successfully.",
    )

    coding_agent = FakeSpecialistAgent(
        specialist=Specialist.CODE_EXECUTION,
        content="Code execution completed successfully.",
    )

    reviewer = FakeReviewer()

    workflow = build_workflow(
        supervisor=supervisor,
        research_agent=research_agent,
        analysis_agent=analysis_agent,
        writing_agent=writing_agent,
        coding_agent=coding_agent,
        reviewer_agent=reviewer,
    )

    result = await workflow.ainvoke(
        {
            "task_id": task_id,
            "user_id": "test-user",
            "description": (
                "Research a topic and prepare findings."
            ),
        }
    )

    assert result["plan"].task_id == task_id

    assert len(
        result["specialist_outputs"]
    ) == 1

    assert (
        result["specialist_outputs"][0]["content"]
        == "Research completed successfully."
    )

    assert result["review"].approved is True
    assert result["review"].quality_score == 0.95
    assert result["review"].confidence == 0.95

    assert (
        result["final_output"]
        == "Research completed successfully."
    )

    assert len(research_agent.calls) == 1