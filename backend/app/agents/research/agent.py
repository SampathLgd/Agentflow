from app.agents.base import BaseAgent
from app.agents.tool_runner import SpecialistToolRunner
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import Specialist


class ResearchAgent(BaseAgent):
    name = Specialist.RESEARCH

    def __init__(
        self,
        tool_runner: SpecialistToolRunner,
    ) -> None:
        self._tool_runner = tool_runner

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:
        """
        Execute a research task using the centralized
        web_search tool.
        """

        query = agent_input.description.strip()

        if not query:
            return AgentOutput(
                agent=self.name,
                specialist=Specialist.RESEARCH,
                subtask_id=agent_input.subtask_id,
                content="Research query cannot be empty.",
                success=False,
                confidence=0.0,
                metadata={
                    "tool_name": "web_search",
                    "error": "empty_query",
                },
            )

        result = await self._tool_runner.run(
            task_id=agent_input.task_id,
            subtask_id=agent_input.subtask_id,
            specialist=Specialist.RESEARCH,
            tool_name="web_search",
            arguments={
                "query": query,
                "max_results": 5,
            },
        )

        results = result.get(
            "results",
            [],
        )

        if not results:
            return AgentOutput(
                agent=self.name,
                specialist=Specialist.RESEARCH,
                subtask_id=agent_input.subtask_id,
                content=(
                    "No web search results were found "
                    f"for: {query}"
                ),
                success=True,
                confidence=0.3,
                metadata={
                    "tool_name": "web_search",
                    "query": query,
                    "result_count": 0,
                },
            )

        content_parts: list[str] = []

        for item in results:
            title = item.get(
                "title",
                "",
            )

            snippet = item.get(
                "snippet",
                "",
            )

            url = item.get(
                "url",
                "",
            )

            content_parts.append(
                f"{title}\n"
                f"{snippet}\n"
                f"Source: {url}"
            )

        content = "\n\n".join(
            content_parts
        )

        return AgentOutput(
            agent=self.name,
            specialist=Specialist.RESEARCH,
            subtask_id=agent_input.subtask_id,
            content=content,
            success=True,
            confidence=0.8,
            metadata={
                "tool_name": "web_search",
                "query": query,
                "result_count": len(results),
            },
        )