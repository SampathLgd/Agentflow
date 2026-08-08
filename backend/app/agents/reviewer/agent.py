from app.agents.base import BaseAgent
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.review import ReviewResult


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:
        """
        Review specialist outputs.

        The actual LLM-backed structured evaluation will be
        connected after the graph contract is verified.
        """

        specialist_outputs = agent_input.context.get(
            "specialist_outputs",
            [],
        )

        if not specialist_outputs:
            review = ReviewResult(
                approved=False,
                quality_score=0.0,
                confidence=1.0,
                feedback="No specialist output was provided.",
                issues=[
                    "Missing specialist output",
                ],
            )
        else:
            review = ReviewResult(
                approved=True,
                quality_score=1.0,
                confidence=1.0,
                feedback="",
                issues=[],
            )

        return AgentOutput(
            agent=self.name,
            subtask_id=agent_input.subtask_id,
            content=review.model_dump_json(),
            success=True,
            confidence=review.confidence,
            metadata={
                "review": review.model_dump(
                    mode="json"
                ),
            },
        )