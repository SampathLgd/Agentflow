from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.execution import Specialist
from app.tools.definition import ToolDefinition
from app.tools.executor import ToolExecutor
from app.tools.file_read import FileReadTool
from app.tools.rate_limiter import (
    InMemoryToolRateLimiter,
    ToolRateLimitExceeded,
)
from app.tools.registry import ToolRegistry
from app.tools.schema_validator import (
    ToolSchemaValidationError,
)


def create_registry(
    tmp_path: Path,
    rate_limit: int | None = 60,
) -> ToolRegistry:

    registry = ToolRegistry()

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    definition = ToolDefinition(
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
            "additionalProperties": False,
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
            "additionalProperties": False,
        },
        allowed_specialists=frozenset({
            "research",
        }),
        rate_limit_per_minute=rate_limit,
    )

    registry.register(
        tool,
        definition,
    )

    return registry


@pytest.mark.asyncio
async def test_tool_input_schema_is_enforced(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    executor = ToolExecutor(
        registry
    )

    with pytest.raises(
        ToolSchemaValidationError
    ):
        await executor.execute(
            task_id=uuid4(),
            subtask_id=None,
            specialist=Specialist.RESEARCH,
            tool_name="file_read",
            arguments={
                "wrong_field": "test.txt",
            },
        )


@pytest.mark.asyncio
async def test_tool_output_schema_is_enforced(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    executor = ToolExecutor(
        registry
    )

    file_path = (
        tmp_path / "test.txt"
    )

    file_path.write_text(
        "hello",
        encoding="utf-8",
    )

    result = await executor.execute(
        task_id=uuid4(),
        subtask_id=None,
        specialist=Specialist.RESEARCH,
        tool_name="file_read",
        arguments={
            "path": "test.txt",
        },
    )

    assert result["content"] == "hello"


@pytest.mark.asyncio
async def test_tool_invocation_records_latency(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    executor = ToolExecutor(
        registry
    )

    file_path = (
        tmp_path / "test.txt"
    )

    file_path.write_text(
        "hello",
        encoding="utf-8",
    )

    await executor.execute(
        task_id=uuid4(),
        subtask_id=None,
        specialist=Specialist.RESEARCH,
        tool_name="file_read",
        arguments={
            "path": "test.txt",
        },
    )

    invocation = executor.invocations[0]

    assert (
        invocation.latency_ms
        is not None
    )

    assert (
        invocation.latency_ms >= 0
    )


@pytest.mark.asyncio
async def test_tool_rate_limit_is_enforced(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path,
        rate_limit=1,
    )

    executor = ToolExecutor(
        registry
    )

    file_path = (
        tmp_path / "test.txt"
    )

    file_path.write_text(
        "hello",
        encoding="utf-8",
    )

    arguments = {
        "path": "test.txt",
    }

    await executor.execute(
        task_id=uuid4(),
        subtask_id=None,
        specialist=Specialist.RESEARCH,
        tool_name="file_read",
        arguments=arguments,
    )

    with pytest.raises(
        ToolRateLimitExceeded
    ):
        await executor.execute(
            task_id=uuid4(),
            subtask_id=None,
            specialist=Specialist.RESEARCH,
            tool_name="file_read",
            arguments=arguments,
        )


def test_rate_limiter_can_be_unlimited():
    limiter = (
        InMemoryToolRateLimiter()
    )

    for _ in range(10):
        limiter.check(
            tool_name="test",
            specialist="research",
            limit_per_minute=None,
        )