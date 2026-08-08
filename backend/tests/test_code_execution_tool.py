from pathlib import Path

import pytest

from app.tools.code_execution import CodeExecutionTool


@pytest.mark.asyncio
async def test_code_execution_tool_runs_python(
    tmp_path: Path,
):
    tool = CodeExecutionTool(
        workspace_root=tmp_path
    )

    result = await tool.execute(
        {
            "code": "print('hello AgentFlow')",
        }
    )

    assert result["stdout"].strip() == (
        "hello AgentFlow"
    )

    assert result["exit_code"] == 0
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_code_execution_tool_captures_stderr(
    tmp_path: Path,
):
    tool = CodeExecutionTool(
        workspace_root=tmp_path
    )

    result = await tool.execute(
        {
            "code": (
                "import sys; "
                "print('failure', file=sys.stderr); "
                "raise SystemExit(2)"
            ),
        }
    )

    assert "failure" in result["stderr"]

    assert result["exit_code"] == 2


@pytest.mark.asyncio
async def test_code_execution_tool_times_out(
    tmp_path: Path,
):
    tool = CodeExecutionTool(
        workspace_root=tmp_path
    )

    result = await tool.execute(
        {
            "code": (
                "import time; "
                "time.sleep(10)"
            ),
            "timeout_seconds": 0.1,
        }
    )

    assert result["timed_out"] is True


@pytest.mark.asyncio
async def test_code_execution_tool_rejects_empty_code(
    tmp_path: Path,
):
    tool = CodeExecutionTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "code": "",
            }
        )


@pytest.mark.asyncio
async def test_code_execution_tool_rejects_excessive_timeout(
    tmp_path: Path,
):
    tool = CodeExecutionTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "code": "print('hello')",
                "timeout_seconds": 31,
            }
        )