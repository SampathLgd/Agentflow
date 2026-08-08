from uuid import uuid4

import pytest

from app.agents.coding.agent import CodeExecutionAgent
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
            "stdout": "Hello from AgentFlow",
            "stderr": "",
            "return_code": 0,
        }


@pytest.mark.asyncio
async def test_code_execution_agent_uses_code_execution_tool():

    runner = FakeToolRunner()

    agent = CodeExecutionAgent(
        tool_runner=runner,
    )

    task_id = uuid4()
    subtask_id = uuid4()

    result = await agent.run(
        AgentInput(
            task_id=task_id,
            subtask_id=subtask_id,
            description=(
                "Execute the requested Python code."
            ),
            context={
                "code": (
                    "print('Hello from AgentFlow')"
                ),
                "timeout": 5,
            },
        )
    )

    assert result.success is True

    assert result.specialist == (
        Specialist.CODE_EXECUTION
    )

    assert len(
        runner.calls
    ) == 1

    call = runner.calls[0]

    assert call["tool_name"] == (
        "code_execution"
    )

    assert call["specialist"] == (
        Specialist.CODE_EXECUTION
    )

    assert call["arguments"] == {
        "code": (
            "print('Hello from AgentFlow')"
        ),
        "timeout": 5,
    }

    assert (
        "Hello from AgentFlow"
        in result.content
    )


@pytest.mark.asyncio
async def test_code_execution_agent_requires_code():

    runner = FakeToolRunner()

    agent = CodeExecutionAgent(
        tool_runner=runner,
    )

    result = await agent.run(
        AgentInput(
            task_id=uuid4(),
            subtask_id=uuid4(),
            description="Run some Python.",
            context={},
        )
    )

    assert result.success is False

    assert (
        result.metadata["error"]
        == "missing_code"
    )

    assert runner.calls == []