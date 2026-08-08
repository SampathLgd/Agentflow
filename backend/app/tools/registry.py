from app.schemas.execution import Specialist
from app.tools.base import BaseTool
from app.tools.definition import ToolDefinition
from typing import List


class ToolRegistry:
    """
    Central registry for AgentFlow custom tools.

    The registry stores both the executable tool and its
    declarative ToolDefinition.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(
        self,
        tool: BaseTool,
        definition: ToolDefinition | None = None,
    ) -> None:
        """
        Register a tool and its metadata definition.
        """

        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered."
            )

        if definition is None:
            definition = ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema={},
                output_schema={},
                allowed_specialists=frozenset(
                    tool.allowed_specialists
                ),
            )

        if definition.name != tool.name:
            raise ValueError(
                "ToolDefinition name must match tool.name."
            )

        self._tools[tool.name] = tool
        self._definitions[tool.name] = definition

    def get(
        self,
        name: str,
    ) -> BaseTool:
        """
        Retrieve an executable tool by name.
        """

        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(
                f"Tool '{name}' is not registered."
            ) from exc

    def get_definition(
        self,
        name: str,
    ) -> ToolDefinition:
        """
        Retrieve tool metadata by name.
        """

        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(
                f"Tool definition '{name}' is not registered."
            ) from exc

    def has_access(
        self,
        name: str,
        specialist: Specialist,
    ) -> bool:
        """
        Check whether a specialist is authorized to use a tool.
        """

        definition = self.get_definition(name)

        return definition.is_allowed(
            specialist
        )

    def list_tools(self) -> list[str]:
        """
        Return registered tool names.
        """

        return list(self._tools.keys())

    def list(self) -> list[str]:
        """
        Backward-compatible alias for list_tools().
        """

        return self.list_tools()

    def list_definitions(self) -> List[ToolDefinition]:
        """
        Return all registered tool definitions.
        """

        return list(
            self._definitions.values()
        )