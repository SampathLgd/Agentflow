from langchain_core.language_models.chat_models import BaseChatModel


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot be initialized."""


class LLMProvider:
    """
    Provider abstraction used by AgentFlow.

    Agents should depend on BaseChatModel/LLMProvider,
    not directly on Gemini or OpenRouter.
    """

    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def get_model(self) -> BaseChatModel:
        return self.model