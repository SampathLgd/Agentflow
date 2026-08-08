import time
from collections import defaultdict, deque


class ToolRateLimitExceeded(RuntimeError):
    """
    Raised when a tool exceeds its configured invocation limit.
    """


class InMemoryToolRateLimiter:
    """
    Simple process-local sliding-window rate limiter.

    This is appropriate for the current Phase 1 development
    environment.

    Later, when the system moves to Redis/Celery/Kubernetes,
    this boundary can be replaced with a distributed limiter
    without changing ToolExecutor.
    """

    def __init__(self) -> None:
        self._calls: dict[
            tuple[str, str],
            deque[float],
        ] = defaultdict(deque)

    def check(
        self,
        *,
        tool_name: str,
        specialist: str,
        limit_per_minute: int | None,
    ) -> None:
        """
        Enforce the configured per-tool/per-specialist limit.
        """

        if limit_per_minute is None:
            return

        now = time.monotonic()

        key = (
            tool_name,
            specialist,
        )

        calls = self._calls[key]

        cutoff = now - 60.0

        while calls and calls[0] <= cutoff:
            calls.popleft()

        if len(calls) >= limit_per_minute:
            raise ToolRateLimitExceeded(
                f"Tool '{tool_name}' exceeded its "
                f"rate limit of {limit_per_minute} "
                "calls per minute."
            )

        calls.append(now)