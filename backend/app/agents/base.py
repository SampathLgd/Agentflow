from abc import ABC, abstractmethod

from app.schemas.agent import AgentInput, AgentOutput


class BaseAgent(ABC):
    """
    Common interface for all AgentFlow agents.
    """

    name: str

    @abstractmethod
    async def run(self, agent_input: AgentInput) -> AgentOutput:
        """
        Execute the agent for a single input.
        """
        raise NotImplementedError