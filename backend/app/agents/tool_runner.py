from typing import Any
from uuid import UUID

from app.schemas.execution import Specialist
from app.tools.executor import ToolExecutor


class SpecialistToolRunner:
    """
    Controlled tool-use interface available to specialist agents.

    Specialist agents never access concrete tools directly.
    Every invocation goes through ToolExecutor so authorization,
    schema validation, rate limiting, and audit logging remain
    centralized.
    """

    def __init__(
        self,
        executor: ToolExecutor,
    ) -> None:
        self._executor = executor

    async def run(
        self,
        *,
        task_id: UUID,
        subtask_id: UUID | None,
        specialist: Specialist,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        return await self._executor.execute(
            task_id=task_id,
            subtask_id=subtask_id,
            specialist=specialist,
            tool_name=tool_name,
            arguments=arguments,
        )