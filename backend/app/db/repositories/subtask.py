from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.subtask import (
    SubTaskModel,
    subtask_dependencies,
)
from app.schemas.execution import (
    Complexity,
    ExecutionPlan,
    Specialist,
    SubTask,
)


class SubTaskRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def create(
        self,
        *,
        execution_id: UUID,
        subtask: SubTask,
    ) -> SubTaskModel:
        model = SubTaskModel(
            id=subtask.id,
            execution_id=execution_id,
            description=subtask.description,
            assigned_specialist=(
                subtask.assigned_specialist.value
            ),
            required_inputs=subtask.required_inputs,
            expected_output=subtask.expected_output,
            estimated_complexity=(
                subtask.estimated_complexity.value
            ),
        )

        self.session.add(model)
        await self.session.flush()

        return model

    async def create_many(
        self,
        *,
        execution_id: UUID,
        subtasks: list[SubTask],
    ) -> list[SubTaskModel]:
        models = []

        for subtask in subtasks:
            model = await self.create(
                execution_id=execution_id,
                subtask=subtask,
            )
            models.append(model)

        await self._save_dependencies(
            subtasks=subtasks,
        )

        return models

    async def get(
        self,
        subtask_id: UUID,
    ) -> SubTaskModel | None:
        result = await self.session.execute(
            select(SubTaskModel)
            .options(
                selectinload(
                    SubTaskModel.dependencies
                )
            )
            .where(
                SubTaskModel.id == subtask_id
            )
        )

        return result.scalar_one_or_none()

    async def list_by_execution(
        self,
        execution_id: UUID,
    ) -> list[SubTaskModel]:
        """
        Load all persisted subtasks belonging to an execution.
        Dependencies are eagerly loaded so the complete plan can
        be reconstructed after Redis working memory is lost.
        """

        result = await self.session.execute(
            select(SubTaskModel)
            .options(
                selectinload(
                    SubTaskModel.dependencies
                )
            )
            .where(
                SubTaskModel.execution_id
                == execution_id
            )
        )

        return list(
            result.scalars().all()
        )

    async def get_execution_plan(
        self,
        *,
        execution_id: UUID,
        task_id: UUID,
    ) -> ExecutionPlan | None:
        """
        Reconstruct the execution plan from PostgreSQL.
        """

        models = await self.list_by_execution(
            execution_id
        )

        if not models:
            return None

        subtasks: list[SubTask] = []

        for model in models:
            dependency_ids = [
                dependency.id
                for dependency in (
                    model.dependencies or []
                )
            ]

            subtasks.append(
                SubTask(
                    id=model.id,
                    description=model.description,
                    assigned_specialist=Specialist(
                        model.assigned_specialist
                    ),
                    required_inputs=list(
                        model.required_inputs or []
                    ),
                    expected_output=model.expected_output,
                    estimated_complexity=Complexity(
                        model.estimated_complexity
                    ),
                    dependencies=dependency_ids,
                )
            )

        return ExecutionPlan(
            task_id=task_id,
            subtasks=subtasks,
        )

    async def _save_dependencies(
        self,
        *,
        subtasks: list[SubTask],
    ) -> None:
        dependency_rows = []

        valid_subtask_ids = {
            subtask.id
            for subtask in subtasks
        }

        for subtask in subtasks:
            for dependency_id in subtask.dependencies:
                if dependency_id not in valid_subtask_ids:
                    raise ValueError(
                        f"Subtask {subtask.id} references "
                        f"unknown dependency {dependency_id}."
                    )

                dependency_rows.append(
                    {
                        "subtask_id": subtask.id,
                        "dependency_id": dependency_id,
                    }
                )

        if dependency_rows:
            await self.session.execute(
                insert(subtask_dependencies),
                dependency_rows,
            )

        await self.session.flush()