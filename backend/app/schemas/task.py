from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """
    User-level task submitted to the orchestration system.
    """

    task_id: UUID = Field(default_factory=uuid4)

    user_id: str = Field(
        min_length=1,
        description="Identifier of the user requesting the task.",
    )

    description: str = Field(
        min_length=1,
        description="Natural-language description of the task.",
    )