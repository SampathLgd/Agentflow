from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.human_decision import HumanDecisionModel
from app.observability.models import SpanModel, TraceModel


def _round(
    value: float,
    digits: int = 4,
) -> float:
    return round(float(value), digits)


def _clean_label(
    value: Any,
) -> str | None:
    """
    Normalize analytics labels.

    Empty strings, None, and literal "unknown" values are treated
    as missing so the analytics layer can continue searching for a
    better source.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() in {
        "unknown",
        "none",
        "null",
        "n/a",
    }:
        return None

    return value


def _task_type(
    trace: TraceModel,
    spans: list[SpanModel],
) -> str:
    """
    Resolve the task type from the strongest available source.

    Priority:

    1. execution/trace-level attributes
    2. span attributes.task_type
    3. LLM span agent
    4. LLM span name/metadata
    5. workflow span agent
    6. "unknown"

    We intentionally do not query TaskModel because the current
    schema does not contain a task_type column.

    The LLM router already emits task_type on LLM spans, and the
    tracing layer stores unknown metadata keys in span.attributes.
    """

    # ---------------------------------------------------------
    # 1. Trace-level task_type
    # ---------------------------------------------------------

    trace_attributes = trace.attributes or {}

    value = _clean_label(
        trace_attributes.get("task_type")
    )

    if value:
        return value

    # ---------------------------------------------------------
    # 2. Explicit span attributes.task_type
    # ---------------------------------------------------------

    for span in spans:
        span_attributes = span.attributes or {}

        value = _clean_label(
            span_attributes.get("task_type")
        )

        if value:
            return value

    # ---------------------------------------------------------
    # 3. LLM span agent
    #
    # LLMRouter calls current_trace(...,
    # agent=task_type, task_type=task_type)
    # ---------------------------------------------------------

    for span in spans:
        if span.kind != "llm":
            continue

        value = _clean_label(span.agent)

        if value:
            return value

    # ---------------------------------------------------------
    # 4. LLM span name
    #
    # This is mainly useful for older traces where task_type
    # metadata may not have been recorded.
    # ---------------------------------------------------------

    task_types = {
        "supervisor",
        "research",
        "writing",
        "reviewer",
        "data_analysis",
        "code_execution",
    }

    for span in spans:
        if span.kind != "llm":
            continue

        value = _clean_label(span.name)

        if value in task_types:
            return value

    # ---------------------------------------------------------
    # 5. Workflow/agent span fallback
    # ---------------------------------------------------------

    for span in spans:
        if span.kind in {
            "agent",
            "workflow",
            "specialist",
        }:
            value = _clean_label(
                span.agent
                or span.specialist
            )

            if value:
                return value

    # ---------------------------------------------------------
    # 6. Genuine unknown
    #
    # We keep this only when the trace truly contains no useful
    # task-type information.
    # ---------------------------------------------------------

    return "unknown"


def _human_review_ms(
    decisions: list[HumanDecisionModel],
) -> float:
    """
    Calculate actual human review time from the durable
    human-decision lifecycle.

    Review time is:
        decision.created_at -> decision.decided_at

    This measures the time the execution was actually waiting
    for a human reviewer, rather than the tiny duration of the
    resume workflow span created after the decision was made.
    """

    total = 0.0

    for decision in decisions:
        if (
            decision.status != "decided"
            or decision.decided_at is None
            or decision.created_at is None
        ):
            continue

        duration = (
            decision.decided_at
            - decision.created_at
        ).total_seconds() * 1000.0

        if duration > 0:
            total += duration

    return total

def _agent_name(
    span: SpanModel,
) -> str | None:
    """
    Resolve the agent represented by a span.

    Tool and workflow spans without an agent are not classified
    as an "unknown agent". They are simply excluded from the
    agent leaderboard.

    Priority:

    1. explicit agent
    2. specialist
    """

    value = _clean_label(span.agent)

    if value:
        return value

    value = _clean_label(span.specialist)

    if value:
        return value

    return None


async def get_observability_analytics(
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Build Phase 4 cross-execution observability analytics.

    Covers:

    - execution counts
    - execution status
    - LLM tokens
    - tool calls
    - cost
    - latency
    - human-review time
    - cost by task type
    - most expensive agents
    - model/provider usage
    - tool usage
    - escalation trends
    """

    # =========================================================
    # Load traces
    # =========================================================

    trace_result = await session.execute(
        select(TraceModel).order_by(
            TraceModel.started_at.asc()
        )
    )

    traces = list(
        trace_result.scalars().all()
    )

    # =========================================================
    # Load spans
    # =========================================================

    span_result = await session.execute(
        select(SpanModel).order_by(
            SpanModel.started_at.asc()
        )
    )

    spans = list(
        span_result.scalars().all()
    )
    decision_result = await session.execute(
        select(HumanDecisionModel).order_by(
            HumanDecisionModel.created_at.asc()
        )
    )

    decisions = list(
        decision_result.scalars().all()
    )

    decisions_by_execution: dict[
        str,
        list[HumanDecisionModel],
    ] = defaultdict(list)

    for decision in decisions:
        decisions_by_execution[
            str(decision.execution_id)
        ].append(decision)

    spans_by_trace: dict[
        str,
        list[SpanModel],
    ] = defaultdict(list)

    for span in spans:
        spans_by_trace[
            span.trace_id
        ].append(span)

    # =========================================================
    # Overview totals
    # =========================================================

    total_executions = len(traces)

    total_input_tokens = sum(
        trace.total_input_tokens or 0
        for trace in traces
    )

    total_output_tokens = sum(
        trace.total_output_tokens or 0
        for trace in traces
    )

    total_tokens = sum(
        trace.total_tokens or 0
        for trace in traces
    )

    total_tool_calls = sum(
        trace.total_tool_calls or 0
        for trace in traces
    )

    total_cost = sum(
        trace.total_cost or 0.0
        for trace in traces
    )

    total_wall_clock_ms = sum(
        trace.wall_clock_ms or 0.0
        for trace in traces
    )

    total_human_review_ms = sum(
    _human_review_ms(
        decisions_by_execution.get(
            str(trace.execution_id),
            [],
        )
    )
    for trace in traces
    )

    completed_count = sum(
        1
        for trace in traces
        if trace.status == "completed"
    )

    escalated_count = sum(
        1
        for trace in traces
        if trace.status == "escalated"
    )

    failed_count = sum(
        1
        for trace in traces
        if trace.status in {
            "failed",
            "failure",
        }
    )

    running_count = sum(
        1
        for trace in traces
        if trace.status == "running"
    )

    # =========================================================
    # Cost by task type
    # =========================================================

    task_type_data: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "task_type": "",
            "executions": 0,
            "total_tokens": 0,
            "total_tool_calls": 0,
            "total_cost": 0.0,
            "total_wall_clock_ms": 0.0,
            "total_human_review_ms": 0.0,
            "escalations": 0,
        }
    )

    for trace in traces:
        trace_spans = spans_by_trace.get(
            trace.trace_id,
            [],
        )

        task_type = _task_type(
            trace,
            trace_spans,
        )

        item = task_type_data[
            task_type
        ]

        item["task_type"] = task_type
        item["executions"] += 1
        item["total_tokens"] += (
            trace.total_tokens or 0
        )
        item["total_tool_calls"] += (
            trace.total_tool_calls or 0
        )
        item["total_cost"] += (
            trace.total_cost or 0.0
        )
        item["total_wall_clock_ms"] += (
            trace.wall_clock_ms or 0.0
        )
        item["total_human_review_ms"] += (
            _human_review_ms(
                decisions_by_execution.get(
                    str(trace.execution_id),
                    [],
                )
            )
        )

        if trace.status == "escalated":
            item["escalations"] += 1

    cost_by_task_type = []

    for item in task_type_data.values():
        executions = item["executions"]

        cost_by_task_type.append(
            {
                **item,
                "total_cost": _round(
                    item["total_cost"]
                ),
                "average_cost": _round(
                    item["total_cost"]
                    / executions
                )
                if executions
                else 0.0,
                "average_wall_clock_ms": _round(
                    item["total_wall_clock_ms"]
                    / executions
                )
                if executions
                else 0.0,
                "average_human_review_ms": _round(
                    item["total_human_review_ms"]
                    / executions
                )
                if executions
                else 0.0,
                "escalation_rate": _round(
                    item["escalations"]
                    / executions,
                    4,
                )
                if executions
                else 0.0,
            }
        )

    cost_by_task_type.sort(
        key=lambda item: item["total_cost"],
        reverse=True,
    )

    # =========================================================
    # Agent analytics
    # =========================================================

    agent_data: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "agent": "",
            "span_count": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_duration_ms": 0.0,
            "tool_calls": 0,
            "warnings": 0,
            "failures": 0,
        }
    )

    for span in spans:
        agent = _agent_name(span)

        # Do not manufacture an "unknown" agent.
        if not agent:
            continue

        item = agent_data[agent]

        item["agent"] = agent
        item["span_count"] += 1
        item["total_tokens"] += (
            span.total_tokens or 0
        )
        item["total_cost"] += (
            span.cost or 0.0
        )
        item["total_duration_ms"] += (
            span.duration_ms or 0.0
        )

        if span.kind == "tool":
            item["tool_calls"] += 1

        if span.status == "warning":
            item["warnings"] += 1

        if span.status in {
            "failed",
            "failure",
        }:
            item["failures"] += 1

    agents = []

    for item in agent_data.values():
        agents.append(
            {
                **item,
                "total_cost": _round(
                    item["total_cost"]
                ),
                "total_duration_ms": _round(
                    item["total_duration_ms"],
                    2,
                ),
            }
        )

    agents.sort(
        key=lambda item: item["total_cost"],
        reverse=True,
    )

    # =========================================================
    # Model/provider analytics
    # =========================================================

    model_data: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "provider": "",
            "model": "",
            "agent": "",
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_duration_ms": 0.0,
        }
    )

    for span in spans:
        if span.kind != "llm":
            continue

        provider = (
            _clean_label(span.provider)
            or "unknown"
        )

        model = (
            _clean_label(span.model)
            or "unknown"
        )

        agent = (
            _clean_label(span.agent)
            or _clean_label(span.specialist)
            or "unknown"
        )

        key = (
            provider,
            model,
            agent,
        )

        item = model_data[key]

        item["provider"] = provider
        item["model"] = model
        item["agent"] = agent
        item["calls"] += 1
        item["input_tokens"] += (
            span.input_tokens or 0
        )
        item["output_tokens"] += (
            span.output_tokens or 0
        )
        item["total_tokens"] += (
            span.total_tokens or 0
        )
        item["total_cost"] += (
            span.cost or 0.0
        )
        item["total_duration_ms"] += (
            span.duration_ms or 0.0
        )

    models = []

    for item in model_data.values():
        models.append(
            {
                **item,
                "total_cost": _round(
                    item["total_cost"]
                ),
                "total_duration_ms": _round(
                    item["total_duration_ms"],
                    2,
                ),
            }
        )

    models.sort(
        key=lambda item: item["total_cost"],
        reverse=True,
    )

    # =========================================================
    # Tool usage
    # =========================================================

    tool_data: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "tool_name": "",
            "calls": 0,
            "total_duration_ms": 0.0,
            "total_cost": 0.0,
            "failures": 0,
        }
    )

    for span in spans:
        if span.kind != "tool":
            continue

        tool_name = (
            _clean_label(span.tool_name)
            or _clean_label(span.name)
            or "unknown"
        )

        item = tool_data[tool_name]

        item["tool_name"] = tool_name
        item["calls"] += 1
        item["total_duration_ms"] += (
            span.duration_ms or 0.0
        )
        item["total_cost"] += (
            span.cost or 0.0
        )

        if span.status in {
            "failed",
            "failure",
        }:
            item["failures"] += 1

    tools = []

    for item in tool_data.values():
        calls = item["calls"]

        tools.append(
            {
                **item,
                "total_duration_ms": _round(
                    item["total_duration_ms"],
                    2,
                ),
                "total_cost": _round(
                    item["total_cost"]
                ),
                "average_duration_ms": _round(
                    item["total_duration_ms"]
                    / calls
                )
                if calls
                else 0.0,
                "failure_rate": _round(
                    item["failures"]
                    / calls,
                    4,
                )
                if calls
                else 0.0,
            }
        )

    tools.sort(
        key=lambda item: item["calls"],
        reverse=True,
    )

    # =========================================================
    # Escalation trend
    # =========================================================

    escalation_trends = []

    for trace in traces:
        escalation_trends.append(
            {
                "execution_id": str(
                    trace.execution_id
                ),
                "started_at": trace.started_at,
                "status": trace.status,
                "escalated": (
                    trace.status
                    == "escalated"
                ),
                "total_cost": _round(
                    trace.total_cost or 0.0
                ),
                "total_tokens": (
                    trace.total_tokens or 0
                ),
                "wall_clock_ms": _round(
                    trace.wall_clock_ms or 0.0,
                    2,
                ),
            }
        )

    # =========================================================
    # Final response
    # =========================================================

    return {
        "overview": {
            "execution_count": (
                total_executions
            ),
            "completed_count": (
                completed_count
            ),
            "escalated_count": (
                escalated_count
            ),
            "failed_count": (
                failed_count
            ),
            "running_count": (
                running_count
            ),
            "escalation_rate": _round(
                escalated_count
                / total_executions,
                4,
            )
            if total_executions
            else 0.0,
            "total_input_tokens": (
                total_input_tokens
            ),
            "total_output_tokens": (
                total_output_tokens
            ),
            "total_tokens": (
                total_tokens
            ),
            "total_tool_calls": (
                total_tool_calls
            ),
            "total_cost": _round(
                total_cost
            ),
            "average_cost": _round(
                total_cost
                / total_executions
            )
            if total_executions
            else 0.0,
            "average_wall_clock_ms": _round(
                total_wall_clock_ms
                / total_executions
            )
            if total_executions
            else 0.0,
            "total_human_review_ms": _round(
                total_human_review_ms,
                2,
            ),
            "average_human_review_ms": _round(
                total_human_review_ms
                / total_executions,
                2,
            )
            if total_executions
            else 0.0,
        },
        "cost_by_task_type": (
            cost_by_task_type
        ),
        "agents": agents,
        "models": models,
        "tools": tools,
        "escalation_trends": (
            escalation_trends
        ),
    }