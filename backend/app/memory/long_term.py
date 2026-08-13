from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class LongTermMemory(BaseModel):
    """
    A durable semantic memory associated with a user and task.

    The actual semantic index is ChromaDB. This model represents
    the application-level memory record.
    """

    id: str

    user_id: str

    task_id: str | None = None

    memory_type: str

    content: str

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    importance_score: float = 0.5

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    access_count: int = 0


class MemorySearchResult(BaseModel):
    """
    A semantic-memory retrieval result.
    """

    memory: LongTermMemory

    distance: float | None = None


class LongTermMemoryStore(ABC):
    """
    Interface for persistent semantic memory.

    Implementations may use ChromaDB or another vector store,
    but the rest of AgentFlow should depend on this abstraction.
    """

    @abstractmethod
    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        """
        Store or update a long-term memory.
        """
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[MemorySearchResult]:
        """
        Search memories semantically.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
    ) -> None:
        """
        Delete one memory.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        """
        Delete all memories belonging to a user.
        """
        raise NotImplementedError

    @abstractmethod
    async def count(
        self,
        user_id: str,
    ) -> int:
        """
        Return the number of memories belonging to a user.
        """
        raise NotImplementedError


    async def list_user_memories(
        self,
        *,
        user_id: str,
        limit: int = 1000,
    ) -> list[LongTermMemory]:
        """
        Optional user-scoped memory listing capability.

        Concrete stores that support dashboard/lifecycle
        enumeration should override this method.
        """

        raise NotImplementedError(
            "This memory store does not support "
            "listing user memories."
        )