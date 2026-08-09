from __future__ import annotations

import pytest

from app.memory.chroma_store import (
    ChromaLongTermMemoryStore,
)
from app.memory.long_term import (
    LongTermMemory,
)


class FakeChromaCollection:
    """
    Async fake implementing the subset of Chroma used by
    ChromaLongTermMemoryStore.

    This tests our application adapter without requiring a
    running Chroma server.
    """

    def __init__(self) -> None:
        self.records: dict[
            str,
            dict,
        ] = {}

    async def upsert(
        self,
        *,
        ids,
        documents,
        metadatas,
    ) -> None:
        for index, memory_id in enumerate(
            ids
        ):
            self.records[memory_id] = {
                "document": documents[index],
                "metadata": metadatas[index],
            }

    async def query(
        self,
        *,
        query_texts,
        n_results,
        where,
    ):
        matched = []

        for memory_id, record in (
            self.records.items()
        ):
            metadata = record["metadata"]

            if not self._matches(
                metadata,
                where,
            ):
                continue

            matched.append(
                (
                    memory_id,
                    record,
                )
            )

        matched = matched[
            :n_results
        ]

        return {
            "ids": [
                [
                    item[0]
                    for item in matched
                ]
            ],
            "documents": [
                [
                    item[1]["document"]
                    for item in matched
                ]
            ],
            "metadatas": [
                [
                    item[1]["metadata"]
                    for item in matched
                ]
            ],
            "distances": [
                [
                    0.1
                    for _ in matched
                ]
            ],
        }

    async def delete(
        self,
        *,
        ids=None,
        where=None,
    ) -> None:
        if ids is not None:
            for memory_id in ids:
                self.records.pop(
                    memory_id,
                    None,
                )

            return

        if where is not None:
            to_delete = [
                memory_id
                for memory_id, record
                in self.records.items()
                if self._matches(
                    record["metadata"],
                    where,
                )
            ]

            for memory_id in to_delete:
                del self.records[
                    memory_id
                ]

    async def get(
        self,
        *,
        where,
        include,
    ):
        ids = [
            memory_id
            for memory_id, record
            in self.records.items()
            if self._matches(
                record["metadata"],
                where,
            )
        ]

        return {
            "ids": ids,
        }

    @staticmethod
    def _matches(
        metadata,
        where,
    ) -> bool:
        if "$and" in where:
            return all(
                FakeChromaCollection._matches(
                    metadata,
                    condition,
                )
                for condition in where[
                    "$and"
                ]
            )

        return all(
            metadata.get(key) == value
            for key, value in where.items()
        )


def make_memory(
    *,
    memory_id: str = "memory-1",
    user_id: str = "user-1",
    task_id: str = "task-1",
    memory_type: str = "successful_approach",
    content: str = (
        "Used web search before analysis."
    ),
) -> LongTermMemory:
    return LongTermMemory(
        id=memory_id,
        user_id=user_id,
        task_id=task_id,
        memory_type=memory_type,
        content=content,
        metadata={
            "tools": [
                "web_search",
            ],
            "specialist": "research",
        },
        importance_score=0.9,
    )


@pytest.mark.asyncio
async def test_chroma_memory_can_be_added():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    memory = make_memory()

    await store.add(
        memory
    )

    assert "memory-1" in collection.records

    stored = collection.records[
        "memory-1"
    ]

    assert (
        stored["document"]
        == memory.content
    )

    assert (
        stored["metadata"]["user_id"]
        == "user-1"
    )


@pytest.mark.asyncio
async def test_chroma_memory_can_be_searched():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory()
    )

    results = await store.search(
        user_id="user-1",
        query="web search research",
        limit=5,
    )

    assert len(results) == 1

    assert (
        results[0].memory.content
        == "Used web search before analysis."
    )

    assert (
        results[0].memory.user_id
        == "user-1"
    )


@pytest.mark.asyncio
async def test_chroma_memory_isolated_by_user():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory(
            memory_id="memory-1",
            user_id="user-1",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            user_id="user-2",
        )
    )

    results = await store.search(
        user_id="user-1",
        query="research",
    )

    assert len(results) == 1

    assert (
        results[0].memory.user_id
        == "user-1"
    )


@pytest.mark.asyncio
async def test_chroma_memory_can_filter_by_type():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory(
            memory_id="memory-1",
            memory_type="successful_approach",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            memory_type="domain_fact",
        )
    )

    results = await store.search(
        user_id="user-1",
        query="research",
        memory_type="domain_fact",
    )

    assert len(results) == 1

    assert (
        results[0].memory.memory_type
        == "domain_fact"
    )


@pytest.mark.asyncio
async def test_chroma_memory_can_delete_one():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory()
    )

    await store.delete(
        "memory-1"
    )

    assert collection.records == {}


@pytest.mark.asyncio
async def test_chroma_memory_can_delete_user():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory(
            memory_id="memory-1",
            user_id="user-1",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            user_id="user-2",
        )
    )

    await store.delete_user(
        "user-1"
    )

    assert "memory-1" not in collection.records

    assert "memory-2" in collection.records


@pytest.mark.asyncio
async def test_chroma_memory_count_is_user_scoped():
    collection = FakeChromaCollection()

    store = ChromaLongTermMemoryStore(
        collection
    )

    await store.add(
        make_memory(
            memory_id="memory-1",
            user_id="user-1",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-2",
            user_id="user-1",
        )
    )

    await store.add(
        make_memory(
            memory_id="memory-3",
            user_id="user-2",
        )
    )

    assert (
        await store.count("user-1")
        == 2
    )

    assert (
        await store.count("user-2")
        == 1
    )