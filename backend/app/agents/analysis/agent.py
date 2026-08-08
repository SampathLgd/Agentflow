from app.agents.base import BaseAgent
from app.agents.tool_runner import SpecialistToolRunner
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import Specialist


class DataAnalysisAgent(BaseAgent):
    name = Specialist.DATA_ANALYSIS

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
        Execute a data-analysis task using the centralized
        database_query tool.

        Phase 1 deliberately expects the read-only SQL query
        to already be present in the agent context. SQL
        generation from natural language will be addressed
        separately rather than coupling it to the tool layer.
        """

        query = agent_input.context.get(
            "sql_query"
        )

        if not isinstance(
            query,
            str,
        ) or not query.strip():
            return AgentOutput(
                agent=self.name,
                specialist=Specialist.DATA_ANALYSIS,
                subtask_id=agent_input.subtask_id,
                content=(
                    "Data analysis requires a read-only SQL "
                    "query in context['sql_query']."
                ),
                success=False,
                confidence=0.0,
                metadata={
                    "tool_name": "database_query",
                    "error": "missing_sql_query",
                },
            )

        parameters = agent_input.context.get(
            "sql_parameters",
            {},
        )

        if not isinstance(
            parameters,
            dict,
        ):
            parameters = {}

        result = await self._tool_runner.run(
            task_id=agent_input.task_id,
            subtask_id=agent_input.subtask_id,
            specialist=Specialist.DATA_ANALYSIS,
            tool_name="database_query",
            arguments={
                "query": query,
                "parameters": parameters,
            },
        )

        rows = result.get(
            "rows",
            [],
        )

        columns = result.get(
            "columns",
            [],
        )

        row_count = result.get(
            "row_count",
            len(rows),
        )

        return AgentOutput(
            agent=self.name,
            specialist=Specialist.DATA_ANALYSIS,
            subtask_id=agent_input.subtask_id,
            content=(
                f"Database query returned "
                f"{row_count} row(s).\n\n"
                f"Columns: {columns}\n\n"
                f"Rows: {rows}"
            ),
            success=True,
            confidence=0.85,
            metadata={
                "tool_name": "database_query",
                "query": query,
                "row_count": row_count,
                "columns": columns,
            },
        )