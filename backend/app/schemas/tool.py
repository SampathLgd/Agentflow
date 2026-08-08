from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """
    Metadata describing a tool available to specialist agents.
    """

    name: str = Field(min_length=1)

    description: str = Field(min_length=1)

    input_schema: dict[str, object] = Field(
        default_factory=dict,
    )

    output_schema: dict[str, object] = Field(
        default_factory=dict,
    )

    allowed_specialists: list[str] = Field(
        default_factory=list,
    )

    rate_limit_per_minute: int | None = Field(
        default=None,
        ge=1,
    )