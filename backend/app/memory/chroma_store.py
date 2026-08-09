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

    The adapter supports both:

    - synchronous Chroma collections
    - asynchronous test/fake collections

    The application-facing interface remains async.
    """

    def __init__(
        self,
        collection: Any,
    ) -> None:
        self.collection = collection

    # ---------------------------------------------------------
    # Collection adapter
    # ---------------------------------------------------------

    async def _call_collection(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Call a Chroma collection method.

        Real Chroma HttpClient collections expose synchronous
        collection methods.

        Our unit-test fake exposes asynchronous methods.

        Support both without leaking that implementation
        detail into the rest of the store.
        """

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

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------

    @staticmethod
    def _metadata(
        memory: LongTermMemory,
    ) -> dict[str, Any]:
        """
        Convert application metadata into Chroma-compatible
        scalar metadata.
        """

        return {
            "user_id": memory.user_id,
            "task_id": memory.task_id or "",
            "memory_type": memory.memory_type,
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
                memory.metadata,
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
        Reconstruct the application memory model from
        Chroma metadata.
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
            str(metadata["created_at"])
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

        return LongTermMemory(
            id=memory_id,
            user_id=str(
                metadata["user_id"]
            ),
            task_id=(
                str(metadata["task_id"])
                if metadata.get("task_id")
                else None
            ),
            memory_type=str(
                metadata["memory_type"]
            ),
            content=document,
            metadata=extra_metadata,
            importance_score=float(
                metadata.get(
                    "importance_score",
                    0.5,
                )
            ),
            created_at=created_at,
            last_accessed_at=last_accessed_at,
            access_count=int(
                metadata.get(
                    "access_count",
                    0,
                )
            ),
        )

    # ---------------------------------------------------------
    # Add
    # ---------------------------------------------------------

    async def add(
        self,
        memory: LongTermMemory,
    ) -> None:
        """
        Insert or update a semantic memory.

        Chroma's upsert provides idempotent writes.
        """

        await self._call_collection(
            "upsert",
            ids=[memory.id],
            documents=[memory.content],
            metadatas=[
                self._metadata(memory)
            ],
        )

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

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
            query_texts=[query],
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
                    metadata=metadatas[index],
                )
            )

            distance = None

            if index < len(distances):
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

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        await self._call_collection(
            "delete",
            ids=[memory_id],
        )

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        """
        Delete every semantic memory belonging to a user.
        """

        await self._call_collection(
            "delete",
            where={
                "user_id": user_id,
            },
        )

    # ---------------------------------------------------------
    # Count
    # ---------------------------------------------------------

    async def count(
        self,
        user_id: str,
    ) -> int:
        """
        Return the number of memories belonging to a user.

        Chroma does not expose a filtered count consistently
        across client versions, so retrieve IDs using the
        user filter and count them.
        """

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