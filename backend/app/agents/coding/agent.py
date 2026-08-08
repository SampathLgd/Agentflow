from app.agents.base import BaseAgent
from app.agents.tool_runner import SpecialistToolRunner
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import Specialist


class CodeExecutionAgent(BaseAgent):
    name = Specialist.CODE_EXECUTION

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
        Execute Python code through the centralized
        code_execution tool.

        The specialist never executes code directly.
        All execution goes through ToolExecutor.
        """

        code = agent_input.context.get(
            "code"
        )

        if not isinstance(
            code,
            str,
        ) or not code.strip():
            return AgentOutput(
                agent=self.name,
                specialist=Specialist.CODE_EXECUTION,
                subtask_id=agent_input.subtask_id,
                content=(
                    "Code execution requires Python code "
                    "in context['code']."
                ),
                success=False,
                confidence=0.0,
                metadata={
                    "tool_name": "code_execution",
                    "error": "missing_code",
                },
            )

        timeout = agent_input.context.get(
            "timeout",
            10,
        )

        if not isinstance(
            timeout,
            int,
        ):
            timeout = 10

        result = await self._tool_runner.run(
            task_id=agent_input.task_id,
            subtask_id=agent_input.subtask_id,
            specialist=Specialist.CODE_EXECUTION,
            tool_name="code_execution",
            arguments={
                "code": code,
                "timeout": timeout,
            },
        )

        stdout = result.get(
            "stdout",
            "",
        )

        stderr = result.get(
            "stderr",
            "",
        )

        return_code = result.get(
            "return_code",
            0,
        )

        success = (
            return_code == 0
        )

        content = (
            f"Return code: {return_code}\n\n"
            f"STDOUT:\n{stdout}\n\n"
            f"STDERR:\n{stderr}"
        )

        return AgentOutput(
            agent=self.name,
            specialist=Specialist.CODE_EXECUTION,
            subtask_id=agent_input.subtask_id,
            content=content,
            success=success,
            confidence=(
                0.9 if success else 0.2
            ),
            metadata={
                "tool_name": "code_execution",
                "return_code": return_code,
                "timeout": timeout,
            },
        )