from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.schemas.execution import Specialist


ToolCallable = Callable[
    [dict[str, Any]],
    Awaitable[Any],
]


@dataclass(frozen=True)
class ToolDefinition:
    """
    Metadata and execution contract for one AgentFlow tool.
    """

    name: str

    description: str

    input_schema: dict[str, Any]

    output_schema: dict[str, Any]

    allowed_specialists: frozenset[str] = field(
        default_factory=frozenset,
    )

    rate_limit_per_minute: int = 60

    timeout_seconds: float = 30.0

    handler: ToolCallable | None = None

    def is_allowed(
        self,
        specialist: Specialist,
    ) -> bool:
        return (
            specialist.value
            in self.allowed_specialists
        )