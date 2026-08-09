from __future__ import annotations

import json

import pytest

from app.memory.redis_store import (
    RedisWorkingMemoryStore,
)


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


@pytest.fixture
def store() -> RedisWorkingMemoryStore:
    return RedisWorkingMemoryStore(
        FakeRedis()
    )


@pytest.mark.asyncio
async def test_working_memory_stores_plan(
    store: RedisWorkingMemoryStore,
) -> None:
    plan = {
        "task_id": "task-1",
        "subtasks": [
            {
                "id": "subtask-1",
                "description": "Research topic",
            }
        ],
    }

    await store.set_plan(
        "task-1",
        plan,
    )

    assert await store.get_plan(
        "task-1"
    ) == plan


@pytest.mark.asyncio
async def test_working_memory_stores_subtask_outputs(
    store: RedisWorkingMemoryStore,
) -> None:
    output = {
        "subtask_id": "subtask-1",
        "content": "Research completed.",
    }

    await store.add_subtask_output(
        "task-1",
        output,
    )

    assert await store.get_subtask_outputs(
        "task-1"
    ) == [output]


@pytest.mark.asyncio
async def test_working_memory_stores_intermediate_results(
    store: RedisWorkingMemoryStore,
) -> None:
    await store.set_intermediate_result(
        "task-1",
        "research_count",
        42,
    )

    await store.set_intermediate_result(
        "task-1",
        "status",
        "processing",
    )

    result = await store.get_intermediate_results(
        "task-1"
    )

    assert result == {
        "research_count": 42,
        "status": "processing",
    }


@pytest.mark.asyncio
async def test_working_memory_stores_errors(
    store: RedisWorkingMemoryStore,
) -> None:
    await store.add_error(
        "task-1",
        "Research tool failed.",
        source="research",
        metadata={
            "tool": "web_search",
        },
    )

    errors = await store.get_errors(
        "task-1"
    )

    assert len(errors) == 1
    assert errors[0]["message"] == (
        "Research tool failed."
    )
    assert errors[0]["source"] == "research"
    assert errors[0]["metadata"]["tool"] == (
        "web_search"
    )


@pytest.mark.asyncio
async def test_working_memory_isolated_by_task(
    store: RedisWorkingMemoryStore,
) -> None:
    await store.set_plan(
        "task-a",
        {"name": "plan-a"},
    )

    await store.set_plan(
        "task-b",
        {"name": "plan-b"},
    )

    assert await store.get_plan(
        "task-a"
    ) == {"name": "plan-a"}

    assert await store.get_plan(
        "task-b"
    ) == {"name": "plan-b"}


@pytest.mark.asyncio
async def test_working_memory_snapshot(
    store: RedisWorkingMemoryStore,
) -> None:
    await store.set_plan(
        "task-1",
        {"name": "plan"},
    )

    await store.add_subtask_output(
        "task-1",
        {"content": "done"},
    )

    await store.set_intermediate_result(
        "task-1",
        "count",
        10,
    )

    await store.add_error(
        "task-1",
        "temporary error",
    )

    snapshot = await store.snapshot(
        "task-1"
    )

    assert snapshot["task_id"] == "task-1"
    assert snapshot["plan"] == {
        "name": "plan"
    }
    assert snapshot["subtask_outputs"] == [
        {"content": "done"}
    ]
    assert snapshot["intermediate_results"] == {
        "count": 10
    }
    assert len(snapshot["errors"]) == 1


@pytest.mark.asyncio
async def test_working_memory_clear(
    store: RedisWorkingMemoryStore,
) -> None:
    await store.set_plan(
        "task-1",
        {"name": "plan"},
    )

    await store.add_subtask_output(
        "task-1",
        {"content": "done"},
    )

    await store.set_intermediate_result(
        "task-1",
        "count",
        10,
    )

    await store.add_error(
        "task-1",
        "temporary error",
    )

    await store.clear(
        "task-1"
    )

    snapshot = await store.snapshot(
        "task-1"
    )

    assert snapshot == {
        "task_id": "task-1",
        "plan": None,
        "subtask_outputs": [],
        "intermediate_results": {},
        "errors": [],
    }