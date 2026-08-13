from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.memory.long_term import (
    LongTermMemory,
    MemorySearchResult,
)
from app.memory.service import MemoryService


class FakeMemoryStore:
    def __init__(self) -> None:
        self.memories: dict[str, LongTermMemory] = {}

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        self.memories[memory.id] = memory

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[MemorySearchResult]:

        memories = [
            memory
            for memory in self.memories.values()
            if memory.user_id == user_id
        ]

        if memory_type is not None:
            memories = [
                memory
                for memory in memories
                if memory.memory_type == memory_type
            ]

        return [
            MemorySearchResult(
                memory=memory,
                distance=0.1,
            )
            for memory in memories[:limit]
        ]

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        self.memories.pop(
            memory_id,
            None,
        )

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        ids = [
            memory.id
            for memory in self.memories.values()
            if memory.user_id == user_id
        ]

        for memory_id in ids:
            self.memories.pop(
                memory_id,
                None,
            )

    async def count(
        self,
        user_id: str,
    ) -> int:
        return sum(
            memory.user_id == user_id
            for memory in self.memories.values()
        )


@pytest.mark.asyncio
async def test_memory_service_persists_important_memory():
    store = FakeMemoryStore()

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    memory = await service.remember(
        user_id="user-1",
        task_id="task-1",
        memory_type="successful_approach",
        content="Use web search before analysis.",
        importance_score=0.9,
    )

    assert memory is not None
    assert memory.id in store.memories
    assert memory.content == (
        "Use web search before analysis."
    )


@pytest.mark.asyncio
async def test_memory_service_rejects_low_value_memory():
    store = FakeMemoryStore()

    service = MemoryService(
        store,
        min_importance_score=0.7,
    )

    memory = await service.remember(
        user_id="user-1",
        memory_type="intermediate_result",
        content="Temporary result.",
        importance_score=0.3,
    )

    assert memory is None
    assert store.memories == {}


@pytest.mark.asyncio
async def test_memory_service_retrieves_workflow_memories():
    store = FakeMemoryStore()

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    await service.remember(
        user_id="user-1",
        memory_type="successful_approach",
        content="Use Redis for task-scoped state.",
        importance_score=0.9,
    )

    memories = await service.retrieve_for_workflow(
        user_id="user-1",
        query="Redis working memory",
    )

    assert len(memories) == 1
    assert memories[0]["memory"]["user_id"] == "user-1"
    assert memories[0]["memory"]["memory_type"] == (
        "successful_approach"
    )


@pytest.mark.asyncio
async def test_memory_service_records_access():
    store = FakeMemoryStore()

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    memory = await service.remember(
        user_id="user-1",
        memory_type="user_preference",
        content="User prefers concise answers.",
        importance_score=0.9,
    )

    assert memory is not None
    assert memory.access_count == 0

    previous_access = memory.last_accessed_at

    await service.record_access(
        memory
    )

    assert memory.access_count == 1
    assert memory.last_accessed_at >= previous_access


@pytest.mark.asyncio
async def test_memory_service_counts_user_memories():
    store = FakeMemoryStore()

    service = MemoryService(store)

    await service.remember(
        user_id="user-1",
        memory_type="domain_fact",
        content="Fact one.",
        importance_score=0.9,
    )

    await service.remember(
        user_id="user-1",
        memory_type="domain_fact",
        content="Fact two.",
        importance_score=0.9,
    )

    await service.remember(
        user_id="user-2",
        memory_type="domain_fact",
        content="Other user fact.",
        importance_score=0.9,
    )

    assert (
        await service.count("user-1")
        == 2
    )


@pytest.mark.asyncio
async def test_memory_service_deletes_user_memory():
    store = FakeMemoryStore()

    service = MemoryService(store)

    memory = await service.remember(
        user_id="user-1",
        memory_type="domain_fact",
        content="Delete me.",
        importance_score=0.9,
    )

    assert memory is not None

    await service.delete(
        memory.id
    )

    assert memory.id not in store.memories