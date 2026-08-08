from pathlib import Path

from app.tools.registry import ToolRegistry
from app.tools.file_read import FileReadTool
from app.tools.file_write import FileWriteTool
from app.tools.web_search import WebSearchTool
from app.tools.database_query import DatabaseQueryTool
from app.tools.api_call import APICallTool
from app.tools.code_execution import CodeExecutionTool

from app.tools.builtin_definitions import (
    API_CALL_DEFINITION,
    DATABASE_QUERY_DEFINITION,
    WEB_SEARCH_DEFINITION,
)


def create_builtin_registry(
    *,
    workspace_root: Path,
    database_path: Path,
    allowed_api_hosts: set[str],
    code_execution_tool: CodeExecutionTool,
) -> ToolRegistry:

    registry = ToolRegistry()

    registry.register(
        FileReadTool(
            workspace_root=workspace_root,
        )
    )

    registry.register(
        FileWriteTool(
            workspace_root=workspace_root,
        )
    )

    registry.register(
        code_execution_tool
    )

    registry.register(
        WebSearchTool(),
        WEB_SEARCH_DEFINITION,
    )

    registry.register(
        DatabaseQueryTool(
            database_path=database_path,
        ),
        DATABASE_QUERY_DEFINITION,
    )

    registry.register(
        APICallTool(
            allowed_hosts=allowed_api_hosts,
        ),
        API_CALL_DEFINITION,
    )

    return registry