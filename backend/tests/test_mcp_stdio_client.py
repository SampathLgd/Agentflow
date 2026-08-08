from pathlib import Path

import pytest

from app.tools.mcp.client import (
    StdioMCPClient,
)


@pytest.mark.asyncio
async def test_stdio_mcp_client_discovers_tools():

    server_path = (
        Path(__file__).parent
        / "fixtures"
        / "mcp_test_server.py"
    )

    client = StdioMCPClient(
        command="python",
        args=[
            str(server_path),
        ],
    )

    async with client:

        tools = await client.list_tools()

    assert len(tools) == 1

    assert tools[0]["name"] == (
        "get_weather"
    )

    assert (
        "city"
        in tools[0]["input_schema"]["properties"]
    )


@pytest.mark.asyncio
async def test_stdio_mcp_client_calls_tool():

    server_path = (
        Path(__file__).parent
        / "fixtures"
        / "mcp_test_server.py"
    )

    client = StdioMCPClient(
        command="python",
        args=[
            str(server_path),
        ],
    )

    async with client:

        result = await client.call_tool(
            "get_weather",
            {
                "city": "London",
            },
        )

    assert result is not None