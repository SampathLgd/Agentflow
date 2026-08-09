from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.graph.workflow import build_workflow
from app.memory.long_term import LongTermMemory
from app.memory.long_term import MemorySearchResult


@pytest.mark.asyncio
async def test_workflow_retrieves_long_term_memory():
    long_term_memory = AsyncMock()

    long_term_memory.search.return_value = [
        MemorySearchResult(
            memory=LongTermMemory(
                id="memory-1",
                user_id="user-1",
                task_id="old-task",
                memory_type="successful_approach",
                content=(
                    "Previously used web search "
                    "before research analysis."
                ),
                metadata={},
                importance_score=0.9,
            ),
            distance=0.1,
        )
    ]

    # The detailed workflow construction should use
    # the existing fixtures/helpers from the project.
    #
    # This test should verify that search() is called with:
    #
    # user_id="user-1"
    # query=current task description
    #
    # and that the returned memory is placed into
    # graph state as long_term_memories.