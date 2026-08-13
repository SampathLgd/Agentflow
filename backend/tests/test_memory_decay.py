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

        self.deleted_ids: list[str] = []

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        self.memories[memory.id] = (
            memory.model_copy(deep=True)
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

        return [
            MemorySearchResult(
                memory=memory.model_copy(
                    deep=True
                ),
                distance=0.1,
            )
            for memory in memories[:limit]
        ]

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        self.deleted_ids.append(
            memory_id
        )

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
            await self.delete(
                memory_id
            )

    async def count(
        self,
        user_id: str,
    ) -> int:
        return sum(
            memory.user_id == user_id
            for memory in self.memories.values()
        )


def make_memory(
    *,
    memory_id: str,
    importance: float,
    last_accessed_days_ago: int,
    created_days_ago: int = 1,
    user_id: str = "user-1",
) -> LongTermMemory:

    now = datetime.now(
        timezone.utc
    )

    return LongTermMemory(
        id=memory_id,
        user_id=user_id,
        task_id=None,
        memory_type="preference",
        content=f"Memory {memory_id}",
        metadata={
            "_base_importance": importance,
        },
        importance_score=importance,
        created_at=(
            now
            - timedelta(
                days=created_days_ago
            )
        ),
        last_accessed_at=(
            now
            - timedelta(
                days=last_accessed_days_ago
            )
        ),
        access_count=0,
    )


@pytest.mark.asyncio
async def test_recent_memory_has_little_decay():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="recent",
        importance=0.8,
        last_accessed_days_ago=0,
    )

    service = MemoryService(store)

    now = memory.last_accessed_at

    decayed = service.calculate_decay(
        memory,
        now=now,
    )

    assert decayed == 0.8


@pytest.mark.asyncio
async def test_old_memory_decays():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="old",
        importance=0.8,
        last_accessed_days_ago=30,
    )

    service = MemoryService(store)

    now = (
        memory.last_accessed_at
        + timedelta(days=30)
    )

    decayed = service.calculate_decay(
        memory,
        now=now,
    )

    assert decayed < 0.8


@pytest.mark.asyncio
async def test_decay_is_deterministic():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="deterministic",
        importance=0.8,
        last_accessed_days_ago=15,
    )

    service = MemoryService(store)

    now = datetime.now(
        timezone.utc
    )

    first = service.calculate_decay(
        memory,
        now=now,
    )

    second = service.calculate_decay(
        memory,
        now=now,
    )

    assert first == second


@pytest.mark.asyncio
async def test_decay_never_goes_below_zero():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="very-old",
        importance=1.0,
        last_accessed_days_ago=10000,
    )

    service = MemoryService(store)

    now = (
        memory.last_accessed_at
        + timedelta(days=10000)
    )

    decayed = service.calculate_decay(
        memory,
        now=now,
    )

    assert 0.0 <= decayed <= 1.0


@pytest.mark.asyncio
async def test_apply_decay_updates_memory():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="old",
        importance=0.8,
        last_accessed_days_ago=30,
    )

    await store.add(memory)

    service = MemoryService(store)

    now = (
        memory.last_accessed_at
        + timedelta(days=30)
    )

    updated = await service.apply_decay(
        user_id="user-1",
        now=now,
    )

    assert updated == 1

    stored = store.memories["old"]

    assert stored.importance_score < 0.8


@pytest.mark.asyncio
async def test_recent_memory_is_not_expired():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="recent",
        importance=0.2,
        last_accessed_days_ago=1,
        created_days_ago=1,
    )

    await store.add(memory)

    service = MemoryService(
        store,
        retention_days=90,
        min_importance_score=0.5,
    )

    now = datetime.now(
        timezone.utc
    )

    expired = await service.expire_memories(
        user_id="user-1",
        now=now,
    )

    assert expired == 0

    assert (
        "recent"
        in store.memories
    )


@pytest.mark.asyncio
async def test_old_low_value_memory_expires():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="expired",
        importance=0.1,
        last_accessed_days_ago=120,
        created_days_ago=120,
    )

    await store.add(memory)

    service = MemoryService(
        store,
        retention_days=90,
        min_importance_score=0.5,
    )

    now = datetime.now(
        timezone.utc
    )

    expired = await service.expire_memories(
        user_id="user-1",
        now=now,
    )

    assert expired == 1

    assert (
        "expired"
        not in store.memories
    )


@pytest.mark.asyncio
async def test_old_high_value_memory_is_retained():
    store = FakeMemoryStore()

    memory = make_memory(
        memory_id="important",
        importance=1.0,
        last_accessed_days_ago=120,
        created_days_ago=120,
    )

    await store.add(memory)

    service = MemoryService(
        store,
        retention_days=90,
        min_importance_score=0.5,
    )

    now = datetime.now(
        timezone.utc
    )

    expired = await service.expire_memories(
        user_id="user-1",
        now=now,
    )

    assert expired == 0

    assert (
        "important"
        in store.memories
    )


@pytest.mark.asyncio
async def test_decay_and_expiration_return_summary():
    store = FakeMemoryStore()

    old_memory = make_memory(
        memory_id="old",
        importance=0.1,
        last_accessed_days_ago=120,
        created_days_ago=120,
    )

    recent_memory = make_memory(
        memory_id="recent",
        importance=0.8,
        last_accessed_days_ago=1,
        created_days_ago=1,
    )

    await store.add(old_memory)
    await store.add(recent_memory)

    service = MemoryService(
        store,
        retention_days=90,
        min_importance_score=0.5,
    )

    now = datetime.now(
        timezone.utc
    )

    result = (
        await service.apply_decay_and_expiration(
            user_id="user-1",
            now=now,
        )
    )

    assert "decayed" in result
    assert "expired" in result

    assert (
        result["expired"]
        == 1
    )

    assert (
        "old"
        not in store.memories
    )

    assert (
        "recent"
        in store.memories
    )