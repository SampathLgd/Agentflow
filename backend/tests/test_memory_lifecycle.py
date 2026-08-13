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
        self.memories: dict[
            str,
            LongTermMemory,
        ] = {}

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        self.memories[
            memory.id
        ] = memory.model_copy(
            deep=True
        )

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
                if memory.memory_type
                == memory_type
            ]

        memories = memories[
            :limit
        ]

        return [
            MemorySearchResult(
                memory=memory.model_copy(
                    deep=True
                ),
                distance=0.1,
            )
            for memory in memories
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
            memory_id
            for memory_id, memory
            in self.memories.items()
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
            1
            for memory in self.memories.values()
            if memory.user_id == user_id
        )


def make_memory(
    *,
    memory_id: str = "memory-1",
    user_id: str = "user-1",
    importance: float = 0.6,
) -> LongTermMemory:
    now = datetime.now(
        timezone.utc
    )

    return LongTermMemory(
        id=memory_id,
        user_id=user_id,
        memory_type="preference",
        content="User prefers concise answers.",
        metadata={
            "_base_importance": importance,
        },
        importance_score=importance,
        created_at=now,
        last_accessed_at=now,
        access_count=0,
    )


@pytest.mark.asyncio
async def test_record_access_increments_access_count():
    store = FakeMemoryStore()

    service = MemoryService(
        store
    )

    memory = make_memory()

    await store.add(
        memory
    )

    accessed_at = datetime.now(
        timezone.utc
    )

    updated = await service.record_access(
        memory,
        accessed_at=accessed_at,
    )

    assert updated.access_count == 1
    assert updated.last_accessed_at == accessed_at
    assert updated.importance_score > 0.6


@pytest.mark.asyncio
async def test_repeated_access_increases_importance():
    store = FakeMemoryStore()

    service = MemoryService(
        store
    )

    memory = make_memory(
        importance=0.5
    )

    await service.record_access(
        memory
    )

    first_score = (
        memory.importance_score
    )

    await service.record_access(
        memory
    )

    second_score = (
        memory.importance_score
    )

    assert memory.access_count == 2
    assert second_score > first_score


@pytest.mark.asyncio
async def test_importance_is_capped_at_one():
    store = FakeMemoryStore()

    service = MemoryService(
        store
    )

    memory = make_memory(
        importance=0.95
    )

    for _ in range(20):
        await service.record_access(
            memory
        )

    assert memory.importance_score <= 1.0


@pytest.mark.asyncio
async def test_retrieve_records_access():
    store = FakeMemoryStore()

    memory = make_memory()

    await store.add(
        memory
    )

    service = MemoryService(
        store
    )

    results = await service.retrieve(
        user_id="user-1",
        query="preferences",
    )

    assert len(results) == 1
    assert (
        results[0].memory.access_count
        == 1
    )

    stored = store.memories[
        "memory-1"
    ]

    assert stored.access_count == 1
    assert (
        stored.last_accessed_at
        is not None
    )


@pytest.mark.asyncio
async def test_repeated_retrieval_tracks_access():
    store = FakeMemoryStore()

    memory = make_memory()

    await store.add(
        memory
    )

    service = MemoryService(
        store
    )

    await service.retrieve(
        user_id="user-1",
        query="preferences",
    )

    await service.retrieve(
        user_id="user-1",
        query="preferences",
    )

    stored = store.memories[
        "memory-1"
    ]

    assert stored.access_count == 2
    assert stored.importance_score > 0.6


@pytest.mark.asyncio
async def test_low_importance_memory_is_not_retrieved():
    store = FakeMemoryStore()

    memory = make_memory(
        importance=0.2
    )

    await store.add(
        memory
    )

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    results = await service.retrieve(
        user_id="user-1",
        query="preferences",
    )

    assert results == []

    stored = store.memories[
        "memory-1"
    ]

    assert stored.access_count == 0


@pytest.mark.asyncio
async def test_remember_preserves_base_importance():
    store = FakeMemoryStore()

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    memory = await service.remember(
        user_id="user-1",
        content="User prefers Python.",
        memory_type="preference",
        importance_score=0.7,
    )

    assert memory is not None

    assert (
        memory.metadata[
            "_base_importance"
        ]
        == 0.7
    )

    assert memory.importance_score == 0.7


@pytest.mark.asyncio
async def test_importance_calculation_is_deterministic():
    memory = make_memory(
        importance=0.5
    )

    fixed_time = datetime.now(
        timezone.utc
    )

    memory.last_accessed_at = (
        fixed_time
    )

    score_without_access = (
        MemoryService.calculate_importance(
            memory,
            now=fixed_time,
        )
    )

    memory.access_count = 3

    score_with_access = (
        MemoryService.calculate_importance(
            memory,
            now=fixed_time,
        )
    )

    assert (
        score_with_access
        > score_without_access
    )


@pytest.mark.asyncio
async def test_old_access_has_less_recency_bonus():
    fixed_time = datetime.now(
        timezone.utc
    )

    recent = make_memory(
        importance=0.5
    )

    recent.last_accessed_at = (
        fixed_time
    )

    old = make_memory(
        importance=0.5
    )

    old.last_accessed_at = (
        fixed_time
        - timedelta(days=7)
    )

    recent_score = (
        MemoryService.calculate_importance(
            recent,
            now=fixed_time,
        )
    )

    old_score = (
        MemoryService.calculate_importance(
            old,
            now=fixed_time,
        )
    )

    assert recent_score > old_score