from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.analysis.agent import DataAnalysisAgent
from app.agents.coding.agent import CodeExecutionAgent
from app.agents.research.agent import ResearchAgent
from app.agents.reviewer.agent import ReviewerAgent
from app.agents.supervisor.agent import SupervisorAgent
from app.agents.writing.agent import WritingAgent
from app.graph.state import AgentGraphState
from app.schemas.agent import AgentInput
from app.schemas.execution import Specialist, SubTask
from app.schemas.review import ReviewResult


# ============================================================
# Dependency helpers
# ============================================================


def _get_ready_subtasks(
    plan,
    completed_ids: set[str],
) -> list[SubTask]:
    """
    Return subtasks whose dependencies have all completed.
    """

    ready: list[SubTask] = []

    for subtask in plan.subtasks:
        subtask_id = str(subtask.id)

        if subtask_id in completed_ids:
            continue

        dependency_ids = {
            str(dependency)
            for dependency in subtask.dependencies
        }

        if dependency_ids.issubset(completed_ids):
            ready.append(subtask)

    return ready


def _all_subtasks_completed(
    plan,
    completed_ids: set[str],
) -> bool:
    """
    Determine whether every subtask in the execution plan
    has completed.
    """

    plan_ids = {
        str(subtask.id)
        for subtask in plan.subtasks
    }

    return plan_ids.issubset(completed_ids)


# ============================================================
# Specialist routing
# ============================================================


def route_after_specialists(
    state: AgentGraphState,
) -> str:
    """
    Decide what should happen after specialist execution.

    Possible outcomes:

    retry
        Specialist failed and still has retry attempts.

    failed
        Specialist failed and retry limit was reached.

    human_escalation
        Specialist completed but confidence is below the
        configured escalation threshold.

    review
        All planned subtasks completed successfully.

    dispatch
        More dependency-ready subtasks remain.
    """

    failure_reason = state.get(
        "failure_reason",
        "",
    )

    # --------------------------------------------------------
    # Specialist failure
    # --------------------------------------------------------

    if failure_reason:
        retry_count = state.get(
            "retry_count",
            0,
        )

        max_retries = state.get(
            "max_retries",
            2,
        )

        if retry_count <= max_retries:
            return "retry"

        return "failed"

    # --------------------------------------------------------
    # Low-confidence specialist escalation
    # --------------------------------------------------------

    confidence = state.get(
        "specialist_confidence",
        1.0,
    )

    confidence_threshold = state.get(
        "confidence_threshold",
        0.5,
    )

    if confidence < confidence_threshold:
        return "human_escalation"

    # --------------------------------------------------------
    # Successful specialist execution
    # --------------------------------------------------------

    plan = state["plan"]

    completed_ids = {
        str(subtask_id)
        for subtask_id in state.get(
            "completed_subtasks",
            [],
        )
    }

    if _all_subtasks_completed(
        plan,
        completed_ids,
    ):
        return "review"

    return "dispatch"


# ============================================================
# Review parsing
# ============================================================


def parse_review_result(
    review_output: dict[str, Any],
) -> ReviewResult:
    """
    Convert reviewer metadata into a validated ReviewResult.
    """

    review_data = review_output.get(
        "review"
    )

    if not isinstance(
        review_data,
        dict,
    ):
        raise ValueError(
            "Reviewer output does not contain a structured "
            "review result."
        )

    return ReviewResult.model_validate(
        review_data
    )


# ============================================================
# Review routing
# ============================================================


def route_after_review(
    state: AgentGraphState,
) -> str:
    """
    Route execution after reviewer evaluation.

    Routing priority:

    1. Low confidence -> escalation
    2. Approved -> synthesis
    3. Rejected with retries available -> retry
    4. Rejected after retry limit -> failed
    """

    review = state.get("review")

    if review is None:
        raise ValueError(
            "Review result is required for review routing."
        )

    # --------------------------------------------------------
    # Reviewer confidence
    # --------------------------------------------------------

    confidence = float(
        getattr(
            review,
            "confidence",
            0.0,
        )
    )

    escalation_threshold = float(
        state.get(
            "confidence_threshold",
            0.5,
        )
    )

    if confidence < escalation_threshold:
        return "escalate"

    # --------------------------------------------------------
    # Approved review
    # --------------------------------------------------------

    approved = bool(
        getattr(
            review,
            "approved",
            False,
        )
    )

    if approved:
        return "synthesis"

    # --------------------------------------------------------
    # Rejected review
    # --------------------------------------------------------

    retry_count = int(
        state.get(
            "review_retry_count",
            0,
        )
    )

    max_retries = int(
        state.get(
            "max_review_retries",
            state.get(
                "max_retries",
                2,
            ),
        )
    )

    if retry_count < max_retries:
        return "review_retry"

    return "review_failed"

