from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.execution import Specialist


class AgentInput(BaseModel):
    """
    Standard input contract shared by all agents.
    """

    task_id: UUID

    subtask_id: UUID | None = None

    description: str = Field(min_length=1)

    context: dict[str, object] = Field(
        default_factory=dict,
    )


class AgentOutput(BaseModel):
    """
    Standard output contract shared by all agents.
    """

    agent: str

    subtask_id: UUID | None = None

    content: str

    success: bool = True

    specialist: Specialist | None = None

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    metadata: dict[str, object] = Field(
        default_factory=dict,
    )