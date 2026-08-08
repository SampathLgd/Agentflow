from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.execution import Specialist
from app.tools.file_read import FileReadTool


@pytest.mark.asyncio
async def test_file_read_tool_reads_workspace_file(
    tmp_path: Path,
):
    file_path = tmp_path / "research.txt"

    file_path.write_text(
        "AgentFlow research data",
        encoding="utf-8",
    )

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    result = await tool.execute(
        {
            "path": "research.txt",
        }
    )

    assert result["path"] == "research.txt"

    assert (
        result["content"]
        == "AgentFlow research data"
    )


@pytest.mark.asyncio
async def test_file_read_tool_rejects_path_traversal(
    tmp_path: Path,
):
    secret = tmp_path.parent / "secret.txt"

    secret.write_text(
        "secret",
        encoding="utf-8",
    )

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "path": "../secret.txt",
            }
        )


@pytest.mark.asyncio
async def test_file_read_tool_requires_path(
    tmp_path: Path,
):
    tool = FileReadTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute({})