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
                    "snippet": (
                        "AgentFlow is an example "
                        "agent orchestration system."
                    ),
                    "url": "https://example.com",
                },
            ],
        }


@pytest.mark.asyncio
async def test_research_agent_uses_web_search():

    runner = FakeToolRunner()

    agent = ResearchAgent(
        tool_runner=runner,
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

    assert result.specialist == (
        Specialist.RESEARCH
    )

    assert len(runner.calls) == 1

    call = runner.calls[0]

    assert call["tool_name"] == (
        "web_search"
    )

    assert call["specialist"] == (
        Specialist.RESEARCH
    )

    assert call["arguments"] == {
        "query": (
            "Research multi-agent orchestration"
        ),
        "max_results": 5,
    }

    assert (
        "AgentFlow"
        in result.content
    )

    assert (
        "https://example.com"
        in result.content
    )