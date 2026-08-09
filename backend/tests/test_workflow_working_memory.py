from __future__ import annotations

from uuid import uuid4

import pytest

from app.graph.workflow import build_workflow
from app.memory.redis_store import RedisWorkingMemoryStore
from app.schemas.execution import Specialist


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
    ) -> None:
        self.data[key] = value

    async def get(
        self,
        key: str,
    ):
        return self.data.get(key)

    async def expire(
        self,
        key: str,
        seconds: int,
    ) -> bool:
        return key in self.data

    async def delete(
        self,
        *keys: str,
    ) -> int:
        deleted = 0

        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1

        return deleted