async def escalate(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Phase 1 reviewer-confidence escalation boundary.

        Persistent human approval/replan behavior will be
        implemented in the HITL phase.
        """

        review = state.get(
            "review"
        )

        confidence = (
            float(
                getattr(
                    review,
                    "confidence",
                    0.0,
                )
            )
            if review is not None
            else 0.0
        )

        return {
            "escalation_required": True,
            "escalation_reason": (
                "Reviewer confidence "
                f"{confidence:.2f} is below the "
                "configured threshold "
                f"{state.get('confidence_threshold', 0.5):.2f}."
            ),
            "replan_required": True,
        }

# ============================================================
# Workflow construction
# ============================================================


def build_workflow(
    supervisor: SupervisorAgent,
    research_agent: ResearchAgent,
    analysis_agent: DataAnalysisAgent,
    writing_agent: WritingAgent,
    coding_agent: CodeExecutionAgent,
    reviewer_agent: ReviewerAgent,
):
    """
    Build the AgentFlow orchestration graph.

    Flow:

        START
          ↓
       planning
          ↓
       dispatch
          ↓
      specialist
       ↙  ↓  ↘
    retry dispatch review
                    ↙  ↓  ↘
                retry synthesize escalate
                    ↓      ↓       ↓
                specialist END     END

    Low-confidence specialist outputs are routed to the
    human_escalation boundary.

    Low-confidence reviewer outputs are routed to the
    Phase 1 escalation boundary.

    Persistent HITL resume/replan behavior is intentionally
    deferred to the HITL phase.
    """

    graph = StateGraph(
        AgentGraphState
    )

    # ========================================================
    # Planning
    # ========================================================

    async def planning(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Ask the supervisor to create the execution plan.
        """

        agent_input = AgentInput(
            task_id=state["task_id"],
            description=state["description"],
        )

        plan = await supervisor.create_plan(
            agent_input
        )

        completed_ids: set[str] = set()

        ready = _get_ready_subtasks(
            plan,
            completed_ids,
        )

        return {
            "plan": plan,
            "ready_subtasks": ready,
            "completed_subtasks": [],
            "specialist_outputs": [],

            # Specialist retry state.
            "retry_count": 0,
            "max_retries": state.get(
                "max_retries",
                2,
            ),
            "failure_reason": "",
            "retry_feedback": "",

            # Reviewer retry state.
            "review_retry_count": 0,
            "max_review_retries": state.get(
                "max_review_retries",
                2,
            ),
            "review_feedback": "",

            # Confidence routing.
            "specialist_confidence": 1.0,
            "confidence_threshold": state.get(
                "confidence_threshold",
                0.5,
            ),
        }

    # ========================================================
    # Dependency-aware dispatch
    # ========================================================

    def dispatch(
        state: AgentGraphState,
    ) -> list[Send]:
        """
        Dispatch all dependency-ready subtasks.
        """

        plan = state["plan"]

        completed_ids = {
            str(subtask_id)
            for subtask_id in state.get(
                "completed_subtasks",
                [],
            )
        }

        ready_subtasks = _get_ready_subtasks(
            plan,
            completed_ids,
        )

        sends: list[Send] = []

        for subtask in ready_subtasks:
            sends.append(
                Send(
                    "specialist",
                    {
                        **state,
                        "current_subtask": subtask,
                    },
                )
            )

        return sends

    # ========================================================
    # Specialist execution
    # ========================================================

    async def specialist(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Execute one dependency-ready specialist subtask.
        """

        subtask = state[
            "current_subtask"
        ]

        agent_input = AgentInput(
            task_id=state["task_id"],
            subtask_id=subtask.id,
            description=subtask.description,
            context={
                "required_inputs": (
                    subtask.required_inputs
                ),
                "expected_output": (
                    subtask.expected_output
                ),
                "completed_outputs": state.get(
                    "specialist_outputs",
                    [],
                ),
                "retry_count": state.get(
                    "retry_count",
                    0,
                ),
                "retry_feedback": state.get(
                    "retry_feedback",
                    "",
                ),
                "review_feedback": state.get(
                    "review_feedback",
                    "",
                ),
            },
        )

        agent_map = {
            Specialist.RESEARCH: research_agent,
            Specialist.DATA_ANALYSIS: analysis_agent,
            Specialist.WRITING: writing_agent,
            Specialist.CODE_EXECUTION: coding_agent,
        }

        agent = agent_map[
            subtask.assigned_specialist
        ]

        try:
            output = await agent.run(
                agent_input
            )

        except Exception as exc:
            return {
                "failure_reason": str(exc),
                "retry_count": (
                    state.get(
                        "retry_count",
                        0,
                    )
                    + 1
                ),
                "specialist_confidence": 0.0,
            }

        # ----------------------------------------------------
        # Specialist reported failure
        # ----------------------------------------------------

        if not output.success:
            return {
                "failure_reason": (
                    output.content
                    or "Specialist execution failed."
                ),
                "retry_count": (
                    state.get(
                        "retry_count",
                        0,
                    )
                    + 1
                ),
                "specialist_confidence": (
                    output.confidence
                    if output.confidence is not None
                    else 0.0
                ),
            }

        # ----------------------------------------------------
        # Successful specialist execution
        # ----------------------------------------------------

        confidence = (
            output.confidence
            if output.confidence is not None
            else 1.0
        )

        return {
            "specialist_outputs": [
                output.model_dump(
                    mode="json"
                ),
            ],
            "completed_subtasks": [
                str(subtask.id),
            ],
            "retry_count": 0,
            "failure_reason": "",
            "retry_feedback": "",
            "specialist_confidence": confidence,
        }

    # ========================================================
    # Specialist retry
    # ========================================================

    def retry_specialist(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Prepare the current subtask for another attempt.
        """

        failure_reason = state.get(
            "failure_reason",
            "Unknown specialist failure.",
        )

        retry_count = state.get(
            "retry_count",
            0,
        )

        return {
            "retry_feedback": (
                "Previous specialist attempt failed.\n"
                f"Failure reason: {failure_reason}\n"
                f"Retry attempt: {retry_count}\n\n"
                "Use a different approach and avoid "
                "repeating the same failed strategy."
            ),
            "failure_reason": "",
        }

    # ========================================================
    # Human escalation boundary
    # ========================================================

    def human_escalation(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Phase 1 escalation boundary.

        Persistent human approval/resume behavior will be
        implemented in the HITL phase.
        """

        return {
            "human_escalation_required": True,
            "escalation_reason": (
                "Specialist confidence "
                f"{state.get('specialist_confidence', 0.0):.2f} "
                "is below the configured threshold "
                f"{state.get('confidence_threshold', 0.5):.2f}."
            ),
        }

    # ========================================================
    # Reviewer escalation boundary
    # ========================================================

    

    # ========================================================
    # Review
    # ========================================================

    async def review(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Reviewer evaluates all specialist outputs.
        """

        review_input = AgentInput(
            task_id=state["task_id"],
            description=(
                "Review all specialist outputs produced "
                "for this execution plan."
            ),
            context={
                "plan": state["plan"].model_dump(
                    mode="json"
                ),
                "specialist_outputs": state.get(
                    "specialist_outputs",
                    [],
                ),
            },
        )

        result = await reviewer_agent.run(
            review_input
        )

        review_result = parse_review_result(
            result.metadata
        )

        return {
            "review": review_result,
            "review_feedback": (
                review_result.feedback
                if not review_result.approved
                else ""
            ),
        }

    # ========================================================
    # Reviewer retry
    # ========================================================

    def retry_after_review(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Prepare a specialist retry using reviewer feedback.
        """

        review_feedback = state.get(
            "review_feedback",
            "",
        )

        retry_count = state.get(
            "review_retry_count",
            0,
        )

        return {
            "review_retry_count": (
                retry_count + 1
            ),
            "retry_feedback": (
                "The reviewer rejected the previous output.\n\n"
                f"Reviewer feedback:\n{review_feedback}\n\n"
                "Revise the approach and produce a better result."
            ),
            "failure_reason": "",
        }

    # ========================================================
    # Synthesis
    # ========================================================

    async def synthesis(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Combine specialist outputs into the final response.
        """

        outputs = state.get(
            "specialist_outputs",
            [],
        )

        content = "\n\n".join(
            output["content"]
            for output in outputs
        )

        return {
            "final_output": content,
        }

    # ========================================================
    # Graph nodes
    # ========================================================

    graph.add_node(
        "planning",
        planning,
    )

    graph.add_node(
        "specialist",
        specialist,
    )

    graph.add_node(
        "retry_specialist",
        retry_specialist,
    )

    graph.add_node(
        "human_escalation",
        human_escalation,
    )

    graph.add_node(
        "review",
        review,
    )

    graph.add_node(
        "escalate",
        escalate,
    )

    graph.add_node(
        "retry_after_review",
        retry_after_review,
    )

    graph.add_node(
        "synthesis",
        synthesis,
    )

    # ========================================================
    # Graph edges
    # ========================================================

    graph.add_edge(
        START,
        "planning",
    )

    # Planning → dependency-aware specialist dispatch.
    graph.add_conditional_edges(
        "planning",
        dispatch,
    )

    # Specialist → retry / dispatch / review / escalation.
    graph.add_conditional_edges(
        "specialist",
        route_after_specialists,
        {
            "retry": "retry_specialist",
            "dispatch": "specialist",
            "review": "review",
            "failed": "review",
            "human_escalation": "human_escalation",
        },
    )

    # Specialist retry → specialist.
    graph.add_edge(
        "retry_specialist",
        "specialist",
    )

    # Specialist low-confidence boundary.
    graph.add_edge(
        "human_escalation",
        END,
    )

    # Reviewer → synthesis / retry / failed / escalation.
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "synthesis": "synthesis",
            "review_retry": "retry_after_review",
            "review_failed": END,
            "escalate": "escalate",
        },
    )

    # Reviewer low-confidence boundary.
    graph.add_edge(
        "escalate",
        END,
    )

    # Reviewer retry → specialist.
    graph.add_edge(
        "retry_after_review",
        "specialist",
    )

    # Synthesis → END.
    graph.add_edge(
        "synthesis",
        END,
    )

    return graph.compile()