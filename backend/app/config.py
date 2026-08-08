from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentFlow"
    app_version: str = "0.1.0"
    environment: str = "development"

    # ---------------------------------------------------------
    # LLM Provider Routing
    # ---------------------------------------------------------

    llm_provider_order: str = "gemini,openrouter"

    # ---------------------------------------------------------
    # Gemini
    # ---------------------------------------------------------

    gemini_api_key: str | None = None

    gemini_model: str = "gemini-2.5-flash-lite"

    # ---------------------------------------------------------
    # OpenRouter
    # ---------------------------------------------------------

    openrouter_api_key: str | None = None

    openrouter_model: str = "openrouter/free"

    # ---------------------------------------------------------
    # Task → Primary Provider Assignment
    # ---------------------------------------------------------

    supervisor_provider: str = "gemini"

    research_provider: str = "gemini"

    writing_provider: str = "gemini"

    reviewer_provider: str = "gemini"

    data_analysis_provider: str = "openrouter"

    code_execution_provider: str = "openrouter"

    # ---------------------------------------------------------
    # Agent Configuration
    # ---------------------------------------------------------

    planner_temperature: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_provider_order(self) -> list[str]:
        """
        Return providers in configured fallback priority.
        """

        return [
            provider.strip().lower()
            for provider in self.llm_provider_order.split(",")
            if provider.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()