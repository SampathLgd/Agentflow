from typing import Any
from uuid import UUID
from datetime import datetime, timezone
import time
from app.schemas.execution import Specialist
from app.schemas.tool_invocation import ToolInvocation
from app.tools.rate_limiter import (
    InMemoryToolRateLimiter,
)
from app.tools.registry import ToolRegistry
from app.tools.schema_validator import (
    validate_tool_input,
    validate_tool_output,
)


class ToolExecutor:
    """
    Controlled execution boundary for all AgentFlow tools.

    Responsibilities:
    - resolve tools through the registry
    - enforce specialist authorization
    - enforce input schemas
    - enforce rate limits
    - execute the tool
    - validate outputs
    - capture invocation/audit information
    """

    def __init__(
        self,
        registry: ToolRegistry,
        rate_limiter: InMemoryToolRateLimiter | None = None,
    ) -> None:
        self.registry = registry

        self.rate_limiter = (
            rate_limiter
            if rate_limiter is not None
            else InMemoryToolRateLimiter()
        )

        self.invocations: list[
            ToolInvocation
        ] = []

    async def execute(
        self,
        *,
        task_id: UUID,
        subtask_id: UUID | None,
        specialist: Specialist,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:

        tool = self.registry.get(
            tool_name
        )

        definition = (
            self.registry.get_definition(
                tool_name
            )
        )

        invocation = ToolInvocation(
            task_id=task_id,
            subtask_id=subtask_id,
            specialist=specialist.value,
            tool_name=tool_name,
            arguments=arguments,
            success=False,
        )
        started = time.perf_counter()

        self.invocations.append(
            invocation
        )

        try:
            # -------------------------------------------------
            # Authorization
            # -------------------------------------------------

            if not definition.is_allowed(
                specialist
            ):
                raise PermissionError(
                    f"Specialist '{specialist.value}' "
                    f"is not allowed to use tool "
                    f"'{tool_name}'."
                )

            # -------------------------------------------------
            # Rate limit
            # -------------------------------------------------

            self.rate_limiter.check(
                tool_name=tool_name,
                specialist=specialist.value,
                limit_per_minute=(
                    definition.rate_limit_per_minute
                ),
            )

            # -------------------------------------------------
            # Input validation
            # -------------------------------------------------

            validate_tool_input(
                definition.input_schema,
                arguments,
            )

            # -------------------------------------------------
            # Tool execution
            # -------------------------------------------------

            result = await tool.execute(
                arguments
            )

            # -------------------------------------------------
            # Output validation
            # -------------------------------------------------

            validate_tool_output(
                definition.output_schema,
                result,
            )

            invocation.success = True
            invocation.result = result

            return result

        except Exception as exc:
            invocation.success = False
            invocation.error = str(exc)

            raise
        finally:
            invocation.completed_at = datetime.now(
                timezone.utc
            )

            invocation.latency_ms = (
                time.perf_counter() - started
            ) * 1000