from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentFlow"
    app_version: str = "0.1.0"
    environment: str = "development"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "agentflow"
    postgres_user: str = "postgres"
    postgres_password: str | None = None

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_database: int = 0
    redis_password: str | None = None

    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = (
        "agentflow_long_term_memory"
    )

    workspace_root: str = "."
    database_path: str = "agentflow.db"
    allowed_api_hosts: str = ""
    code_execution_timeout_seconds: float = 5.0

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
    @property
    def postgres_async_url(self) -> str:
            if not self.postgres_password:
                raise ValueError(
                    "POSTGRES_PASSWORD must be configured."
                )

            return (
                "postgresql+asyncpg://"
                f"{self.postgres_user}:"
                f"{self.postgres_password}@"
                f"{self.postgres_host}:"
                f"{self.postgres_port}/"
                f"{self.postgres_database}"
            )
    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return (
                "redis://:"
                f"{self.redis_password}@"
                f"{self.redis_host}:"
                f"{self.redis_port}/"
                f"{self.redis_database}"
            )

        return (
            "redis://"
            f"{self.redis_host}:"
            f"{self.redis_port}/"
            f"{self.redis_database}"
        )
    @property
    def allowed_api_host_set(self) -> set[str]:
        return {
            host.strip().lower()
            for host in self.allowed_api_hosts.split(",")
            if host.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
