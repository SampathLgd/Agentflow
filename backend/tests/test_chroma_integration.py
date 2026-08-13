from __future__ import annotations

from uuid import uuid4

import pytest
import chromadb

from app.memory.chroma_store import (
    ChromaLongTermMemoryStore,
)
from app.memory.long_term import (
    LongTermMemory,
)


import os

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))


@pytest.fixture
def collection():
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
    )

    collection_name = (
        f"agentflow_test_{uuid4().hex}"
    )

    collection = client.get_or_create_collection(
        name=collection_name,
    )

    yield collection

    client.delete_collection(
        name=collection_name,
    )


def make_memory(
    *,
    user_id: str,
    content: str,
    memory_type: str = "successful_approach",
) -> LongTermMemory:
    return LongTermMemory(
        id=str(uuid4()),
        user_id=user_id,
        task_id=str(uuid4()),
        memory_type=memory_type,
        content=content,
        metadata={
            "tools": [
                "web_search",
                "analysis",
            ],
        },
        importance_score=0.9,
    )


@pytest.mark.asyncio
async def test_real_chroma_can_store_and_search_memory(
    collection,
):
    store = ChromaLongTermMemoryStore(
        collection
    )

    memory = make_memory(
        user_id="user-1",
        content=(
            "For research tasks, use web search "
            "before performing analysis."
        ),
    )

    await store.add(memory)

    results = await store.search(
        user_id="user-1",
        query="research web search analysis",
        limit=5,
    )

    assert len(results) >= 1

    assert any(
        result.memory.id == memory.id
        for result in results
    )


@pytest.mark.asyncio
async def test_real_chroma_isolates_users(
    collection,
):
    store = ChromaLongTermMemoryStore(
        collection
    )

    user_one_memory = make_memory(
        user_id="user-1",
        content=(
            "User one prefers concise research reports."
        ),
    )

    user_two_memory = make_memory(
        user_id="user-2",
        content=(
            "User two prefers detailed research reports."
        ),
    )

    await store.add(
        user_one_memory
    )

    await store.add(
        user_two_memory
    )

    results = await store.search(
        user_id="user-1",
        query="research reports",
        limit=10,
    )

    assert results

    assert all(
        result.memory.user_id == "user-1"
        for result in results
    )


@pytest.mark.asyncio
async def test_real_chroma_filters_memory_type(
    collection,
):
    store = ChromaLongTermMemoryStore(
        collection
    )

    approach = make_memory(
        user_id="user-1",
        content=(
            "Successful approach: search first."
        ),
        memory_type="successful_approach",
    )

    fact = make_memory(
        user_id="user-1",
        content=(
            "Domain fact: Redis provides fast "
            "task-scoped state."
        ),
        memory_type="domain_fact",
    )

    await store.add(approach)
    await store.add(fact)

    results = await store.search(
        user_id="user-1",
        query="Redis task state",
        memory_type="domain_fact",
        limit=10,
    )

    assert results

    assert all(
        result.memory.memory_type
        == "domain_fact"
        for result in results
    )


@pytest.mark.asyncio
async def test_real_chroma_can_delete_memory(
    collection,
):
    store = ChromaLongTermMemoryStore(
        collection
    )

    memory = make_memory(
        user_id="user-1",
        content="Temporary semantic memory.",
    )

    await store.add(memory)

    assert (
        await store.count("user-1")
        == 1
    )

    await store.delete(
        memory.id
    )

    assert (
        await store.count("user-1")
        == 0
    )


@pytest.mark.asyncio
async def test_real_chroma_can_delete_all_user_memory(
    collection,
):
    store = ChromaLongTermMemoryStore(
        collection
    )

    first = make_memory(
        user_id="user-1",
        content="First user memory.",
    )

    second = make_memory(
        user_id="user-1",
        content="Second user memory.",
    )

    other_user = make_memory(
        user_id="user-2",
        content="Other user memory.",
    )

    await store.add(first)
    await store.add(second)
    await store.add(other_user)

    assert (
        await store.count("user-1")
        == 2
    )

    await store.delete_user(
        "user-1"
    )

    assert (
        await store.count("user-1")
        == 0
    )

    assert (
        await store.count("user-2")
        == 1
    )