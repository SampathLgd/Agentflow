from uuid import uuid4

import pytest

from app.agents.research.agent import ResearchAgent
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
            "query": arguments["query"],
            "results": [
                {
                    "title": "AgentFlow",
                    "url": "https://example.com",
                    "snippet": "Example result.",
                }
            ],
        }


@pytest.mark.asyncio
async def test_research_agent_uses_web_search():

    runner = FakeToolRunner()

    agent = ResearchAgent(
        tool_runner=runner
    )

    task_id = uuid4()
    subtask_id = uuid4()

    result = await agent.run(
        AgentInput(
            task_id=task_id,
            subtask_id=subtask_id,
            description=(
                "Research multi-agent orchestration"
            ),
        )
    )

    assert result.success is True

    assert (
        runner.calls[0]["tool_name"]
        == "web_search"
    )

    assert (
        runner.calls[0]["specialist"]
        == Specialist.RESEARCH
    )

    assert (
        runner.calls[0]["arguments"]["query"]
        == "Research multi-agent orchestration"
    )

    assert (
        "Example result."
        in result.content
    )