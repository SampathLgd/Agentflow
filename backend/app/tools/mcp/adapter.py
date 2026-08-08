from typing import Any

from app.schemas.execution import Specialist
from app.tools.base import BaseTool
from app.tools.definition import ToolDefinition
from app.tools.mcp.client import MCPClient


class MCPToolAdapter(BaseTool):
    """
    Adapt an MCP tool to AgentFlow's BaseTool interface.
    """

    def __init__(
        self,
        *,
        client: MCPClient,
        definition: ToolDefinition,
    ) -> None:
        self._client = client
        self._definition = definition

        self.name = definition.name
        self.description = definition.description

        self.allowed_specialists = [
            specialist.value
            if isinstance(
                specialist,
                Specialist,
            )
            else specialist
            for specialist in (
                definition.allowed_specialists
            )
        ]

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> Any:
        return await self._client.call_tool(
            self.name,
            arguments,
        )

    @property
    def definition(
        self,
    ) -> ToolDefinition:
        return self._definition