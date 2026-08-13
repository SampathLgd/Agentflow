from __future__ import annotations

import inspect
import json
from datetime import datetime
from typing import Any

from app.memory.long_term import (
    LongTermMemory,
    LongTermMemoryStore,
    MemorySearchResult,
)


class ChromaLongTermMemoryStore(
    LongTermMemoryStore
):
    """
    ChromaDB-backed long-term semantic memory.

    Supports both:

    - synchronous Chroma collections
    - asynchronous test/fake collections

    The application-facing interface remains async.
    """

    def __init__(
        self,
        collection: Any,
    ) -> None:
        self.collection = collection

    # =========================================================
    # Collection adapter
    # =========================================================

    async def _call_collection(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        method = getattr(
            self.collection,
            method_name,
        )

        result = method(
            *args,
            **kwargs,
        )

        if inspect.isawaitable(result):
            return await result

        return result

    # =========================================================
    # Serialization
    # =========================================================

    @staticmethod
    def _metadata(
        memory: LongTermMemory,
    ) -> dict[str, Any]:
        """
        Convert application memory into Chroma-compatible
        scalar metadata.
        """

        metadata_json = dict(
            memory.metadata
        )

        # Keep the original importance explicitly available
        # for lifecycle scoring.
        metadata_json.setdefault(
            "_base_importance",
            float(
                memory.importance_score
            ),
        )

        return {
            "user_id": memory.user_id,

            "task_id": (
                memory.task_id
                or ""
            ),

            "memory_type": (
                memory.memory_type
            ),

            "importance_score": float(
                memory.importance_score
            ),

            "created_at": (
                memory.created_at.isoformat()
            ),

            "last_accessed_at": (
                memory.last_accessed_at.isoformat()
            ),

            "access_count": int(
                memory.access_count
            ),

            "metadata_json": json.dumps(
                metadata_json,
                default=str,
            ),
        }

    @staticmethod
    def _memory_from_record(
        *,
        memory_id: str,
        document: str,
        metadata: dict[str, Any],
    ) -> LongTermMemory:
        """
        Reconstruct application memory from Chroma metadata.
        """

        raw_metadata = metadata.get(
            "metadata_json",
            "{}",
        )

        try:
            extra_metadata = json.loads(
                raw_metadata
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            extra_metadata = {}

        created_at = datetime.fromisoformat(
            str(
                metadata["created_at"]
            )
        )

        last_accessed_at = (
            datetime.fromisoformat(
                str(
                    metadata[
                        "last_accessed_at"
                    ]
                )
            )
        )

        importance_score = float(
            metadata.get(
                "importance_score",
                0.5,
            )
        )

        # Backward compatibility for memories created before
        # _base_importance was introduced.
        extra_metadata.setdefault(
            "_base_importance",
            importance_score,
        )

        return LongTermMemory(
            id=memory_id,

            user_id=str(
                metadata["user_id"]
            ),

            task_id=(
                str(
                    metadata["task_id"]
                )
                if metadata.get(
                    "task_id"
                )
                else None
            ),

            memory_type=str(
                metadata["memory_type"]
            ),

            content=document,

            metadata=extra_metadata,

            importance_score=importance_score,

            created_at=created_at,

            last_accessed_at=last_accessed_at,

            access_count=int(
                metadata.get(
                    "access_count",
                    0,
                )
            ),
        )

    # =========================================================
    # Add / Upsert
    # =========================================================

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        """
        Insert or update a semantic memory.
        """

        await self._call_collection(
            "upsert",
            ids=[
                memory.id
            ],
            documents=[
                memory.content
            ],
            metadatas=[
                self._metadata(
                    memory
                )
            ],
        )

    # =========================================================
    # Search
    # =========================================================

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[MemorySearchResult]:
        """
        Retrieve semantically similar memories for a user.
        """

        if not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        if limit < 1:
            raise ValueError(
                "Search limit must be at least 1."
            )

        if memory_type is None:
            where: dict[str, Any] = {
                "user_id": user_id,
            }
        else:
            where = {
                "$and": [
                    {
                        "user_id": user_id,
                    },
                    {
                        "memory_type": memory_type,
                    },
                ]
            }

        results = await self._call_collection(
            "query",
            query_texts=[
                query
            ],
            n_results=limit,
            where=where,
        )

        ids = results.get(
            "ids",
            [[]],
        )[0]

        documents = results.get(
            "documents",
            [[]],
        )[0]

        metadatas = results.get(
            "metadatas",
            [[]],
        )[0]

        distances = results.get(
            "distances",
            [[]],
        )[0]

        output: list[
            MemorySearchResult
        ] = []

        for index, memory_id in enumerate(
            ids
        ):
            memory = (
                self._memory_from_record(
                    memory_id=str(
                        memory_id
                    ),
                    document=str(
                        documents[index]
                    ),
                    metadata=metadatas[
                        index
                    ],
                )
            )

            distance = None

            if index < len(
                distances
            ):
                distance = float(
                    distances[index]
                )

            output.append(
                MemorySearchResult(
                    memory=memory,
                    distance=distance,
                )
            )

        return output

    # =========================================================
    # Delete
    # =========================================================

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        await self._call_collection(
            "delete",
            ids=[
                memory_id
            ],
        )

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        await self._call_collection(
            "delete",
            where={
                "user_id": user_id,
            },
        )
    async def list_user_memories(
        self,
        *,
        user_id: str,
        limit: int = 1000,
    ) -> list[LongTermMemory]:
        """
        Return all available memories for a user up to `limit`.

        Unlike semantic search, this operation does not depend
        on query similarity and is therefore suitable for
        dashboard/statistics calculations.
        """

        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty."
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        result = await self._call_collection(
            "get",
            where={
                "user_id": user_id,
            },
            limit=limit,
            include=[
                "documents",
                "metadatas",
            ],
        )

        ids = result.get(
            "ids",
            [],
        )

        documents = result.get(
            "documents",
            [],
        )

        metadatas = result.get(
            "metadatas",
            [],
        )

        memories: list[
            LongTermMemory
        ] = []

        for index, memory_id in enumerate(ids):
            memories.append(
                self._memory_from_record(
                    memory_id=str(
                        memory_id
                    ),
                    document=str(
                        documents[index]
                    ),
                    metadata=metadatas[index],
                )
            )

        return memories
    # =========================================================
    # Count
    # =========================================================

    async def count(
        self,
        user_id: str,
    ) -> int:
        result = await self._call_collection(
            "get",
            where={
                "user_id": user_id,
            },
            include=[],
        )

        ids = result.get(
            "ids",
            [],
        )

        return len(ids)