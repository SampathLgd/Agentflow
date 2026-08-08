from pathlib import Path

import pytest

from app.tools.file_write import FileWriteTool


@pytest.mark.asyncio
async def test_file_write_tool_writes_workspace_file(
    tmp_path: Path,
):
    tool = FileWriteTool(
        workspace_root=tmp_path
    )

    result = await tool.execute(
        {
            "path": "output/report.txt",
            "content": "AgentFlow report",
        }
    )

    output_file = (
        tmp_path
        / "output"
        / "report.txt"
    )

    assert output_file.exists()

    assert (
        output_file.read_text(
            encoding="utf-8"
        )
        == "AgentFlow report"
    )

    assert result["path"] == "output/report.txt"


@pytest.mark.asyncio
async def test_file_write_tool_rejects_path_traversal(
    tmp_path: Path,
):
    tool = FileWriteTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "path": "../outside.txt",
                "content": "should not be written",
            }
        )


@pytest.mark.asyncio
async def test_file_write_tool_requires_content(
    tmp_path: Path,
):
    tool = FileWriteTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "path": "output.txt",
            })


@pytest.mark.asyncio
async def test_file_write_tool_requires_path(
    tmp_path: Path,
):
    tool = FileWriteTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "content": "missing path",
            })