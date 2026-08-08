import sqlite3
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.schemas.execution import Specialist
from app.tools.api_call import APICallTool
from app.tools.database_query import DatabaseQueryTool
from app.tools.definition import ToolDefinition
from app.tools.executor import ToolExecutor
from app.tools.file_read import FileReadTool
from app.tools.file_write import FileWriteTool
from app.tools.registry import ToolRegistry
from app.tools.web_search import WebSearchTool
from app.tools.builtin_definitions import (
    API_CALL_DEFINITION,
    DATABASE_QUERY_DEFINITION,
    WEB_SEARCH_DEFINITION,
)


def build_registry(
    tmp_path: Path,
    http_client: httpx.AsyncClient,
) -> ToolRegistry:

    registry = ToolRegistry()

    registry.register(
        FileReadTool(
            workspace_root=tmp_path
        ),
        ToolDefinition(
            name="file_read",
            description="Read a workspace file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                },
                "required": ["path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "content": {
                        "type": "string",
                    },
                },
                "required": [
                    "path",
                    "content",
                ],
            },
            allowed_specialists=frozenset({
                "research",
                "writing",
            }),
            rate_limit_per_minute=60,
        ),
    )

    registry.register(
        FileWriteTool(
            workspace_root=tmp_path
        ),
        ToolDefinition(
            name="file_write",
            description="Write a workspace file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "content": {
                        "type": "string",
                    },
                },
                "required": [
                    "path",
                    "content",
                ],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "bytes_written": {
                        "type": "integer",
                    },
                },
                "required": [
                    "path",
                    "bytes_written",
                ],
            },
            allowed_specialists=frozenset({
                "research",
                "writing",
                "code_execution",
            }),
            rate_limit_per_minute=30,
        ),
    )

    registry.register(
        WebSearchTool(
            client=http_client
        ),
        WEB_SEARCH_DEFINITION,
    )

    registry.register(
        DatabaseQueryTool(
            tmp_path / "test.db"
        ),
        DATABASE_QUERY_DEFINITION,
    )

    registry.register(
        APICallTool(
            allowed_hosts={
                "api.example.com",
            },
            client=http_client,
        ),
        API_CALL_DEFINITION,
    )

    return registry


@pytest.mark.asyncio
async def test_tool_executor_invokes_multiple_tool_types(
    tmp_path: Path,
):

    database = tmp_path / "test.db"

    connection = sqlite3.connect(
        database
    )

    connection.execute(
        "CREATE TABLE items (id INTEGER, name TEXT)"
    )

    connection.execute(
        "INSERT INTO items VALUES (1, 'AgentFlow')"
    )

    connection.commit()
    connection.close()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        if request.url.host == (
            "api.example.com"
        ):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                },
            )

        return httpx.Response(
            200,
            json={
                "Heading": "AgentFlow",
                "AbstractText": (
                    "Agent orchestration system."
                ),
                "AbstractURL": (
                    "https://example.com/agentflow"
                ),
                "RelatedTopics": [],
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:

        registry = build_registry(
            tmp_path,
            client,
        )

        executor = ToolExecutor(
            registry
        )

        task_id = uuid4()

        search_result = await executor.execute(
            task_id=task_id,
            subtask_id=None,
            specialist=Specialist.RESEARCH,
            tool_name="web_search",
            arguments={
                "query": "AgentFlow",
            },
        )

        database_result = await executor.execute(
            task_id=task_id,
            subtask_id=None,
            specialist=Specialist.DATA_ANALYSIS,
            tool_name="database_query",
            arguments={
                "query": (
                    "SELECT name "
                    "FROM items"
                ),
            },
        )

        api_result = await executor.execute(
            task_id=task_id,
            subtask_id=None,
            specialist=Specialist.RESEARCH,
            tool_name="api_call",
            arguments={
                "url": (
                    "https://api.example.com/status"
                ),
            },
        )

    assert search_result["query"] == "AgentFlow"

    assert (
        database_result["rows"][0]["name"]
        == "AgentFlow"
    )

    assert api_result["status_code"] == 200

    assert len(
        executor.invocations
    ) == 3

    assert all(
        invocation.success
        for invocation in executor.invocations
    )

    assert all(
        invocation.latency_ms is not None
        for invocation in executor.invocations
    )

    assert {
        invocation.tool_name
        for invocation in executor.invocations
    } == {
        "web_search",
        "database_query",
        "api_call",
    }

    assert all(
        invocation.task_id == task_id
        for invocation in executor.invocations
    )