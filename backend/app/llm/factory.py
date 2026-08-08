from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.llm.providers import LLMProviderError


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def create_llm(
    settings: Settings,
    provider: str,
) -> BaseChatModel:
    """
    Create an LLM for a specific provider.

    This function is intentionally unaware of task assignment
    and fallback logic. That responsibility belongs to the
    LLM router.

    Parameters
    ----------
    settings:
        Application configuration.

    provider:
        Provider name, e.g. "gemini" or "openrouter".
    """

    provider = provider.lower().strip()

    # ---------------------------------------------------------
    # Gemini
    # ---------------------------------------------------------

    if provider == "gemini":

        if not settings.gemini_api_key:
            raise LLMProviderError(
                "GEMINI_API_KEY is required when "
                "using the Gemini provider."
            )

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
        )

    # ---------------------------------------------------------
    # OpenRouter
    # ---------------------------------------------------------

    if provider == "openrouter":

        if not settings.openrouter_api_key:
            raise LLMProviderError(
                "OPENROUTER_API_KEY is required when "
                "using the OpenRouter provider."
            )

        return ChatOpenAI(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=settings.planner_temperature,
        )

    # ---------------------------------------------------------
    # Unsupported provider
    # ---------------------------------------------------------

    raise LLMProviderError(
        f"Unsupported LLM provider: {provider}"
    )