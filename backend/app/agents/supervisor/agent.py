from app.agents.base import BaseAgent
from app.agents.supervisor.planner import TaskPlanner
from app.schemas.agent import AgentInput, AgentOutput
from app.schemas.execution import ExecutionPlan


class SupervisorAgent(BaseAgent):
    """
    Supervisor responsible for planning and orchestration.

    Planning is intentionally kept as an internal Supervisor capability
    rather than creating a separate Planner agent.
    """

    name = "supervisor"

    def __init__(self, planner: TaskPlanner) -> None:
        self._planner = planner

    async def create_plan(
        self,
        agent_input: AgentInput,
    ) -> ExecutionPlan:
        return await self._planner.create_plan(
            task_id=agent_input.task_id,
            task_description=agent_input.description,
        )

    async def run(
        self,
        agent_input: AgentInput,
    ) -> AgentOutput:
        plan = await self.create_plan(agent_input)

        return AgentOutput(
            agent=self.name,
            content=plan.model_dump_json(),
            success=True,
            metadata={
                "subtask_count": len(plan.subtasks),
            },
        )