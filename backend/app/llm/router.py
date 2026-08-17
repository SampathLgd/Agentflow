from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from app.config import Settings
from app.llm.factory import create_llm
from app.llm.providers import LLMProviderError
from app.observability.tracing import (
    annotate_current_span,
    current_trace,
)


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
    - Emit observability spans around provider calls.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self.settings = settings

        self._provider_order = (
            settings.get_provider_order()
        )

        if not self._provider_order:
            raise LLMProviderError(
                "LLM_PROVIDER_ORDER must contain "
                "at least one provider."
            )

    # ---------------------------------------------------------
    # Provider configuration
    # ---------------------------------------------------------

    def _task_provider(
        self,
        task_type: str,
    ) -> str:
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
        Primary provider first, followed by configured fallbacks.
        """

        primary = self._task_provider(
            task_type
        )

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
    def _is_retryable_error(
        error: Exception,
    ) -> bool:
        status_code = getattr(
            error,
            "status_code",
            None,
        )

        if status_code in {
            408,
            409,
            429,
            500,
            502,
            503,
            504,
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
    # Usage extraction
    # ---------------------------------------------------------

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> tuple[
        int | None,
        int | None,
        int | None,
        float | None,
    ]:
        """
        Extract:

            input_tokens
            output_tokens
            total_tokens
            provider_cost

        from LangChain and provider-specific metadata.
        """

        if response is None:
            return (
                None,
                None,
                None,
                None,
            )

        usage: dict[str, Any] = {}
        metadata: dict[str, Any] = {}

        # ---------------------------------------------------------
        # LangChain normalized metadata
        # ---------------------------------------------------------

        normalized_usage = getattr(
            response,
            "usage_metadata",
            None,
        )

        if isinstance(
            normalized_usage,
            dict,
        ):
            usage.update(
                normalized_usage
            )

        # ---------------------------------------------------------
        # Provider response metadata
        # ---------------------------------------------------------

        response_metadata = getattr(
            response,
            "response_metadata",
            None,
        )

        if isinstance(
            response_metadata,
            dict,
        ):
            metadata = response_metadata

            provider_usage = (
                response_metadata.get("usage")
                or response_metadata.get(
                    "usage_metadata"
                )
                or response_metadata.get(
                    "token_usage"
                )
            )

            if isinstance(
                provider_usage,
                dict,
            ):
                for key, value in provider_usage.items():
                    if key not in usage:
                        usage[key] = value

        # ---------------------------------------------------------
        # Input tokens
        # ---------------------------------------------------------

        input_tokens = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("inputTokenCount")
            or usage.get("promptTokenCount")
            or usage.get("prompt_token_count")
        )

        # ---------------------------------------------------------
        # Output tokens
        # ---------------------------------------------------------

        output_tokens = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("outputTokenCount")
            or usage.get("candidatesTokenCount")
            or usage.get("candidates_token_count")
        )

        # ---------------------------------------------------------
        # Total tokens
        # ---------------------------------------------------------

        total_tokens = (
            usage.get("total_tokens")
            or usage.get("totalTokenCount")
            or usage.get("total_token_count")
        )

        if (
            total_tokens is None
            and input_tokens is not None
            and output_tokens is not None
        ):
            total_tokens = (
                int(input_tokens)
                + int(output_tokens)
            )

        # ---------------------------------------------------------
        # Cost
        # ---------------------------------------------------------

        cost = (
            usage.get("cost")
            or usage.get("cost_usd")
            or usage.get("total_cost")
            or metadata.get("cost")
            or metadata.get("cost_usd")
        )

        return (
            (
                int(input_tokens)
                if input_tokens is not None
                else None
            ),
            (
                int(output_tokens)
                if output_tokens is not None
                else None
            ),
            (
                int(total_tokens)
                if total_tokens is not None
                else None
            ),
            (
                float(cost)
                if cost is not None
                else None
            ),
        )

    # ---------------------------------------------------------
    # Model name extraction
    # ---------------------------------------------------------

    @staticmethod
    def _extract_model_name(
        model: BaseChatModel,
        response: Any = None,
    ) -> str | None:
        """
        Extract the provider/model identifier for trace metadata.

        Structured LangChain responses may be wrapped as:

            {
                "raw": AIMessage(...),
                "parsed": ...,
                "parsing_error": None,
            }

        Therefore inspect:
        1. The response wrapper.
        2. The raw AIMessage.
        3. Additional kwargs.
        4. The instantiated model.
        """

        candidates: list[Any] = []

        if response is not None:
            candidates.append(response)

            if isinstance(
                response,
                dict,
            ):
                raw = response.get(
                    "raw"
                )

                if raw is not None:
                    candidates.append(raw)

        for candidate in candidates:
            if candidate is None:
                continue

            # -----------------------------------------------------
            # response_metadata
            # -----------------------------------------------------

            metadata = getattr(
                candidate,
                "response_metadata",
                None,
            )

            if isinstance(
                metadata,
                dict,
            ):
                for key in (
                    "model_name",
                    "model",
                    "model_id",
                    "modelName",
                    "modelId",
                ):
                    value = metadata.get(key)

                    if value:
                        return str(value)

                # Some providers nest model information.
                for nested_key in (
                    "response",
                    "metadata",
                    "model_info",
                ):
                    nested = metadata.get(
                        nested_key
                    )

                    if isinstance(
                        nested,
                        dict,
                    ):
                        for key in (
                            "model_name",
                            "model",
                            "model_id",
                            "modelName",
                            "modelId",
                        ):
                            value = nested.get(key)

                            if value:
                                return str(value)

            # -----------------------------------------------------
            # additional_kwargs
            # -----------------------------------------------------

            additional_kwargs = getattr(
                candidate,
                "additional_kwargs",
                None,
            )

            if isinstance(
                additional_kwargs,
                dict,
            ):
                for key in (
                    "model_name",
                    "model",
                    "model_id",
                    "modelName",
                    "modelId",
                ):
                    value = additional_kwargs.get(
                        key
                    )

                    if value:
                        return str(value)

        # ---------------------------------------------------------
        # Instantiated model
        # ---------------------------------------------------------

        for attribute in (
            "model_name",
            "model",
            "model_id",
        ):
            value = getattr(
                model,
                attribute,
                None,
            )

            if value:
                return str(value)

        return None

    # ---------------------------------------------------------
    # Cost estimation
    # ---------------------------------------------------------

    def _estimate_cost(
        self,
        *,
        provider: str,
        model: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        provider_cost: float | None,
    ) -> float | None:
        """
        Prefer provider-reported cost.

        If Gemini does not provide cost metadata, estimate using
        the configured Gemini input/output price fields.

        OpenRouter is not estimated here because its model/provider
        pricing is dynamic.
        """

        if provider_cost is not None:
            return provider_cost

        if provider.lower() != "gemini":
            return None

        if (
            input_tokens is None
            and output_tokens is None
        ):
            return None

        input_cost = (
            (input_tokens or 0)
            / 1_000_000
            * self.settings.gemini_input_cost_per_million
        )

        output_cost = (
            (output_tokens or 0)
            / 1_000_000
            * self.settings.gemini_output_cost_per_million
        )

        return input_cost + output_cost

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

        candidates = self._provider_candidates(
            task_type
        )

        errors: list[str] = []

        for provider in candidates:
            try:
                model = self._create_model(
                    provider
                )

                model_name = (
                    self._extract_model_name(
                        model
                    )
                )

                with current_trace(
                    name="llm.generate",
                    kind="llm",
                    agent=task_type,
                    provider=provider,
                    model=model_name,
                    task_type=task_type,
                ) as span:

                    if span is not None:
                        annotate_current_span(
                            input_value=prompt,
                            prompt=prompt,
                        )

                    response = await model.ainvoke(
                        prompt
                    )

                    (
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        provider_cost,
                    ) = self._extract_usage(
                        response
                    )

                    # The response can contain the authoritative
                    # provider/model identifier.
                    model_name = (
                        self._extract_model_name(
                            model,
                            response,
                        )
                    )

                    cost = self._estimate_cost(
                        provider=provider,
                        model=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        provider_cost=provider_cost,
                    )

                    if span is not None:
                        annotate_current_span(
                            raw_response=response,
                            provider=provider,
                            model=model_name,
                        )

                        span.finish(
                            status="success",
                            output=response,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            cost=cost,
                        )

                    return response

            except Exception as error:
                if not self._is_retryable_error(
                    error
                ):
                    raise

                errors.append(
                    f"{provider}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

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

        Production LangChain models use include_raw=True so that
        the original AIMessage is retained for token/cost/model
        observability.

        Lightweight test/fake models may return the Pydantic
        object directly. Both response shapes are supported.
        """

        candidates = self._provider_candidates(
            task_type
        )

        errors: list[str] = []

        for provider in candidates:
            try:
                model = self._create_model(
                    provider
                )

                initial_model_name = (
                    self._extract_model_name(
                        model
                    )
                )

                with current_trace(
                    name="llm.generate_structured",
                    kind="llm",
                    agent=task_type,
                    provider=provider,
                    model=initial_model_name,
                    task_type=task_type,
                    schema=schema.__name__,
                ) as span:

                    if span is not None:
                        annotate_current_span(
                            input_value=prompt,
                            prompt=prompt,
                        )

                    # -------------------------------------------------
                    # Prefer include_raw=True.
                    #
                    # Some lightweight test/fake models do not accept
                    # include_raw. Fall back to the compatible call.
                    # -------------------------------------------------

                    try:
                        structured_model = (
                            model.with_structured_output(
                                schema,
                                method="json_schema",
                                include_raw=True,
                            )
                        )

                    except TypeError as exc:
                        if "include_raw" not in str(
                            exc
                        ):
                            raise

                        structured_model = (
                            model.with_structured_output(
                                schema,
                                method="json_schema",
                            )
                        )

                    structured_result = (
                        await structured_model.ainvoke(
                            prompt
                        )
                    )

                    # -------------------------------------------------
                    # Normal LangChain include_raw=True response:
                    #
                    # {
                    #     "raw": AIMessage,
                    #     "parsed": PydanticModel,
                    #     "parsing_error": None,
                    # }
                    # -------------------------------------------------

                    if isinstance(
                        structured_result,
                        dict,
                    ):
                        result = (
                            structured_result.get(
                                "parsed"
                            )
                        )

                        raw_response = (
                            structured_result.get(
                                "raw"
                            )
                        )

                        parsing_error = (
                            structured_result.get(
                                "parsing_error"
                            )
                        )

                        if parsing_error is not None:
                            raise parsing_error

                    # -------------------------------------------------
                    # Compatibility with fake/simple models.
                    # -------------------------------------------------

                    elif isinstance(
                        structured_result,
                        schema,
                    ):
                        result = structured_result
                        raw_response = None

                    else:
                        raise TypeError(
                            "Structured LLM response did not "
                            "return a valid Pydantic result or "
                            "raw/parsed structure."
                        )

                    if not isinstance(
                        result,
                        schema,
                    ):
                        raise TypeError(
                            "LLM returned an unexpected "
                            "structured output type."
                        )

                    # -------------------------------------------------
                    # Extract usage/model from the ORIGINAL AIMessage.
                    # -------------------------------------------------

                    (
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        provider_cost,
                    ) = self._extract_usage(
                        raw_response
                    )

                    model_name = (
                        self._extract_model_name(
                            model,
                            structured_result,
                        )
                    )

                    # Explicitly retry against raw response too.
                    #
                    # This is useful for providers where model metadata
                    # only exists on AIMessage.response_metadata.
                    if model_name is None:
                        model_name = (
                            self._extract_model_name(
                                model,
                                raw_response,
                            )
                        )

                    cost = self._estimate_cost(
                        provider=provider,
                        model=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        provider_cost=provider_cost,
                    )

                    if span is not None:
                        annotate_current_span(
                            raw_response=raw_response,
                            provider=provider,
                            model=model_name,
                            schema=schema.__name__,
                        )

                        span.finish(
                            status="success",
                            output=result,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            cost=cost,
                        )

                    return result

            except Exception as error:
                if not self._is_retryable_error(
                    error
                ):
                    raise

                errors.append(
                    f"{provider}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

        raise LLMRouterError(
            "All configured LLM providers failed "
            "while requesting structured output.\n"
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
        Verify that a provider can be instantiated.

        This intentionally does not perform an LLM generation.
        """

        try:
            self._create_model(
                provider
            )
            return True

        except Exception:
            return False