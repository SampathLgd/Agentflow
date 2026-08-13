from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.memory.service import MemoryService


class FakeMemory:
    def __init__(
        self,
        *,
        memory_id: str,
        user_id: str,
        memory_type: str,
        importance: float,
        access_count: int,
        last_accessed_at: datetime,
    ):
        self.id = memory_id
        self.user_id = user_id
        self.memory_type = memory_type
        self.importance_score = importance
        self.access_count = access_count
        self.last_accessed_at = (
            last_accessed_at
        )


class FakeStore:
    def __init__(
        self,
        memories,
    ):
        self.memories = memories

    async def list_user_memories(
        self,
        *,
        user_id: str,
        limit: int = 1000,
    ):
        return [
            memory
            for memory in self.memories
            if memory.user_id == user_id
        ][:limit]


@pytest.mark.asyncio
async def test_dashboard_returns_memory_statistics():
    now = datetime.now(
        timezone.utc
    )

    store = FakeStore(
        [
            FakeMemory(
                memory_id="1",
                user_id="user-1",
                memory_type="preference",
                importance=0.9,
                access_count=5,
                last_accessed_at=now,
            ),
            FakeMemory(
                memory_id="2",
                user_id="user-1",
                memory_type="fact",
                importance=0.4,
                access_count=3,
                last_accessed_at=(
                    now
                    - timedelta(days=100)
                ),
            ),
            FakeMemory(
                memory_id="3",
                user_id="user-1",
                memory_type="fact",
                importance=0.8,
                access_count=2,
                last_accessed_at=now,
            ),
        ]
    )

    service = MemoryService(
        store,
        retention_days=90,
        min_importance_score=0.5,
    )

    result = await service.get_dashboard(
        user_id="user-1",
        now=now,
    )

    assert result["user_id"] == "user-1"
    assert result["total_memories"] == 3

    assert (
        result["high_importance_count"]
        == 2
    )

    assert (
        result["low_importance_count"]
        == 1
    )

    assert (
        result["total_access_count"]
        == 10
    )

    assert (
        result["average_access_count"]
        == pytest.approx(
            10 / 3,
            rel=1e-4,
        )
    )

    assert (
        result["average_importance"]
        == pytest.approx(
            0.7,
            rel=1e-4,
        )
    )

    assert (
        result["stale_memory_count"]
        == 1
    )

    assert (
        result["recent_memory_count"]
        == 2
    )

    assert result["memory_types"] == {
        "preference": 1,
        "fact": 2,
    }


@pytest.mark.asyncio
async def test_dashboard_isolates_users():
    now = datetime.now(
        timezone.utc
    )

    store = FakeStore(
        [
            FakeMemory(
                memory_id="1",
                user_id="user-1",
                memory_type="fact",
                importance=0.9,
                access_count=10,
                last_accessed_at=now,
            ),
            FakeMemory(
                memory_id="2",
                user_id="user-2",
                memory_type="fact",
                importance=0.1,
                access_count=1,
                last_accessed_at=now,
            ),
        ]
    )

    service = MemoryService(
        store
    )

    result = await service.get_dashboard(
        user_id="user-1",
        now=now,
    )

    assert result["total_memories"] == 1
    assert result["total_access_count"] == 10


@pytest.mark.asyncio
async def test_empty_dashboard():
    store = FakeStore([])

    service = MemoryService(
        store
    )

    result = await service.get_dashboard(
        user_id="user-1",
    )

    assert result == {
        "user_id": "user-1",
        "total_memories": 0,
        "average_importance": 0.0,
        "high_importance_count": 0,
        "low_importance_count": 0,
        "total_access_count": 0,
        "average_access_count": 0.0,
        "stale_memory_count": 0,
        "recent_memory_count": 0,
        "memory_types": {},
    }


@pytest.mark.asyncio
async def test_dashboard_rejects_empty_user():
    store = FakeStore([])

    service = MemoryService(
        store
    )

    with pytest.raises(
        ValueError,
        match="user_id cannot be empty",
    ):
        await service.get_dashboard(
            user_id="   ",
        )