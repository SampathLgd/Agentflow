from uuid import uuid4

import pytest

from app.agents.writing.agent import WritingAgent
from app.schemas.agent import AgentInput
from app.schemas.execution import Specialist


class FakeLLMRouter:
    async def ainvoke(
        self,
        *,
        task_type,
        prompt,
    ):
        class Response:
            content = (
                "This is the generated final document."
            )

        return Response()


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

        if tool_name == "file_read":
            return {
                "path": arguments["path"],
                "content": (
                    "Existing research material."
                ),
            }

        if tool_name == "file_write":
            return {
                "path": arguments["path"],
                "bytes_written": len(
                    arguments["content"].encode(
                        "utf-8"
                    )
                ),
            }

        raise AssertionError(
            f"Unexpected tool: {tool_name}"
        )


@pytest.mark.asyncio
async def test_writing_agent_reads_and_writes_files():

    tool_runner = FakeToolRunner()

    agent = WritingAgent(
        llm_router=FakeLLMRouter(),
        tool_runner=tool_runner,
    )

    result = await agent.run(
        AgentInput(
            task_id=uuid4(),
            subtask_id=uuid4(),
            description=(
                "Prepare a final research report."
            ),
            context={
                "expected_output": (
                    "A concise research report."
                ),
                "input_path": "research.txt",
                "output_path": "report.txt",
                "completed_outputs": [],
            },
        )
    )

    assert result.success is True

    assert result.specialist == (
        Specialist.WRITING
    )

    assert result.content == (
        "This is the generated final document."
    )

    assert len(tool_runner.calls) == 2

    assert tool_runner.calls[0]["tool_name"] == (
        "file_read"
    )

    assert tool_runner.calls[0]["arguments"] == {
        "path": "research.txt",
    }

    assert tool_runner.calls[1]["tool_name"] == (
        "file_write"
    )

    assert tool_runner.calls[1]["arguments"] == {
        "path": "report.txt",
        "content": (
            "This is the generated final document."
        ),
    }


@pytest.mark.asyncio
async def test_writing_agent_can_return_without_file_tools():

    tool_runner = FakeToolRunner()

    agent = WritingAgent(
        llm_router=FakeLLMRouter(),
        tool_runner=tool_runner,
    )

    result = await agent.run(
        AgentInput(
            task_id=uuid4(),
            subtask_id=uuid4(),
            description="Write a short summary.",
            context={},
        )
    )

    assert result.success is True

    assert result.content == (
        "This is the generated final document."
    )

    assert tool_runner.calls == []