from uuid import UUID

from app.llm.router import LLMRouter
from app.schemas.execution import ExecutionPlan


PLANNER_SYSTEM_PROMPT = """
You are the planning component of a production multi-agent
orchestration system.

Your job is to decompose a complex user task into an execution plan.

Available specialist agents:

1. research
   - Web research
   - Information gathering
   - Source discovery
   - Fact finding

2. data_analysis
   - Data processing
   - Calculations
   - Statistical analysis
   - Structured data interpretation

3. writing
   - Reports
   - Summaries
   - Documentation
   - Final prose generation

4. code_execution
   - Programming
   - Code generation
   - Code analysis
   - Controlled code execution

Rules:

- Break the task into meaningful subtasks.
- Do not create unnecessary subtasks.
- Assign every subtask to exactly one specialist.
- Define the inputs required by each subtask.
- Define the expected output clearly.
- Estimate complexity as low, medium, or high.
- Express dependencies using subtask IDs.
- A subtask must depend on another subtask if it requires
  that subtask's output.
- Independent subtasks should have no dependency.
- Do not perform the task yourself.
- Only create the execution plan.
"""


class TaskPlanner:
    """
    Produces a validated ExecutionPlan using the LLM router.
    """

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm_router = llm_router

    async def create_plan(
        self,
        *,
        task_id: UUID,
        task_description: str,
    ) -> ExecutionPlan:

        prompt = f"""
{PLANNER_SYSTEM_PROMPT}

Task ID:
{task_id}

User task:
{task_description}

Create the execution plan.
"""

        plan = await self._llm_router.ainvoke_structured(
            task_type="supervisor",
            prompt=prompt,
            schema=ExecutionPlan,
        )

        if plan.task_id != task_id:
            plan.task_id = task_id

        return plan