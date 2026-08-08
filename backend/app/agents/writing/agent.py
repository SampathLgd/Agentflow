from app.agents.base import BaseAgent
from app.agents.tool_runner import SpecialistToolRunner
from app.llm.router import LLMRouter
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import Specialist


class WritingAgent(BaseAgent):
    name = Specialist.WRITING

    def __init__(
        self,
        llm_router: LLMRouter,
        tool_runner: SpecialistToolRunner,
    ) -> None:
        self._llm_router = llm_router
        self._tool_runner = tool_runner

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:
        """
        Generate written content and optionally use the
        workspace file tools.

        Phase 1 behavior:

        - input_path: read existing workspace content
        - output_path: write generated content
        - neither: simply return generated content
        """

        context = agent_input.context

        source_content = ""

        # ----------------------------------------------------
        # Optional file read
        # ----------------------------------------------------

        input_path = context.get(
            "input_path"
        )

        if isinstance(
            input_path,
            str,
        ) and input_path.strip():

            read_result = await self._tool_runner.run(
                task_id=agent_input.task_id,
                subtask_id=agent_input.subtask_id,
                specialist=Specialist.WRITING,
                tool_name="file_read",
                arguments={
                    "path": input_path,
                },
            )

            source_content = read_result.get(
                "content",
                "",
            )

        # ----------------------------------------------------
        # Build writing prompt
        # ----------------------------------------------------

        completed_outputs = context.get(
            "completed_outputs",
            [],
        )

        expected_output = context.get(
            "expected_output",
            "",
        )

        prompt = f"""
You are the AgentFlow writing specialist.

Produce the requested written output.

Task:
{agent_input.description}

Expected output:
{expected_output}

Existing source material:
{source_content}

Previous specialist outputs:
{completed_outputs}

Write a clear, useful final response.
"""

        # ----------------------------------------------------
        # LLM generation
        # ----------------------------------------------------

        response = await self._llm_router.ainvoke(
            task_type="writing",
            prompt=prompt,
        )

        content = getattr(
            response,
            "content",
            str(response),
        )

        # ----------------------------------------------------
        # Optional file write
        # ----------------------------------------------------

        output_path = context.get(
            "output_path"
        )

        metadata = {
            "llm_backed": True,
        }

        if isinstance(
            output_path,
            str,
        ) and output_path.strip():

            write_result = await self._tool_runner.run(
                task_id=agent_input.task_id,
                subtask_id=agent_input.subtask_id,
                specialist=Specialist.WRITING,
                tool_name="file_write",
                arguments={
                    "path": output_path,
                    "content": content,
                },
            )

            metadata["tool_name"] = "file_write"
            metadata["file_result"] = write_result

        return AgentOutput(
            agent=self.name,
            specialist=Specialist.WRITING,
            subtask_id=agent_input.subtask_id,
            content=content,
            success=True,
            confidence=0.85,
            metadata=metadata,
        )