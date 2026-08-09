from uuid import uuid4
from app.memory.redis_store import RedisWorkingMemoryStore
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
from app.memory.long_term import (
    LongTermMemory,
    LongTermMemoryStore,
    MemorySearchResult,
)
class FakeRedis:
    """
    Minimal async Redis replacement for workflow tests.

    Implements only the Redis operations required by
    RedisWorkingMemoryStore.
    """

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
    ) -> None:
        self.data[key] = value

    async def get(
        self,
        key: str,
    ) -> str | None:
        return self.data.get(key)

    async def expire(
        self,
        key: str,
        seconds: int,
    ) -> bool:
        # TTL behavior is not required for this unit test.
        return key in self.data

    async def delete(
        self,
        *keys: str,
    ) -> int:
        deleted = 0

        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1

        return deleted

class FakeLongTermMemoryStore(LongTermMemoryStore):
    """
    In-memory fake for workflow integration tests.

    This lets us verify that the workflow actually retrieves
    and persists long-term memory without requiring ChromaDB.
    """

    def __init__(self) -> None:
        self.memories: list[LongTermMemory] = []
        self.search_calls: list[dict] = []
        self.add_calls: list[LongTermMemory] = []

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        self.add_calls.append(memory)
        self.memories.append(memory)

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[MemorySearchResult]:

        self.search_calls.append(
            {
                "user_id": user_id,
                "query": query,
                "limit": limit,
                "memory_type": memory_type,
            }
        )

        results = [
            MemorySearchResult(
                memory=memory,
                distance=0.1,
            )
            for memory in self.memories
            if memory.user_id == user_id
            and (
                memory_type is None
                or memory.memory_type == memory_type
            )
        ]

        return results[:limit]

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        self.memories = [
            memory
            for memory in self.memories
            if memory.id != memory_id
        ]

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        self.memories = [
            memory
            for memory in self.memories
            if memory.user_id != user_id
        ]

    async def count(
        self,
        user_id: str,
    ) -> int:
        return sum(
            memory.user_id == user_id
            for memory in self.memories
        )
class FakeSupervisor:
    """
    Deterministic Supervisor used for graph integration testing.
    """

    def __init__(
        self,
        plan: ExecutionPlan,
    ) -> None:
        self.plan = plan
        self.calls: list[AgentInput] = []

    async def create_plan(
        self,
        agent_input: AgentInput,
    ) -> ExecutionPlan:

        self.calls.append(
            agent_input
        )

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

    long_term_memory = FakeLongTermMemoryStore()

    workflow = build_workflow(
        supervisor=supervisor,
        research_agent=research_agent,
        analysis_agent=analysis_agent,
        writing_agent=writing_agent,
        coding_agent=coding_agent,
        reviewer_agent=reviewer,
        long_term_memory=long_term_memory,
    )

    result = await workflow.ainvoke(
        {
            "task_id": str(task_id),
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

@pytest.mark.asyncio
async def test_workflow_uses_working_memory():
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

    memory = RedisWorkingMemoryStore(
        FakeRedis()
    )

    long_term_memory = FakeLongTermMemoryStore()

    workflow = build_workflow(
        supervisor=supervisor,
        research_agent=research_agent,
        analysis_agent=analysis_agent,
        writing_agent=writing_agent,
        coding_agent=coding_agent,
        reviewer_agent=reviewer,
        working_memory=memory,
        long_term_memory=long_term_memory,
    )

    result = await workflow.ainvoke(
        {
            "task_id": str(task_id),
            "user_id": "test-user",
            "description": (
                "Research a topic and prepare findings."
            ),
        }
    )

    assert result["final_output"]

    # Successful completion clears task-scoped
    # short-term working memory.
    snapshot = await memory.snapshot(
        str(task_id)
    )

    assert snapshot["plan"] is None
    assert snapshot["subtask_outputs"] == []
    assert snapshot["intermediate_results"] == {}
    assert snapshot["errors"] == []

@pytest.mark.asyncio
async def test_workflow_uses_long_term_memory():
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

    long_term_memory = FakeLongTermMemoryStore()

    previous_memory = LongTermMemory(
        id="previous-memory",
        user_id="test-user",
        task_id="previous-task",
        memory_type="successful_approach",
        content=(
            "Use web search before performing analysis."
        ),
        metadata={
            "source": "previous_execution",
        },
        importance_score=0.9,
    )

    await long_term_memory.add(
        previous_memory
    )

    workflow = build_workflow(
        supervisor=supervisor,
        research_agent=research_agent,
        analysis_agent=analysis_agent,
        writing_agent=writing_agent,
        coding_agent=coding_agent,
        reviewer_agent=reviewer,
        long_term_memory=long_term_memory,
    )

    result = await workflow.ainvoke(
        {
            "task_id": str(task_id),
            "user_id": "test-user",
            "description": (
                "Research a topic and prepare findings."
            ),
        }
    )

    # --------------------------------------------------------
    # Retrieval happened
    # --------------------------------------------------------

    assert len(
        long_term_memory.search_calls
    ) == 1

    search_call = (
        long_term_memory.search_calls[0]
    )

    assert search_call["user_id"] == "test-user"

    assert search_call["query"] == (
        "Research a topic and prepare findings."
    )

    # --------------------------------------------------------
    # Retrieved memory entered graph state
    # --------------------------------------------------------

    assert result["long_term_memories"]

    assert (
        result["long_term_memories"][0]["memory"]["id"]
        == "previous-memory"
    )

    # --------------------------------------------------------
    # Successful execution was persisted
    # --------------------------------------------------------

    assert len(supervisor.calls) == 1

    assert (
        supervisor.calls[0].context[
            "long_term_memories"
        ][0]["memory"]["id"]
        == "previous-memory"
    )
    assert len(
        long_term_memory.add_calls
    ) == 2

    new_memories = [
        memory
        for memory in long_term_memory.add_calls
        if memory.id != "previous-memory"
    ]

    assert len(new_memories) == 1

    stored = new_memories[0]

    assert stored.user_id == "test-user"

    assert stored.task_id == str(task_id)

    assert (
        stored.memory_type
        == "successful_approach"
    )

    assert (
        "Research completed successfully."
        in stored.content
    )