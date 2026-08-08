import pytest
from uuid import uuid4
from app.tools.executor import ToolExecutor
from app.schemas.execution import Specialist
from app.tools.definition import ToolDefinition
from app.tools.mcp.adapter import MCPToolAdapter
from app.tools.mcp.registry import register_mcp_tools
from app.tools.registry import ToolRegistry


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            ToolDefinition(
                name="mcp_weather",
                description=(
                    "Get weather information."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                        },
                    },
                    "required": [
                        "city",
                    ],
                },
                output_schema={
                    "type": "object",
                },
                allowed_specialists=frozenset(
                    {
                        Specialist.RESEARCH.value,
                    }
                ),
            )
        ]

    async def call_tool(
        self,
        tool_name,
        arguments,
    ):
        self.calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
            }
        )

        return {
            "city": arguments["city"],
            "temperature": 22,
        }


@pytest.mark.asyncio
async def test_mcp_tool_can_be_registered():

    client = FakeMCPClient()
    registry = ToolRegistry()

    registered = await register_mcp_tools(
        client=client,
        registry=registry,
    )

    assert registered == [
        "mcp_weather"
    ]

    assert registry.get(
        "mcp_weather"
    ).name == "mcp_weather"

    assert registry.has_access(
        "mcp_weather",
        Specialist.RESEARCH,
    )

    assert not registry.has_access(
        "mcp_weather",
        Specialist.WRITING,
    )


@pytest.mark.asyncio
async def test_mcp_adapter_invokes_client():

    client = FakeMCPClient()

    definition = ToolDefinition(
        name="mcp_weather",
        description="Get weather information.",
        input_schema={
            "type": "object",
        },
        output_schema={
            "type": "object",
        },
        allowed_specialists=frozenset(
            {
                Specialist.RESEARCH.value,
            }
        ),
    )

    adapter = MCPToolAdapter(
        client=client,
        definition=definition,
    )

    result = await adapter.execute(
        {
            "city": "London",
        }
    )

    assert result == {
        "city": "London",
        "temperature": 22,
    }

    assert client.calls == [
        {
            "tool_name": "mcp_weather",
            "arguments": {
                "city": "London",
            },
        }
    ]

   


@pytest.mark.asyncio
async def test_mcp_tool_runs_through_tool_executor():

    client = FakeMCPClient()

    registry = ToolRegistry()

    await register_mcp_tools(
        client=client,
        registry=registry,
    )

    executor = ToolExecutor(
        registry
    )

    result = await executor.execute(
        task_id=uuid4(),
        subtask_id=None,
        specialist=Specialist.RESEARCH,
        tool_name="mcp_weather",
        arguments={
            "city": "London",
        },
    )

    assert result == {
        "city": "London",
        "temperature": 22,
    }

    assert client.calls == [
        {
            "tool_name": "mcp_weather",
            "arguments": {
                "city": "London",
            },
        }
    ]