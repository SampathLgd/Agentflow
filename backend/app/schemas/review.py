from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    """
    Structured result produced by the Reviewer Agent.

    The reviewer decides whether specialist outputs are
    acceptable for synthesis.
    """

    approved: bool = Field(
        description="Whether the specialist output is acceptable."
    )

    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall quality score from 0.0 to 1.0.",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Reviewer confidence in its evaluation.",
    )

    feedback: str = Field(
        default="",
        description=(
            "Actionable feedback for the specialist when "
            "the output is rejected."
        ),
    )

    issues: list[str] = Field(
        default_factory=list,
        description="Specific issues found in the output.",
    )