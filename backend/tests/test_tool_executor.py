from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.execution import Specialist
from app.tools.executor import ToolExecutor
from app.tools.file_read import FileReadTool
from app.tools.registry import ToolRegistry

@pytest.mark.asyncio
async def test_tool_executor_executes_and_logs(
    tmp_path: Path,
):
    file_path = tmp_path / "research.txt"

    file_path.write_text(
        "research findings",
        encoding="utf-8",
    )

    registry = ToolRegistry()

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    registry.register(tool)

    executor = ToolExecutor(
        registry
    )

    task_id = uuid4()

    result = await executor.execute(
        task_id=task_id,
        subtask_id=None,
        specialist=Specialist.RESEARCH,
        tool_name="file_read",
        arguments={
            "path": "research.txt",
        },
    )

    assert (
        result["content"]
        == "research findings"
    )

    assert len(
        executor.invocations
    ) == 1

    invocation = executor.invocations[0]

    assert (
        invocation.task_id
        == task_id
    )

    assert (
        invocation.tool_name
        == "file_read"
    )

    assert invocation.success is True
@pytest.mark.asyncio
async def test_tool_executor_rejects_unauthorized_specialist(
    tmp_path: Path,
):
    registry = ToolRegistry()

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    registry.register(tool)

    executor = ToolExecutor(
        registry
    )

    with pytest.raises(PermissionError):
        await executor.execute(
            task_id=uuid4(),
            subtask_id=None,
            specialist=Specialist.DATA_ANALYSIS,
            tool_name="file_read",
            arguments={
                "path": "test.txt",
            },
        )

    assert len(
        executor.invocations
    ) == 1

    assert (
        executor.invocations[0].success
        is False
    )


@pytest.mark.asyncio
async def test_tool_executor_records_failure(
    tmp_path: Path,
):
    registry = ToolRegistry()

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    registry.register(tool)

    executor = ToolExecutor(
        registry
    )

    with pytest.raises(FileNotFoundError):
        await executor.execute(
            task_id=uuid4(),
            subtask_id=None,
            specialist=Specialist.RESEARCH,
            tool_name="file_read",
            arguments={
                "path": "does-not-exist.txt",
            },
        )

    invocation = (
        executor.invocations[0]
    )

    assert invocation.success is False

    assert (
        invocation.error
        is not None
    )