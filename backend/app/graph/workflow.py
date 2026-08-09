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
from app.memory.base import WorkingMemoryStore
from app.memory.long_term import (
    LongTermMemory,
    LongTermMemoryStore,
)
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
    """

    failure_reason = state.get(
        "failure_reason",
        "",
    )

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
    """

    review = state.get("review")

    if review is None:
        raise ValueError(
            "Review result is required for review routing."
        )

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

    approved = bool(
        getattr(
            review,
            "approved",
            False,
        )
    )

    if approved:
        return "synthesis"

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


# ============================================================
# Reviewer escalation
# ============================================================


async def escalate(
    state: AgentGraphState,
) -> dict[str, Any]:
    """
    Phase 1 reviewer-confidence escalation boundary.

    Persistent human approval/replan behavior is deferred
    to the HITL phase.
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
    working_memory: WorkingMemoryStore | None = None,
    long_term_memory: LongTermMemoryStore | None = None,
):
    """
    Build the AgentFlow orchestration graph.

    Working memory is injected as an infrastructure dependency
    rather than being placed inside LangGraph state.

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

    Working memory lifecycle:

        planning
            ↓
        save plan
            ↓
        specialists
            ↓
        save outputs/errors/intermediate results
            ↓
        review
            ↓
        synthesis/failure
            ↓
        clear task memory
    """

    graph = StateGraph(
        AgentGraphState
    )

    # ========================================================
    # Working-memory helpers
    # ========================================================

    async def _save_error(
        state: AgentGraphState,
        message: str,
        *,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record an error if working memory is configured.
        """

        if working_memory is None:
            return

        await working_memory.add_error(
            state["task_id"],
            message,
            source=source,
            metadata=metadata,
        )

    async def _clear_memory(
        state: AgentGraphState,
    ) -> None:
        """
        Clear task-scoped working memory.

        This is intentionally a no-op when working memory
        has not been configured.
        """

        if working_memory is None:
            return

        await working_memory.clear(
            state["task_id"]
        )

    # ========================================================
    # Long-term memory retrieval
    # ========================================================

    async def retrieve_long_term_memory(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Retrieve relevant memories from previous executions
        for the current user.

        Long-term memory is optional. If it is not configured,
        the workflow continues normally.
        """

        if long_term_memory is None:
            return {
                "long_term_memories": [],
            }

        user_id = state.get(
            "user_id",
            "",
        )

        if not user_id:
            return {
                "long_term_memories": [],
            }

        results = await long_term_memory.search(
            user_id=user_id,
            query=state["description"],
            limit=5,
        )

        memories = [
            {
                "memory": result.memory.model_dump(
                    mode="json"
                ),
                "distance": result.distance,
            }
            for result in results
        ]

        return {
            "long_term_memories": memories,
        }
    # ========================================================
    # Planning
    # ========================================================

    async def planning(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Ask the supervisor to create the execution plan.

        The plan is also persisted into task-scoped working memory.
        """

        agent_input = AgentInput(
             task_id=state["task_id"],
            description=state["description"],
            context={
                "long_term_memories": state.get(
                    "long_term_memories",
                    [],
                ),
            },
        )

        plan = await supervisor.create_plan(
            agent_input
        )

        completed_ids: set[str] = set()

        ready = _get_ready_subtasks(
            plan,
            completed_ids,
        )

        # ----------------------------------------------------
        # Working memory: save execution plan
        # ----------------------------------------------------

        if working_memory is not None:
            await working_memory.set_plan(
                state["task_id"],
                plan.model_dump(
                    mode="json"
                ),
            )

        return {
            "plan": plan,
            "ready_subtasks": ready,
            "completed_subtasks": [],
            "specialist_outputs": [],

            "long_term_memories": state.get(
                "long_term_memories",
                [],
            ),

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

            # Escalation state.
            "human_escalation_required": False,
            "escalation_required": False,
            "replan_required": False,
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

        Working memory receives:
        - successful output
        - intermediate result
        - failures
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
                "long_term_memories": state.get(
                    "long_term_memories",
                    [],
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

        # ----------------------------------------------------
        # Execute specialist
        # ----------------------------------------------------

        try:
            output = await agent.run(
                agent_input
            )

        except Exception as exc:
            error_message = str(exc)

            await _save_error(
                state,
                error_message,
                source=(
                    f"specialist:"
                    f"{subtask.assigned_specialist.value}"
                ),
                metadata={
                    "subtask_id": str(
                        subtask.id
                    ),
                },
            )

            return {
                "failure_reason": error_message,
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
            failure_reason = (
                output.content
                or "Specialist execution failed."
            )

            await _save_error(
                state,
                failure_reason,
                source=(
                    f"specialist:"
                    f"{subtask.assigned_specialist.value}"
                ),
                metadata={
                    "subtask_id": str(
                        subtask.id
                    ),
                },
            )

            return {
                "failure_reason": failure_reason,
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

        serialized_output = output.model_dump(
            mode="json"
        )

        # ----------------------------------------------------
        # Working memory: save completed output
        # ----------------------------------------------------

        if working_memory is not None:
            await working_memory.add_subtask_output(
                state["task_id"],
                serialized_output,
            )

            # Intermediate result keyed by subtask.
            await working_memory.set_intermediate_result(
                state["task_id"],
                str(subtask.id),
                serialized_output,
            )

        return {
            "specialist_outputs": [
                serialized_output,
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

        Memory is intentionally retained here because the
        task has not completed yet.
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

        try:
            result = await reviewer_agent.run(
                review_input
            )

            review_result = parse_review_result(
                result.metadata
            )

        except Exception as exc:
            await _save_error(
                state,
                str(exc),
                source="reviewer",
            )
            raise

        # Save reviewer decision as an intermediate result.
        if working_memory is not None:
            await working_memory.set_intermediate_result(
                state["task_id"],
                "review",
                review_result.model_dump(
                    mode="json"
                ),
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

        On successful completion:

        1. Persist a useful execution memory to Chroma.
        2. Clear task-scoped working memory.
        """

        outputs = state.get(
            "specialist_outputs",
            [],
        )

        content = "\n\n".join(
            output["content"]
            for output in outputs
        )

        # ----------------------------------------------------
        # Long-term memory
        # ----------------------------------------------------

        if (
            long_term_memory is not None
            and state.get("user_id")
            and content.strip()
        ):
            memory = LongTermMemory(
                id=(
                    f"{state['task_id']}"
                    "-successful-execution"
                ),
                user_id=state["user_id"],
                task_id=state["task_id"],
                memory_type="successful_approach",
                content=(
                    f"Task:\n"
                    f"{state['description']}\n\n"
                    f"Successful result:\n"
                    f"{content}"
                ),
                metadata={
                    "specialist_outputs": len(
                        outputs
                    ),
                    "source": "workflow_synthesis",
                },
                importance_score=0.8,
            )

            await long_term_memory.add(
                memory
            )

        # ----------------------------------------------------
        # Clear short-term working memory
        # ----------------------------------------------------

        await _clear_memory(
            state
        )

        return {
            "final_output": content,
        }

       
    # ========================================================
    # Failed review cleanup
    # ========================================================

    async def review_failed(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Terminal cleanup for a review that exhausted retries.
        """

        await _clear_memory(
            state
        )

        return {
            "error": (
                "Reviewer rejected the result after "
                "the maximum number of retries."
            ),
        }

    # ========================================================
    # Graph nodes
    # ========================================================
    graph.add_node(
        "retrieve_long_term_memory",
        retrieve_long_term_memory,
    )
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
        "review_failed",
        review_failed,
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
        "retrieve_long_term_memory",
    )

    graph.add_edge(
        "retrieve_long_term_memory",
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
            "review_failed": "review_failed",
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

    # Failed review → cleanup → END.
    graph.add_edge(
        "review_failed",
        END,
    )

    # Synthesis → END.
    graph.add_edge(
        "synthesis",
        END,
    )

    return graph.compile()