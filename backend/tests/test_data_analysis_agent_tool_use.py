from uuid import uuid4

import pytest

from app.agents.analysis.agent import DataAnalysisAgent
from app.schemas.agent import AgentInput
from app.schemas.execution import Specialist


class FakeToolRunner:
    def __init__(self):
        self.calls = []

    async def run(
        self,
        *,
        task_id,
        subtask_id,
        specialist,
        tool_name,
        arguments,
    ):
        self.calls.append(
            {
                "task_id": task_id,
                "subtask_id": subtask_id,
                "specialist": specialist,
                "tool_name": tool_name,
                "arguments": arguments,
            }
        )

        return {
            "columns": [
                "name",
                "score",
            ],
            "rows": [
                ["Alice", 95],
                ["Bob", 88],
            ],
            "row_count": 2,
        }


@pytest.mark.asyncio
async def test_data_analysis_agent_uses_database_query():

    runner = FakeToolRunner()

    agent = DataAnalysisAgent(
        tool_runner=runner,
    )

    task_id = uuid4()
    subtask_id = uuid4()

    result = await agent.run(
        AgentInput(
            task_id=task_id,
            subtask_id=subtask_id,
            description=(
                "Analyze the student scores."
            ),
            context={
                "sql_query": (
                    "SELECT name, score "
                    "FROM students "
                    "WHERE score >= :minimum"
                ),
                "sql_parameters": {
                    "minimum": 80,
                },
            },
        )
    )

    assert result.success is True

    assert result.specialist == (
        Specialist.DATA_ANALYSIS
    )

    assert len(
        runner.calls
    ) == 1

    call = runner.calls[0]

    assert call["tool_name"] == (
        "database_query"
    )

    assert call["specialist"] == (
        Specialist.DATA_ANALYSIS
    )

    assert call["arguments"] == {
        "query": (
            "SELECT name, score "
            "FROM students "
            "WHERE score >= :minimum"
        ),
        "parameters": {
            "minimum": 80,
        },
    }

    assert (
        "2 row(s)"
        in result.content
    )

    assert (
        "Alice"
        in result.content
    )


@pytest.mark.asyncio
async def test_data_analysis_agent_requires_sql_query():

    runner = FakeToolRunner()

    agent = DataAnalysisAgent(
        tool_runner=runner,
    )

    result = await agent.run(
        AgentInput(
            task_id=uuid4(),
            subtask_id=uuid4(),
            description="Analyze student data.",
            context={},
        )
    )

    assert result.success is False

    assert (
        result.metadata["error"]
        == "missing_sql_query"
    )

    assert runner.calls == []