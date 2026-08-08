from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from app.config import Settings
from app.llm.factory import create_llm
from app.llm.providers import LLMProviderError


T = TypeVar("T", bound=BaseModel)


class LLMRouterError(RuntimeError):
    """Raised when all configured LLM providers fail."""


class LLMRouter:
    """
    Routes LLM requests between configured providers.

    Responsibilities:
    - Select the primary provider for a task.
    - Detect retryable provider failures.
    - Fall back to another configured provider.
    - Avoid retrying permanently invalid requests.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self._provider_order = settings.get_provider_order()

        if not self._provider_order:
            raise LLMProviderError(
                "LLM_PROVIDER_ORDER must contain at least one provider."
            )

    # ---------------------------------------------------------
    # Provider configuration
    # ---------------------------------------------------------

    def _task_provider(self, task_type: str) -> str:
        """
        Return the configured primary provider for a task.
        """

        provider_map = {
            "supervisor": self.settings.supervisor_provider,
            "research": self.settings.research_provider,
            "writing": self.settings.writing_provider,
            "reviewer": self.settings.reviewer_provider,
            "data_analysis": self.settings.data_analysis_provider,
            "code_execution": self.settings.code_execution_provider,
        }

        provider = provider_map.get(task_type)

        if provider is None:
            raise LLMProviderError(
                f"No LLM provider configured for task type: "
                f"{task_type}"
            )

        return provider.lower().strip()

    def _provider_candidates(
        self,
        task_type: str,
    ) -> list[str]:
        """
        Return primary provider first, followed by fallback providers.
        """

        primary = self._task_provider(task_type)

        candidates = [primary]

        for provider in self._provider_order:
            provider = provider.lower().strip()

            if provider not in candidates:
                candidates.append(provider)

        return candidates

    # ---------------------------------------------------------
    # Error classification
    # ---------------------------------------------------------

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """
        Determine whether an LLM error should trigger fallback.

        Retry/fallback cases:
        - rate limits
        - quota exhaustion
        - temporary provider failures
        - timeouts
        - connection failures

        Non-retryable cases:
        - invalid API key
        - invalid request
        - application/programming errors
        """

        status_code = getattr(error, "status_code", None)

        if status_code in {
            408,  # Request Timeout
            409,  # Conflict / transient provider issue
            429,  # Rate limit / quota
            500,  # Provider server error
            502,  # Bad Gateway
            503,  # Service unavailable
            504,  # Gateway timeout
        }:
            return True

        error_text = str(error).lower()

        retryable_terms = (
            "rate limit",
            "rate_limit",
            "quota",
            "quota exceeded",
            "too many requests",
            "temporarily unavailable",
            "service unavailable",
            "internal server error",
            "bad gateway",
            "gateway timeout",
            "timeout",
            "timed out",
            "connection error",
            "connection reset",
        )

        return any(
            term in error_text
            for term in retryable_terms
        )

    # ---------------------------------------------------------
    # Model creation
    # ---------------------------------------------------------

    def _create_model(
        self,
        provider: str,
    ) -> BaseChatModel:
        return create_llm(
            settings=self.settings,
            provider=provider,
        )

    # ---------------------------------------------------------
    # Standard invocation
    # ---------------------------------------------------------

    async def ainvoke(
        self,
        *,
        task_type: str,
        prompt: str,
    ) -> Any:
        """
        Invoke an LLM using the configured provider/fallback chain.
        """

        candidates = self._provider_candidates(task_type)

        errors: list[str] = []

        for provider in candidates:
            try:
                model = self._create_model(provider)

                response = await model.ainvoke(prompt)

                return response

            except Exception as error:
                if not self._is_retryable_error(error):
                    raise

                errors.append(
                    f"{provider}: {type(error).__name__}: {error}"
                )

                continue

        raise LLMRouterError(
            "All configured LLM providers failed.\n"
            + "\n".join(errors)
        )

    # ---------------------------------------------------------
    # Structured output
    # ---------------------------------------------------------

    async def ainvoke_structured(
        self,
        *,
        task_type: str,
        prompt: str,
        schema: type[T],
    ) -> T:
        """
        Invoke an LLM and require a validated Pydantic response.

        This is used by the Supervisor planner to produce
        an ExecutionPlan.
        """

        candidates = self._provider_candidates(task_type)

        errors: list[str] = []

        for provider in candidates:
            try:
                model = self._create_model(provider)

                structured_model = model.with_structured_output(
                    schema,
                    method="json_schema",
                )

                result = await structured_model.ainvoke(
                    prompt
                )

                if not isinstance(result, schema):
                    raise TypeError(
                        "LLM returned an unexpected structured "
                        "output type."
                    )

                return result

            except Exception as error:
                if not self._is_retryable_error(error):
                    raise

                errors.append(
                    f"{provider}: {type(error).__name__}: {error}"
                )

                continue

        raise LLMRouterError(
            "All configured LLM providers failed while "
            "requesting structured output.\n"
            + "\n".join(errors)
        )

    # ---------------------------------------------------------
    # Health check
    # ---------------------------------------------------------

    async def health_check(
        self,
        provider: str,
    ) -> bool:
        """
        Basic provider availability check.

        This does not perform a real LLM generation request.
        It only verifies that the provider can be instantiated.
        """

        try:
            self._create_model(provider)
            return True

        except Exception:
            return False