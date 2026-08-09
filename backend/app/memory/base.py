from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorkingMemoryStore(ABC):
    """
    Interface for task-scoped short-term working memory.

    Implementations may use Redis, an in-memory store, or another
    backend without changing agent code.
    """

    @abstractmethod
    async def set_plan(
        self,
        task_id: str,
        plan: dict[str, Any],
    ) -> None:
        """
        Store the current execution plan.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_plan(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve the current execution plan.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_subtask_output(
        self,
        task_id: str,
        output: dict[str, Any],
    ) -> None:
        """
        Store the output of a completed subtask.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_subtask_outputs(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve completed subtask outputs.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_intermediate_result(
        self,
        task_id: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Store an intermediate result.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_intermediate_results(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve all intermediate results.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_error(
        self,
        task_id: str,
        message: str,
        *,
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record an execution error.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_errors(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve execution errors.
        """
        raise NotImplementedError

    @abstractmethod
    async def snapshot(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve the complete working-memory snapshot.
        """
        raise NotImplementedError

    @abstractmethod
    async def clear(
        self,
        task_id: str,
    ) -> None:
        """
        Clear all working memory for a task.
        """
        raise NotImplementedError