from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.memory.long_term import (
    LongTermMemory,
    LongTermMemoryStore,
    MemorySearchResult,
)


class MemoryService:
    """
    Application-level memory orchestration.

    Responsibilities:

    - retrieve relevant long-term memories
    - persist durable memories
    - track memory access
    - increase importance for frequently accessed memories
    - consolidate related memories
    - filter low-value memories
    - apply retention rules
    - delete user memories
    - keep workflow code independent from ChromaDB
    """

    DEFAULT_RETRIEVAL_LIMIT = 5
    DEFAULT_MIN_IMPORTANCE = 0.50
    DEFAULT_RETENTION_DAYS = 90

    # ---------------------------------------------------------
    # Importance scoring
    # ---------------------------------------------------------

    ACCESS_IMPORTANCE_INCREMENT = 0.05

    MAX_ACCESS_IMPORTANCE_BONUS = 0.30

    RECENCY_IMPORTANCE_BONUS = 0.10

    # ---------------------------------------------------------
    # Consolidation
    # ---------------------------------------------------------

    DEFAULT_CONSOLIDATION_LIMIT = 5

    def __init__(
        self,
        long_term_store: LongTermMemoryStore,
        *,
        retrieval_limit: int = DEFAULT_RETRIEVAL_LIMIT,
        min_importance_score: float = DEFAULT_MIN_IMPORTANCE,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        if retrieval_limit < 1:
            raise ValueError(
                "retrieval_limit must be at least 1."
            )

        if not 0.0 <= min_importance_score <= 1.0:
            raise ValueError(
                "min_importance_score must be between 0 and 1."
            )

        if retention_days < 1:
            raise ValueError(
                "retention_days must be at least 1."
            )

        self.long_term_store = long_term_store
        self.retrieval_limit = retrieval_limit
        self.min_importance_score = (
            min_importance_score
        )
        self.retention_days = retention_days

    # =========================================================
    # Importance scoring
    # =========================================================

    @classmethod
    def calculate_importance(
        cls,
        memory: LongTermMemory,
        *,
        now: datetime | None = None,
    ) -> float:
        """
        Calculate the effective importance of a memory.

        The score combines:

        1. Original/base importance.
        2. Access frequency.
        3. Recent access.

        Result is constrained to [0.0, 1.0].
        """

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        base_importance = float(
            memory.metadata.get(
                "_base_importance",
                memory.importance_score,
            )
        )

        base_importance = min(
            1.0,
            max(
                0.0,
                base_importance,
            ),
        )

        access_bonus = min(
            cls.MAX_ACCESS_IMPORTANCE_BONUS,
            memory.access_count
            * cls.ACCESS_IMPORTANCE_INCREMENT,
        )

        last_accessed = memory.last_accessed_at

        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(
                tzinfo=timezone.utc
            )

        age_seconds = max(
            0.0,
            (
                current_time
                - last_accessed
            ).total_seconds(),
        )

        recency_factor = math.exp(
            -age_seconds
            / (24.0 * 60.0 * 60.0)
        )

        recency_bonus = (
            cls.RECENCY_IMPORTANCE_BONUS
            * recency_factor
        )

        score = (
            base_importance
            + access_bonus
            + recency_bonus
        )

        return round(
            min(
                1.0,
                max(
                    0.0,
                    score,
                ),
            ),
            6,
        )

    # =========================================================
    # Retrieval
    # =========================================================

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        limit: int | None = None,
        memory_type: str | None = None,
    ) -> list[MemorySearchResult]:
        """
        Retrieve semantically relevant memories.

        Retrieval counts as memory access.
        """

        if not user_id.strip():
            return []

        if not query.strip():
            return []

        effective_limit = (
            limit
            if limit is not None
            else self.retrieval_limit
        )

        if effective_limit < 1:
            raise ValueError(
                "Memory retrieval limit must be at least 1."
            )

        results = await self.long_term_store.search(
            user_id=user_id,
            query=query,
            limit=effective_limit,
            memory_type=memory_type,
        )

        eligible = [
            result
            for result in results
            if result.memory.importance_score
            >= self.min_importance_score
        ]

        return await self.record_search_access(
            eligible
        )

    async def retrieve_for_workflow(
        self,
        *,
        user_id: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve memories in the structure expected by
        AgentGraphState.
        """

        results = await self.retrieve(
            user_id=user_id,
            query=query,
        )

        return [
            {
                "memory": result.memory.model_dump(
                    mode="json"
                ),
                "distance": result.distance,
            }
            for result in results
        ]

    # =========================================================
    # Persistence
    # =========================================================

    async def remember(
        self,
        *,
        user_id: str,
        content: str,
        memory_type: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        importance_score: float = 0.5,
    ) -> LongTermMemory | None:
        """
        Create and persist a long-term memory.
        """

        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty."
            )

        if not content.strip():
            raise ValueError(
                "Memory content cannot be empty."
            )

        if not memory_type.strip():
            raise ValueError(
                "memory_type cannot be empty."
            )

        if not 0.0 <= importance_score <= 1.0:
            raise ValueError(
                "importance_score must be between 0 and 1."
            )

        if importance_score < self.min_importance_score:
            return None

        memory_metadata = dict(
            metadata or {}
        )

        memory_metadata[
            "_base_importance"
        ] = importance_score

        memory = LongTermMemory(
            id=str(uuid4()),
            user_id=user_id,
            task_id=task_id,
            memory_type=memory_type,
            content=content.strip(),
            metadata=memory_metadata,
            importance_score=importance_score,
        )

        await self.long_term_store.add(
            memory
        )

        return memory

    # =========================================================
    # Access tracking
    # =========================================================

    async def record_access(
        self,
        memory: LongTermMemory,
        *,
        accessed_at: datetime | None = None,
    ) -> LongTermMemory:
        """
        Record one access to a memory.
        """

        access_time = (
            accessed_at
            or datetime.now(timezone.utc)
        )

        if access_time.tzinfo is None:
            access_time = access_time.replace(
                tzinfo=timezone.utc
            )

        memory.access_count += 1

        memory.last_accessed_at = (
            access_time
        )

        memory.importance_score = (
            self.calculate_importance(
                memory,
                now=access_time,
            )
        )

        await self.long_term_store.add(
            memory
        )

        return memory

    async def record_search_access(
        self,
        results: list[MemorySearchResult],
    ) -> list[MemorySearchResult]:
        """
        Record access for all retrieved memories.
        """

        for result in results:
            await self.record_access(
                result.memory
            )

        return results

    # =========================================================
    # Memory consolidation
    # =========================================================

    @staticmethod
    def _build_consolidated_content(
        memories: list[LongTermMemory],
    ) -> str:
        """
        Build deterministic consolidated content.

        Each source memory is retained as a distinct statement.
        This avoids losing information before an optional future
        LLM summarization layer is introduced.
        """

        ordered = sorted(
            memories,
            key=lambda memory: (
                -memory.importance_score,
                -memory.access_count,
                memory.created_at,
            ),
        )

        statements: list[str] = []

        seen: set[str] = set()

        for memory in ordered:
            content = memory.content.strip()

            if not content:
                continue

            normalized = content.casefold()

            if normalized in seen:
                continue

            seen.add(normalized)

            statements.append(content)

        return "\n".join(
            f"- {statement}"
            for statement in statements
        )

    @staticmethod
    def _consolidated_memory_type(
        memories: list[LongTermMemory],
        requested_type: str | None,
    ) -> str:
        """
        Preserve a common memory type.

        If all memories have the same type, preserve it.

        If different memory types are being consolidated,
        use 'consolidated'.
        """

        if requested_type:
            return requested_type

        memory_types = {
            memory.memory_type
            for memory in memories
        }

        if len(memory_types) == 1:
            return next(
                iter(memory_types)
            )

        return "consolidated"

    async def consolidate(
        self,
        *,
        user_id: str,
        query: str,
        memory_type: str | None = None,
        limit: int = DEFAULT_CONSOLIDATION_LIMIT,
        min_candidates: int = 2,
    ) -> LongTermMemory | None:
        """
        Consolidate semantically related memories.

        The operation:

        1. Searches the user's memories.
        2. Removes memories below the importance threshold.
        3. Requires at least `min_candidates`.
        4. Creates one consolidated memory.
        5. Preserves aggregate lifecycle metadata.
        6. Deletes the superseded source memories.

        The source memories are only deleted after the
        consolidated memory has successfully been persisted.

        Calling consolidation again after the sources have been
        removed is therefore naturally idempotent when fewer than
        `min_candidates` memories remain.
        """

        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty."
            )

        if not query.strip():
            raise ValueError(
                "query cannot be empty."
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        if min_candidates < 2:
            raise ValueError(
                "min_candidates must be at least 2."
            )

        results = await self.long_term_store.search(
            user_id=user_id,
            query=query,
            limit=limit,
            memory_type=memory_type,
        )

        candidates: list[
            LongTermMemory
        ] = []

        seen_ids: set[str] = set()

        for result in results:
            memory = result.memory

            if memory.id in seen_ids:
                continue

            if memory.importance_score < (
                self.min_importance_score
            ):
                continue

            seen_ids.add(memory.id)

            candidates.append(
                memory
            )

        if len(candidates) < min_candidates:
            return None

        # -----------------------------------------------------
        # Build consolidated content.
        # -----------------------------------------------------

        content = (
            self._build_consolidated_content(
                candidates
            )
        )

        if not content.strip():
            return None

        # -----------------------------------------------------
        # Aggregate lifecycle metadata.
        # -----------------------------------------------------

        highest_importance = max(
            memory.importance_score
            for memory in candidates
        )

        total_access_count = sum(
            memory.access_count
            for memory in candidates
        )

        earliest_created_at = min(
            memory.created_at
            for memory in candidates
        )

        latest_accessed_at = max(
            memory.last_accessed_at
            for memory in candidates
        )

        source_ids = [
            memory.id
            for memory in candidates
        ]

        source_task_ids = sorted(
            {
                memory.task_id
                for memory in candidates
                if memory.task_id
            }
        )

        # -----------------------------------------------------
        # Preserve useful metadata.
        # -----------------------------------------------------

        merged_metadata: dict[
            str,
            Any,
        ] = {}

        for memory in candidates:
            for key, value in (
                memory.metadata.items()
            ):
                # Internal lifecycle fields from individual
                # memories are not blindly copied.
                if key.startswith(
                    "_"
                ):
                    continue

                if key not in merged_metadata:
                    merged_metadata[key] = value

        merged_metadata.update(
            {
                "consolidated": True,
                "source_memory_ids": source_ids,
                "source_task_ids": source_task_ids,
                "source_memory_count": len(
                    candidates
                ),
                "_base_importance": (
                    highest_importance
                ),
            }
        )

        consolidated = LongTermMemory(
            id=str(uuid4()),
            user_id=user_id,
            task_id=(
                source_task_ids[0]
                if len(source_task_ids) == 1
                else None
            ),
            memory_type=(
                self._consolidated_memory_type(
                    candidates,
                    memory_type,
                )
            ),
            content=content,
            metadata=merged_metadata,
            importance_score=highest_importance,
            created_at=earliest_created_at,
            last_accessed_at=latest_accessed_at,
            access_count=total_access_count,
        )

        # -----------------------------------------------------
        # Persist first.
        #
        # Never delete source memories before the new memory
        # has been successfully written.
        # -----------------------------------------------------

        await self.long_term_store.add(
            consolidated
        )

        # -----------------------------------------------------
        # Delete superseded source memories.
        # -----------------------------------------------------

        for memory in candidates:
            await self.long_term_store.delete(
                memory.id
            )

        return consolidated

    # =========================================================
    # Retention
    # =========================================================

    async def apply_retention(
        self,
        *,
        user_id: str,
        now: datetime | None = None,
    ) -> int:
        """
        Remove stale, low-value memories.
        """

        if not user_id.strip():
            return 0

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        cutoff = (
            current_time
            - timedelta(
                days=self.retention_days
            )
        )

        candidates = await self.long_term_store.search(
            user_id=user_id,
            query="memory",
            limit=100,
        )

        deleted = 0

        for result in candidates:
            memory = result.memory

            if (
                memory.created_at < cutoff
                and memory.importance_score
                < self.min_importance_score
            ):
                await self.long_term_store.delete(
                    memory.id
                )
                deleted += 1

        return deleted

    # =========================================================
    # Explicit deletion
    # =========================================================

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        """
        Delete one long-term memory.
        """

        if not memory_id.strip():
            raise ValueError(
                "memory_id cannot be empty."
            )

        await self.long_term_store.delete(
            memory_id
        )

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        """
        Delete all long-term memory belonging to a user.
        """

        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty."
            )

        await self.long_term_store.delete_user(
            user_id
        )

    async def count(
        self,
        user_id: str,
    ) -> int:
        """
        Count long-term memories for a user.
        """

        if not user_id.strip():
            return 0

        return await self.long_term_store.count(
            user_id
        )


    # =========================================================
    # Decay / expiration
    # =========================================================

    DECAY_HALF_LIFE_DAYS = 30.0

    MIN_DECAYED_IMPORTANCE = 0.0

    def calculate_decay(
        self,
        memory: LongTermMemory,
        *,
        now: datetime | None = None,
    ) -> float:
        """
        Calculate the decayed importance of a memory.

        Decay is based on time since the memory was last accessed.

        A memory's importance is multiplied by an exponential
        decay factor using DECAY_HALF_LIFE_DAYS.

        The result is always constrained to [0.0, 1.0].
        """

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        last_accessed = (
            memory.last_accessed_at
        )

        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(
                tzinfo=timezone.utc
            )

        age_seconds = max(
            0.0,
            (
                current_time
                - last_accessed
            ).total_seconds(),
        )

        age_days = (
            age_seconds
            / (24.0 * 60.0 * 60.0)
        )

        decay_factor = (
            0.5
            ** (
                age_days
                / self.DECAY_HALF_LIFE_DAYS
            )
        )

        decayed_importance = (
            memory.importance_score
            * decay_factor
        )

        return round(
            min(
                1.0,
                max(
                    self.MIN_DECAYED_IMPORTANCE,
                    decayed_importance,
                ),
            ),
            6,
        )

    async def apply_decay(
        self,
        *,
        user_id: str,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        """
        Apply time-based importance decay to a user's memories.

        Returns the number of memories whose importance changed.
        """

        if not user_id.strip():
            return 0

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        results = await self.long_term_store.search(
            user_id=user_id,
            query="memory",
            limit=limit,
        )

        updated = 0

        for result in results:
            memory = result.memory

            decayed_importance = (
                self.calculate_decay(
                    memory,
                    now=current_time,
                )
            )

            if (
                decayed_importance
                >= memory.importance_score
            ):
                continue

            memory.importance_score = (
                decayed_importance
            )

            await self.long_term_store.add(
                memory
            )

            updated += 1

        return updated

    async def expire_memories(
        self,
        *,
        user_id: str,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        """
        Expire memories that are stale and genuinely low-value.

        Important distinction:

        - `importance_score` represents the durable value of the
          memory.
        - `calculate_decay()` represents temporary time-based
          relevance.

        A memory that was originally important must not be deleted
        merely because it has not been accessed recently.

        Expiration therefore uses the memory's durable/base
        importance rather than its decayed relevance.
        """

        if not user_id.strip():
            return 0

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        cutoff = (
            current_time
            - timedelta(
                days=self.retention_days
            )
        )

        results = await self.long_term_store.search(
            user_id=user_id,
            query="memory",
            limit=limit,
        )

        expired = 0

        for result in results:
            memory = result.memory

            created_at = memory.created_at

            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=timezone.utc
                )

            # Memory is not old enough to expire.
            if created_at >= cutoff:
                continue

            # Use durable/base importance for expiration.
            #
            # `_base_importance` is written by remember() and
            # consolidation. For memories created by older code
            # that do not have it, fall back to current importance.
            base_importance = float(
                memory.metadata.get(
                    "_base_importance",
                    memory.importance_score,
                )
            )

            base_importance = min(
                1.0,
                max(
                    0.0,
                    base_importance,
                ),
            )

            # Important memories are retained even when their
            # current relevance has decayed.
            if (
                base_importance
                >= self.min_importance_score
            ):
                continue

            await self.long_term_store.delete(
                memory.id
            )

            expired += 1

        return expired

    async def apply_decay_and_expiration(
        self,
        *,
        user_id: str,
        now: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        """
        Run the complete decay/expiration lifecycle.

        Returns:

            {
                "decayed": <number updated>,
                "expired": <number deleted>,
            }
        """

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        decayed = await self.apply_decay(
            user_id=user_id,
            now=current_time,
            limit=limit,
        )

        expired = await self.expire_memories(
            user_id=user_id,
            now=current_time,
            limit=limit,
        )

        return {
            "decayed": decayed,
            "expired": expired,
        }
        
    async def get_dashboard(
        self,
        *,
        user_id: str,
        now: datetime | None = None,
        stale_after_days: int | None = None,
        limit: int = 1000,
    ) -> dict[str, object]:
        """
        Return memory statistics for a single user.
        """

        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty."
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        current_time = (
            now
            or datetime.now(timezone.utc)
        )

        stale_days = (
            stale_after_days
            if stale_after_days is not None
            else self.retention_days
        )

        if stale_days < 1:
            raise ValueError(
                "stale_after_days must be at least 1."
            )

        memories = (
            await self.long_term_store
            .list_user_memories(
                user_id=user_id,
                limit=limit,
            )
        )

        total_memories = len(memories)

        if total_memories == 0:
            return {
                "user_id": user_id,
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

        importance_values = [
            float(
                memory.importance_score
            )
            for memory in memories
        ]

        access_values = [
            int(
                memory.access_count
            )
            for memory in memories
        ]

        high_importance_count = sum(
            importance >= 0.7
            for importance in importance_values
        )

        low_importance_count = sum(
            importance < 0.5
            for importance in importance_values
        )

        total_access_count = sum(
            access_values
        )

        average_importance = (
            sum(importance_values)
            / total_memories
        )

        average_access_count = (
            total_access_count
            / total_memories
        )

        stale_cutoff = (
            current_time
            - timedelta(
                days=stale_days
            )
        )

        stale_memory_count = 0
        recent_memory_count = 0

        memory_types: dict[str, int] = {}

        for memory in memories:
            memory_types[
                memory.memory_type
            ] = (
                memory_types.get(
                    memory.memory_type,
                    0,
                )
                + 1
            )

            last_accessed = (
                memory.last_accessed_at
            )

            if last_accessed.tzinfo is None:
                last_accessed = (
                    last_accessed.replace(
                        tzinfo=timezone.utc
                    )
                )

            if last_accessed < stale_cutoff:
                stale_memory_count += 1
            else:
                recent_memory_count += 1

        return {
            "user_id": user_id,
            "total_memories": total_memories,
            "average_importance": round(
                average_importance,
                4,
            ),
            "high_importance_count": (
                high_importance_count
            ),
            "low_importance_count": (
                low_importance_count
            ),
            "total_access_count": (
                total_access_count
            ),
            "average_access_count": round(
                average_access_count,
                4,
            ),
            "stale_memory_count": (
                stale_memory_count
            ),
            "recent_memory_count": (
                recent_memory_count
            ),
            "memory_types": memory_types,
        }