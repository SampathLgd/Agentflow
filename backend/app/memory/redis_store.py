from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.memory.base import WorkingMemoryStore
from app.memory.models import MemoryErrorRecord


class RedisWorkingMemoryStore(
    WorkingMemoryStore
):
    """
    Redis-backed task-scoped working memory.

    Every task gets its own Redis namespace:

        agentflow:memory:{task_id}:plan
        agentflow:memory:{task_id}:subtask_outputs
        agentflow:memory:{task_id}:intermediate_results
        agentflow:memory:{task_id}:errors

    This prevents memory from leaking between task executions.
    """

    PREFIX = "agentflow:memory"

    PLAN = "plan"
    SUBTASK_OUTPUTS = "subtask_outputs"
    INTERMEDIATE_RESULTS = "intermediate_results"
    ERRORS = "errors"

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    def _key(
        self,
        task_id: str,
        component: str,
    ) -> str:
        return (
            f"{self.PREFIX}:"
            f"{task_id}:"
            f"{component}"
        )

    async def _set_json(
        self,
        key: str,
        value: Any,
    ) -> None:
        await self.redis.set(
            key,
            json.dumps(
                value,
                default=str,
            ),
        )

        if self.ttl_seconds is not None:
            await self.redis.expire(
                key,
                self.ttl_seconds,
            )

    async def _get_json(
        self,
        key: str,
    ) -> Any | None:
        value = await self.redis.get(key)

        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        return json.loads(value)

    async def set_plan(
        self,
        task_id: str,
        plan: dict[str, Any],
    ) -> None:
        await self._set_json(
            self._key(
                task_id,
                self.PLAN,
            ),
            plan,
        )

    async def get_plan(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        result = await self._get_json(
            self._key(
                task_id,
                self.PLAN,
            )
        )

        if result is None:
            return None

        if not isinstance(result, dict):
            raise TypeError(
                "Stored execution plan must be a dictionary."
            )

        return result

    async def add_subtask_output(
        self,
        task_id: str,
        output: dict[str, Any],
    ) -> None:
        key = self._key(
            task_id,
            self.SUBTASK_OUTPUTS,
        )

        outputs = await self._get_json(key)

        if outputs is None:
            outputs = []

        if not isinstance(outputs, list):
            raise TypeError(
                "Stored subtask outputs must be a list."
            )

        outputs.append(output)

        await self._set_json(
            key,
            outputs,
        )

    async def get_subtask_outputs(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        result = await self._get_json(
            self._key(
                task_id,
                self.SUBTASK_OUTPUTS,
            )
        )

        if result is None:
            return []

        if not isinstance(result, list):
            raise TypeError(
                "Stored subtask outputs must be a list."
            )

        return result

    async def set_intermediate_result(
        self,
        task_id: str,
        key: str,
        value: Any,
    ) -> None:
        redis_key = self._key(
            task_id,
            self.INTERMEDIATE_RESULTS,
        )

        results = await self._get_json(redis_key)

        if results is None:
            results = {}

        if not isinstance(results, dict):
            raise TypeError(
                "Stored intermediate results must be a dictionary."
            )

        results[key] = value

        await self._set_json(
            redis_key,
            results,
        )

    async def get_intermediate_results(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        result = await self._get_json(
            self._key(
                task_id,
                self.INTERMEDIATE_RESULTS,
            )
        )

        if result is None:
            return {}

        if not isinstance(result, dict):
            raise TypeError(
                "Stored intermediate results must be a dictionary."
            )

        return result

    async def add_error(
        self,
        task_id: str,
        message: str,
        *,
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = self._key(
            task_id,
            self.ERRORS,
        )

        errors = await self._get_json(key)

        if errors is None:
            errors = []

        if not isinstance(errors, list):
            raise TypeError(
                "Stored errors must be a list."
            )

        record = MemoryErrorRecord(
            message=message,
            source=source,
            metadata=metadata or {},
        )

        errors.append(
            record.model_dump(
                mode="json"
            )
        )

        await self._set_json(
            key,
            errors,
        )

    async def get_errors(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        result = await self._get_json(
            self._key(
                task_id,
                self.ERRORS,
            )
        )

        if result is None:
            return []

        if not isinstance(result, list):
            raise TypeError(
                "Stored errors must be a list."
            )

        return result

    async def snapshot(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "plan": await self.get_plan(
                task_id
            ),
            "subtask_outputs": (
                await self.get_subtask_outputs(
                    task_id
                )
            ),
            "intermediate_results": (
                await self.get_intermediate_results(
                    task_id
                )
            ),
            "errors": await self.get_errors(
                task_id
            ),
        }

    async def clear(
        self,
        task_id: str,
    ) -> None:
        keys = [
            self._key(
                task_id,
                self.PLAN,
            ),
            self._key(
                task_id,
                self.SUBTASK_OUTPUTS,
            ),
            self._key(
                task_id,
                self.INTERMEDIATE_RESULTS,
            ),
            self._key(
                task_id,
                self.ERRORS,
            ),
        ]

        await self.redis.delete(*keys)