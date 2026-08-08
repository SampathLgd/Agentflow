from pathlib import Path

import pytest

from app.schemas.execution import Specialist
from app.tools.definition import ToolDefinition
from app.tools.file_read import FileReadTool
from app.tools.registry import ToolRegistry


def create_registry(tmp_path: Path) -> ToolRegistry:
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
        },
        allowed_specialists=frozenset({
            "research",
            "writing",
        }),
        rate_limit_per_minute=60,
    )

    registry.register(
        tool,
        definition,
    )

    return registry


def test_registry_stores_definition(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    definition = registry.get_definition(
        "file_read"
    )

    assert definition.name == "file_read"

    assert (
        definition.description
        == "Read a workspace file."
    )

    assert (
        definition.rate_limit_per_minute
        == 60
    )


def test_registry_checks_specialist_access(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    assert registry.has_access(
        "file_read",
        Specialist.RESEARCH,
    )

    assert registry.has_access(
        "file_read",
        Specialist.WRITING,
    )

    assert not registry.has_access(
        "file_read",
        Specialist.DATA_ANALYSIS,
    )


def test_registry_lists_tools(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    assert registry.list_tools() == [
        "file_read"
    ]


def test_registry_rejects_definition_name_mismatch(
    tmp_path: Path,
):
    registry = ToolRegistry()

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    definition = ToolDefinition(
        name="different_name",
        description="Wrong name.",
        input_schema={},
        output_schema={},
    )

    with pytest.raises(ValueError):
        registry.register(
            tool,
            definition,
        )


def test_registry_rejects_duplicate_tool(
    tmp_path: Path,
):
    registry = create_registry(
        tmp_path
    )

    tool = FileReadTool(
        workspace_root=tmp_path
    )

    with pytest.raises(ValueError):
        registry.register(tool)