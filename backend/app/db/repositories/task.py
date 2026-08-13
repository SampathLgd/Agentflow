from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import TaskModel


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        task_id: UUID,
        user_id: str,
        description: str,
    ) -> TaskModel:
        task = TaskModel(
            id=task_id,
            user_id=user_id,
            description=description,
        )

        self.session.add(task)
        await self.session.flush()

        return task

    async def get(
        self,
        task_id: UUID,
    ) -> TaskModel | None:
        result = await self.session.execute(
            select(TaskModel).where(
                TaskModel.id == task_id
            )
        )

        return result.scalar_one_or_none()