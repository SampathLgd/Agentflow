from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """
    Base interface for every AgentFlow tool.

    Every concrete tool must define:
    - name
    - description
    - allowed_specialists
    - execute()
    """

    name: str
    description: str
    allowed_specialists: list[str]

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> Any:
        """
        Execute the tool with validated arguments.
        """
        raise NotImplementedError