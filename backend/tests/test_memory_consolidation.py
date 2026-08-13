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

        memories = memories[:limit]

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
            1
            for memory in self.memories.values()
            if memory.user_id == user_id
        )


def make_memory(
    *,
    memory_id: str,
    content: str,
    importance: float = 0.7,
    access_count: int = 0,
    task_id: str | None = None,
    memory_type: str = "preference",
) -> LongTermMemory:

    now = datetime.now(
        timezone.utc
    )

    return LongTermMemory(
        id=memory_id,
        user_id="user-1",
        task_id=task_id,
        memory_type=memory_type,
        content=content,
        metadata={
            "_base_importance": importance,
            "source": "test",
        },
        importance_score=importance,
        created_at=(
            now
            - timedelta(days=5)
        ),
        last_accessed_at=now,
        access_count=access_count,
    )


@pytest.mark.asyncio
async def test_related_memories_are_consolidated():
    store = FakeMemoryStore()

    first = make_memory(
        memory_id="memory-1",
        content="User prefers Python.",
    )

    second = make_memory(
        memory_id="memory-2",
        content="User prefers FastAPI.",
    )

    await store.add(first)
    await store.add(second)

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="Python FastAPI preferences",
        )
    )

    assert consolidated is not None

    assert (
        "User prefers Python."
        in consolidated.content
    )

    assert (
        "User prefers FastAPI."
        in consolidated.content
    )

    assert consolidated.user_id == "user-1"

    assert (
        consolidated.memory_type
        == "preference"
    )


@pytest.mark.asyncio
async def test_consolidation_deletes_source_memories():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="User likes Python.",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="User likes FastAPI.",
        )
    )

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="Python FastAPI",
        )
    )

    assert consolidated is not None

    assert (
        "memory-1"
        in store.deleted_ids
    )

    assert (
        "memory-2"
        in store.deleted_ids
    )

    assert (
        "memory-1"
        not in store.memories
    )

    assert (
        "memory-2"
        not in store.memories
    )

    assert (
        consolidated.id
        in store.memories
    )


@pytest.mark.asyncio
async def test_consolidation_preserves_highest_importance():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Important preference.",
            importance=0.65,
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="Very important preference.",
            importance=0.9,
        )
    )

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="preferences",
        )
    )

    assert consolidated is not None

    assert (
        consolidated.importance_score
        == 0.9
    )


@pytest.mark.asyncio
async def test_consolidation_aggregates_access_count():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Preference A.",
            access_count=3,
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="Preference B.",
            access_count=5,
        )
    )

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="preferences",
        )
    )

    assert consolidated is not None

    assert (
        consolidated.access_count
        == 8
    )


@pytest.mark.asyncio
async def test_consolidation_records_source_metadata():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Preference A.",
            task_id="task-1",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="Preference B.",
            task_id="task-2",
        )
    )

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="preferences",
        )
    )

    assert consolidated is not None

    assert (
        consolidated.metadata[
            "consolidated"
        ]
        is True
    )

    assert set(
        consolidated.metadata[
            "source_memory_ids"
        ]
    ) == {
        "memory-1",
        "memory-2",
    }

    assert set(
        consolidated.metadata[
            "source_task_ids"
        ]
    ) == {
        "task-1",
        "task-2",
    }

    assert (
        consolidated.metadata[
            "source_memory_count"
        ]
        == 2
    )


@pytest.mark.asyncio
async def test_single_memory_is_not_consolidated():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Only memory.",
        )
    )

    service = MemoryService(
        store
    )

    result = await service.consolidate(
        user_id="user-1",
        query="memory",
    )

    assert result is None

    assert (
        "memory-1"
        in store.memories
    )

    assert store.deleted_ids == []


@pytest.mark.asyncio
async def test_low_importance_memories_are_not_consolidated():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Low value A.",
            importance=0.2,
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="Low value B.",
            importance=0.3,
        )
    )

    service = MemoryService(
        store,
        min_importance_score=0.5,
    )

    result = await service.consolidate(
        user_id="user-1",
        query="low value",
    )

    assert result is None

    assert (
        "memory-1"
        in store.memories
    )

    assert (
        "memory-2"
        in store.memories
    )


@pytest.mark.asyncio
async def test_duplicate_content_is_not_repeated():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="User prefers Python.",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="User prefers Python.",
        )
    )

    service = MemoryService(
        store
    )

    consolidated = (
        await service.consolidate(
            user_id="user-1",
            query="Python",
        )
    )

    assert consolidated is not None

    assert (
        consolidated.content.count(
            "User prefers Python."
        )
        == 1
    )


@pytest.mark.asyncio
async def test_consolidation_is_naturally_idempotent():
    store = FakeMemoryStore()

    await store.add(
        make_memory(
            memory_id="memory-1",
            content="Preference A.",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            content="Preference B.",
        )
    )

    service = MemoryService(
        store
    )

    first = await service.consolidate(
        user_id="user-1",
        query="preferences",
    )

    assert first is not None

    second = await service.consolidate(
        user_id="user-1",
        query="preferences",
    )

    assert second is None

    assert (
        first.id
        in store.memories
    )