from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from app.memory.service import MemoryService
from app.agents.analysis.agent import DataAnalysisAgent
from app.agents.coding.agent import CodeExecutionAgent
from app.agents.research.agent import ResearchAgent
from app.agents.reviewer.agent import ReviewerAgent
from app.agents.supervisor.agent import SupervisorAgent
from app.agents.writing.agent import WritingAgent
from app.hitl.approval import (
    ApprovalPolicy,
)
from app.hitl.user_request import UserEscalationDetector
approval_policy = ApprovalPolicy()
user_escalation_detector = UserEscalationDetector()
from app.graph.state import (
    AgentGraphState,
    SpecialistBranchState,
)

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

    # --------------------------------------------------------
    # Specialist failure / retry
    # --------------------------------------------------------

    if failure_reason:
        retry_count = int(
            state.get(
                "retry_count",
                0,
            )
        )

        max_retries = int(
            state.get(
                "max_retries",
                2,
            )
        )

        if retry_count < max_retries:
            return "retry"

        return "failed"

    # --------------------------------------------------------
    # Specialist confidence
    # --------------------------------------------------------

    confidence = float(
        state.get(
            "specialist_confidence",
            1.0,
        )
    )

    confidence_threshold = float(
        state.get(
            "confidence_threshold",
            0.5,
        )
    )

    if confidence < confidence_threshold:
        return "human_escalation"

    # --------------------------------------------------------
    # Dependency-aware progression
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
    """

    review = state.get(
        "review"
    )

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

    # --------------------------------------------------------
    # Low reviewer confidence -> HITL
    # --------------------------------------------------------

    if confidence < escalation_threshold:
        return "escalate"

    # --------------------------------------------------------
    # Approved -> synthesis
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
    # Reviewer rejected -> retry
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

# ============================================================
# Reviewer escalation
# ============================================================

async def escalate(
    state: AgentGraphState,
) -> dict[str, Any]:
    """
    Escalate a low-confidence reviewer result to HITL.

    A human decision is required before execution can continue.
    The escalation is marked as requiring replanning so that an
    approve/replan decision can resume through the appropriate
    workflow path.
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

    threshold = float(
        state.get(
            "confidence_threshold",
            0.5,
        )
    )

    # Preserve an existing escalation reason if one was already
    # supplied by an upstream node.
    existing_reason = state.get(
        "escalation_reason"
    )

    reason = (
        existing_reason
        or (
            "Reviewer confidence "
            f"{confidence:.2f} is below the "
            "configured threshold "
            f"{threshold:.2f}."
        )
    )

    return {
        
        # ----------------------------------------------------
        # Execution / escalation state
        # ----------------------------------------------------

        "execution_status": "escalated",

        "escalation_required": True,

        "human_escalation_required": True,

        # ----------------------------------------------------
        # HITL decision state
        # ----------------------------------------------------

        "human_decision_status": "pending",

        "human_decision": None,

        "human_feedback": None,

        # ----------------------------------------------------
        # Replanning
        # ----------------------------------------------------

        "replan_required": True,

        # ----------------------------------------------------
        # Escalation metadata
        # ----------------------------------------------------

        "escalation_trigger": "reviewer_confidence",

        "approval_level": "approve_action",

        "escalation_reason": reason,

        "proposed_action": (
            "Review the specialist/reviewer result "
            "before continuing execution."
        ),

        "specialist_confidence": confidence,

        "confidence_threshold": threshold,

        # ----------------------------------------------------
        # Resume information
        # ----------------------------------------------------

        "resume_node": "post_review",

        "resume_subtask_id": None,

    }
# ============================================================
# Public HITL state helpers
# ============================================================

GRANULAR_HUMAN_DECISIONS = {
    "approve",
    "replan",
    "reject",
    "notify",
    "approve_action",
    "approve_plan",
    "take_over",
}


def _normalize_human_decision(
    state: AgentGraphState,
) -> str:
    decision = (
        state.get("human_decision") or ""
    ).strip().lower()

    if decision not in GRANULAR_HUMAN_DECISIONS:
        raise ValueError(
            f"Invalid human decision: {decision!r}"
        )

    return decision


def resume_after_human(
    state: AgentGraphState,
) -> dict[str, Any]:
    """
    Normalize state after a persisted human decision.

    Granular HITL decisions:

        approve
            Continue the existing execution.

        replan
            Generate a new execution plan.

        reject
            Terminate the execution.

        notify
            Acknowledge the escalation and continue.

        approve_action
            Approve the currently escalated action/subtask.

        approve_plan
            Approve the current execution plan.

        take_over
            Transfer execution ownership to the human.
    """

    decision = _normalize_human_decision(state)

    if decision == "reject":
        return {
            "execution_status": "rejected",
            "human_escalation_required": False,
            "escalation_required": False,
            "replan_required": False,
            "error": (
                "Execution was rejected by "
                "the human reviewer."
            ),
        }

    if decision == "replan":
        return {
            "execution_status": "running",
            "human_escalation_required": False,
            "escalation_required": False,
            "replan_required": True,
            "review_feedback": (
                state.get("human_feedback")
                or "Human reviewer requested replanning."
            ),
        }

    if decision == "take_over":
        return {
            "execution_status": "human_takeover",
            "human_escalation_required": False,
            "escalation_required": False,
            "replan_required": False,
        }

    # --------------------------------------------------------
    # approve / notify / approve_action / approve_plan
    # --------------------------------------------------------

    return {
        "execution_status": "running",
        "human_escalation_required": False,
        "escalation_required": False,
        "replan_required": False,
    }

def _build_hitl_review_context(
    state: AgentGraphState,
    *,
    proposed_action: str,
    reasoning: str | None = None,
) -> dict[str, Any]:
    plan = state.get("plan")

    completed_ids = {
        str(item)
        for item in state.get(
            "completed_subtasks",
            [],
        )
    }

    completed_steps: list[dict[str, Any]] = []

    for output in state.get(
        "specialist_outputs",
        [],
    ):
        subtask_id = str(
            output.get(
                "subtask_id",
                "",
            )
        )

        if subtask_id in completed_ids:
            completed_steps.append(
                output
            )

    current_subtask = state.get(
        "current_subtask"
    )

    current_step = None

    if current_subtask is not None:
        current_step = (
            current_subtask.model_dump(
                mode="json"
            )
        )

    return {
        "original_task": state.get(
            "description",
            "",
        ),

        "plan": (
            plan.model_dump(
                mode="json"
            )
            if plan is not None
            else None
        ),

        "completed_steps": completed_steps,

        "current_step": current_step,

        "proposed_action": proposed_action,

        "reasoning": reasoning,

        "relevant_memories": state.get(
            "long_term_memories",
            [],
        ),

        "past_decisions": [],
    }

def route_after_human(
    state: AgentGraphState,
) -> str:
    """
    Return the logical route after a human decision.

    This helper is intentionally kept free of LangGraph Send
    objects so it remains easy to unit test.

    The compiled workflow uses _route_after_human() because
    specialist continuation requires dependency-aware Send
    objects.
    """

    decision = _normalize_human_decision(state)

    if decision == "reject":
        return "rejected"

    if decision == "take_over":
        return "human_takeover"

    if decision == "replan":
        return "planning"

    if decision == "approve_plan":
        if state.get("plan") is None:
            return "planning"

        return "specialist"

    if decision in {
        "approve",
        "notify",
        "approve_action",
    }:
        if state.get("plan") is None:
            return "planning"

        resume_node = (
            state.get("resume_node")
            or "post_specialist"
        )

        if resume_node == "post_review":
            return "synthesis"

        return "specialist"

    raise ValueError(
        f"Invalid human decision: {decision!r}"
    )



def _apply_escalation_policy(
    state: AgentGraphState,
    *,
    trigger: str,
    reason: str,
    proposed_action: str,
) -> dict[str, Any]:
    """
    Convert an escalation trigger into the required
    human approval level.
    """

    policy_result = approval_policy.evaluate(
        trigger=trigger,
        reason=reason,
    )

    return {
        "execution_status": "escalated",
        "escalation_required": True,
        "human_escalation_required": True,

        "escalation_trigger": trigger,
        "approval_level": policy_result.approval_level,

        "escalation_reason": (
            policy_result.reason
            or reason
        ),

        "proposed_action": proposed_action,

        "human_decision_status": "pending",
        "human_decision": None,
        "human_feedback": None,
    }

def check_user_escalation(
    state: AgentGraphState,
) -> dict[str, Any]:
    """
    Detect an explicit request for human intervention
    before normal workflow execution begins.

    This is deterministic and must happen before planning
    or specialist execution.
    """

    result = user_escalation_detector.detect(
        state.get(
            "description",
            "",
        )
    )

    if not result.escalation_required:
        return {
            "escalation_required": False,
            "human_escalation_required": False,
        }

    policy_result = _apply_escalation_policy(
        state,
        trigger="user_request",
        reason=(
            result.reason
            or "The user explicitly requested "
            "human intervention."
        ),
        proposed_action=(
            "Transfer execution to human control "
            "before continuing."
        ),
    )

    return {
        **policy_result,

        "execution_status": "escalated",

        "escalation_required": True,

        "human_escalation_required": True,

        "human_decision_status": "pending",

        "human_decision": None,

        "human_feedback": None,

        "resume_node": "planning",

        "resume_subtask_id": None,

        "replan_required": False,
    }
def user_request_escalation(
    state: AgentGraphState,
) -> dict[str, Any]:
    """
    Preserve an explicit user-request escalation exactly as
    detected. This node must not rewrite the escalation trigger.
    """

    return {
        "execution_status": "escalated",
        "escalation_required": True,
        "human_escalation_required": True,

        "escalation_trigger": "user_request",

        "approval_level": "take_over",

        "escalation_reason": (
            state.get("escalation_reason")
            or "The user explicitly requested human intervention."
        ),

        "proposed_action": (
            "Transfer execution to human control "
            "before continuing."
        ),

        "human_decision_status": "pending",
        "human_decision": None,
        "human_feedback": None,

        "resume_node": "planning",
        "resume_subtask_id": None,

        "replan_required": False,
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
    memory_service: MemoryService | None = None,
):
    """
    Build the AgentFlow orchestration graph.

    Normal execution:

        START
          ↓
        retrieve_long_term_memory
          ↓
        planning
          ↓
        dependency-aware dispatch
          ↓
        specialist
        ↙   ↓   ↘
      retry dispatch review
                    ↙  ↓  ↘
                 retry  synthesis  HITL
                          ↓          ↓
                         END        END


    HITL resume:

        START
          ↓
        resume_after_human
          ↓
       ┌──┴──────────────┐
       │                 │
     reject            replan
       ↓                 ↓
      END             planning
                         ↓
                      dispatch


    HITL approve:

        START
          ↓
        resume_after_human
          ↓
        if work remains
          ↓
        dependency-aware dispatch
          ↓
        specialist


        OR if all specialists complete:

        resume_after_human
          ↓
        review / synthesis
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
        """

        if working_memory is None:
            return

        await working_memory.clear(
            state["task_id"]
        )
    # ========================================================
    # Explicit user-request escalation
    # ========================================================

    
    # ========================================================
    # Long-term memory retrieval
    # ========================================================

    async def retrieve_long_term_memory(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Retrieve relevant long-term memories for the
        current user.

        MemoryService owns retrieval policy and filtering.
        """

        if memory_service is not None:
            memories = (
                await memory_service.retrieve_for_workflow(
                    user_id=state.get(
                        "user_id",
                        "",
                    ),
                    query=state["description"],
                )
            )

            return {
                "long_term_memories": memories,
            }

        # Backward-compatible fallback.
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

        return {
            "long_term_memories": [
                {
                    "memory": result.memory.model_dump(
                        mode="json"
                    ),
                    "distance": result.distance,
                }
                for result in results
            ],
        }
    # ========================================================
    # Planning
    # ========================================================

    async def planning(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Ask the supervisor to create the execution plan.

        A replanning decision intentionally starts a new plan
        and resets execution-progress state.
        """

        agent_input = AgentInput(
            task_id=state["task_id"],
            description=state["description"],
            context={
                "long_term_memories": state.get(
                    "long_term_memories",
                    [],
                ),

                "human_feedback": state.get(
                    "human_feedback",
                    "",
                ),

                "replan_required": state.get(
                    "replan_required",
                    False,
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

            "retry_count": 0,

            "failure_reason": "",

            "retry_feedback": "",

            "review_retry_count": 0,

            "review_feedback": "",

            "review": None,

            "specialist_confidence": 1.0,

            "confidence_threshold": float(
                state.get(
                    "confidence_threshold",
                    0.5,
                )
            ),

            "human_escalation_required": False,

            "escalation_required": False,

            "escalation_reason": "",

            "replan_required": False,

            "resume_node": "",

            "resume_subtask_id": None,

            "human_decision_status": "",

            "human_decision": None,

            "human_feedback": None,

            "resume_from_human": False,

            "execution_status": "running",

            "error": "",
        }

    # ========================================================
    # Dependency-aware dispatch
    # ========================================================

    def dispatch(
        state: AgentGraphState,
    ) -> list[Send]:
        """
        Dispatch all dependency-ready subtasks.

        Every specialist Send gets its own explicit
        current_subtask.

        This is important for both normal execution and HITL
        resume. The specialist node never assumes that
        current_subtask exists in shared graph state.
        """

        plan = state.get(
            "plan"
        )

        if plan is None:
            raise RuntimeError(
                "Cannot dispatch specialists without an execution plan."
            )

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
            branch_state: SpecialistBranchState = {
                "task_id": state["task_id"],

                "user_id": state.get(
                    "user_id",
                    "",
                ),

                "description": state["description"],

                "plan": plan,

                "current_subtask": subtask,

                "specialist_outputs": state.get(
                    "specialist_outputs",
                    [],
                ),

                "long_term_memories": state.get(
                    "long_term_memories",
                    [],
                ),

                "retry_count": int(
                    state.get(
                        "retry_count",
                        0,
                    )
                ),

                "max_retries": int(
                    state.get(
                        "max_retries",
                        2,
                    )
                ),

                "failure_reason": state.get(
                    "failure_reason",
                    "",
                ),

                "retry_feedback": state.get(
                    "retry_feedback",
                    "",
                ),

                "review_feedback": state.get(
                    "review_feedback",
                    "",
                ),

                "confidence_threshold": float(
                    state.get(
                        "confidence_threshold",
                        0.5,
                    )
                ),
            }

            sends.append(
                Send(
                    "specialist",
                    branch_state,
                )
            )

        if not sends:
            raise RuntimeError(
                "No dependency-ready subtasks are available for dispatch."
            )

        return sends

    # ========================================================
    # Specialist execution
    # ========================================================

    async def specialist(
        state: SpecialistBranchState,
    ) -> dict[str, Any]:
        """
        Execute one specialist subtask.

        current_subtask MUST come from the branch created by
        dispatch().
        """

        subtask = state.get(
            "current_subtask"
        )

        if subtask is None:
            raise RuntimeError(
                "Specialist branch received no current_subtask."
            )

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
                state,  # type: ignore[arg-type]
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
                "current_subtask": subtask,

                "failure_reason": error_message,

                "retry_count": (
                    int(
                        state.get(
                            "retry_count",
                            0,
                        )
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
                state,  # type: ignore[arg-type]
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
                "current_subtask": subtask,

                "failure_reason": failure_reason,

                "retry_count": (
                    int(
                        state.get(
                            "retry_count",
                            0,
                        )
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

        serialized_output = {
            **output.model_dump(
                mode="json"
            ),

            "subtask_id": str(
                subtask.id
            ),

            "subtask_description": (
                subtask.description
            ),

            "assigned_specialist": (
                subtask.assigned_specialist.value
            ),
        }

        # ----------------------------------------------------
        # Working memory
        # ----------------------------------------------------

        if working_memory is not None:
            await working_memory.add_subtask_output(
                state["task_id"],
                serialized_output,
            )

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

        subtask = state.get(
            "current_subtask"
        )

        if subtask is None:
            raise RuntimeError(
                "Cannot retry specialist because "
                "current_subtask is missing."
            )

        failure_reason = state.get(
            "failure_reason",
            "Unknown specialist failure.",
        )

        retry_count = int(
            state.get(
                "retry_count",
                0,
            )
        )

        return {
            "current_subtask": subtask,

            "retry_feedback": (
                "Previous specialist attempt failed.\n"
                f"Failure reason: {failure_reason}\n"
                f"Retry attempt: {retry_count}\n\n"
                "Use a different approach and avoid "
                "repeating the same failed strategy."
            ),

            "failure_reason": "",

            "specialist_confidence": 1.0,
        }

    # ========================================================
    # Human escalation
    # ========================================================

    def human_escalation(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        current_subtask = state.get(
            "current_subtask"
        )

        confidence = float(
            state.get(
                "specialist_confidence",
                0.0,
            )
        )

        threshold = float(
            state.get(
                "confidence_threshold",
                0.5,
            )
        )

        reason = (
            "Specialist confidence "
            f"{confidence:.2f} is below the "
            "configured threshold "
            f"{threshold:.2f}."
        )

        proposed_action = (
            current_subtask.description
            if current_subtask is not None
            else "Continue the escalated specialist task."
        )

        result = _apply_escalation_policy(
            state,
            trigger="specialist_failure",
            reason=reason,
            proposed_action=proposed_action,
        )

        return {
            **result,

            "specialist_confidence": confidence,
            "confidence_threshold": threshold,

            "resume_node": "post_specialist",

            "resume_subtask_id": (
                str(current_subtask.id)
                if current_subtask is not None
                else None
            ),

            "replan_required": False,
        }
    # ========================================================
    # Reviewer escalation
    # ========================================================

    async def escalate(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        review = state.get("review")

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

        threshold = float(
            state.get(
                "confidence_threshold",
                0.5,
            )
        )

        reason = (
            "Reviewer confidence "
            f"{confidence:.2f} is below the "
            "configured threshold "
            f"{threshold:.2f}."
        )

        proposed_action = (
            "Human reviewer must decide whether "
            "the reviewed result may proceed."
        )

        result = _apply_escalation_policy(
            state,
            trigger="reviewer_low_confidence",
            reason=reason,
            proposed_action=proposed_action,
        )

        return {
            **result,

            "specialist_confidence": confidence,
            "confidence_threshold": threshold,

            "resume_node": "post_review",
            "resume_subtask_id": None,

            "replan_required": False,
        }

    # ========================================================
    # Resume after human
    # ========================================================

    def _resume_after_human(
        state: AgentGraphState,
    ) -> dict[str, Any]:
        """
        Normalize the state after a persisted human decision.

        Routing is handled separately by _route_after_human().
        """

        decision = (
            state.get(
                "human_decision"
            )
            or ""
        ).strip().lower()

        if decision == "reject":
            return {
                "execution_status": "rejected",

                "human_escalation_required": False,

                "escalation_required": False,

                "replan_required": False,

                "error": (
                    "Execution was rejected by the human reviewer."
                ),
            }

        if decision == "replan":
            return {
                "execution_status": "running",

                "human_escalation_required": False,

                "escalation_required": False,

                "replan_required": True,

                "review_feedback": (
                    state.get(
                        "human_feedback"
                    )
                    or "Human reviewer requested replanning."
                ),
            }

        if decision == "take_over":
            return {
                "execution_status": "human_takeover",

                "human_escalation_required": False,

                "escalation_required": False,

                "replan_required": False,
            }

        if decision in {
            "approve",
            "notify",
            "approve_action",
            "approve_plan",
        }:
            return {
                "execution_status": "running",

                "human_escalation_required": False,

                "escalation_required": False,

                "replan_required": False,
            }

        raise ValueError(
            f"Cannot resume workflow with invalid human decision: "
            f"{decision!r}"
        )
    # ========================================================
    # HITL resume routing
    # ========================================================

    def _route_after_human(
        state: AgentGraphState,
    ):
        """
        Route execution after a persisted human decision.

        Decisions:

            reject
                END

            take_over
                END with human_takeover status

            replan
                planning

            approve_plan
                Continue the existing plan.

            approve_action
                Continue the existing plan from the escalated
                subtask.

            approve / notify
                Continue normal execution.
        """

        decision = _normalize_human_decision(state)

        # ========================================================
        # Reject
        # ========================================================

        if decision == "reject":
            return "rejected"

        # ========================================================
        # Human takeover
        # ========================================================

        if decision == "take_over":
            return "human_takeover"

        # ========================================================
        # Replan
        # ========================================================

        if decision == "replan":
            return "planning"

        # ========================================================
        # Decisions that continue the current plan
        # ========================================================

        if decision in {
            "approve",
            "notify",
            "approve_action",
            "approve_plan",
        }:

            plan = state.get("plan")

            if plan is None:
                return "planning"

            completed_ids = {
                str(item)
                for item in state.get(
                    "completed_subtasks",
                    [],
                )
            }

            # ----------------------------------------------------
            # If all specialist work is complete, continue to
            # review/synthesis.
            # ----------------------------------------------------

            if _all_subtasks_completed(
                plan,
                completed_ids,
            ):
                if state.get("review") is not None:
                    return "synthesis"

                return "review"

            # ----------------------------------------------------
            # Continue unfinished work.
            #
            # dispatch() creates Send("specialist", ...)
            # and explicitly injects current_subtask.
            # ----------------------------------------------------

            sends = dispatch(state)

            if not sends:
                raise RuntimeError(
                    "Human decision was received, but no "
                    "dependency-ready subtasks are available."
                )

            return sends

        raise ValueError(
            f"Invalid human decision: {decision!r}"
        )
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

        retry_count = int(
            state.get(
                "review_retry_count",
                0,
            )
        )

        current_subtask = state.get(
            "current_subtask"
        )

        # A reviewer rejection happens after the specialist fan-out
        # has normally completed, so current_subtask may no longer
        # be present in the merged graph state. The specialist node
        # requires an explicit branch subtask; fall back to the first
        # plan subtask so the retry can never enter specialist with a
        # missing current_subtask.
        if current_subtask is None:
            plan = state.get("plan")

            if plan is not None and plan.subtasks:
                current_subtask = plan.subtasks[0]

        result: dict[str, Any] = {
            "review_retry_count": (
                retry_count + 1
            ),

            "retry_feedback": (
                "The reviewer rejected the previous output.\n\n"
                f"Reviewer feedback:\n{review_feedback}\n\n"
                "Revise the approach and produce a better result."
            ),

            "failure_reason": "",

            "specialist_confidence": 1.0,
        }

        if current_subtask is not None:
            result["current_subtask"] = current_subtask

        return result

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
            output.get(
                "content",
                "",
            )
            for output in outputs
        )

        # ----------------------------------------------------
        # Long-term memory
        # ----------------------------------------------------

        if (
            long_term_memory is not None
            and state.get(
                "user_id"
            )
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
        # Clear working memory
        # ----------------------------------------------------

        await _clear_memory(
            state
        )

        return {
            "final_output": content,

            "execution_status": "completed",

            "human_escalation_required": False,

            "escalation_required": False,

            "human_decision_status": "completed",
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

            "execution_status": "failed",

            "human_escalation_required": False,

            "escalation_required": False,
        }

    # ========================================================
    # Graph nodes
    # ========================================================
    graph.add_node(
        "check_user_escalation",
        check_user_escalation,
    )
    graph.add_node(
        "user_request_escalation",
        user_request_escalation,
    )
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
        "resume_after_human",
        _resume_after_human,
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
    # Initial entry routing
    # ========================================================

    def route_initial_entry(
        state: AgentGraphState,
    ) -> str:
        """
        Choose whether this is a HITL resume or a fresh execution.
        """

        if state.get(
            "resume_from_human",
            False,
        ):
            return "resume_after_human"

        return "check_user_escalation"
 

    
    def route_after_user_escalation(
        state: AgentGraphState,
    ) -> str:
        """
        Explicit user escalation is already a complete HITL
        boundary. Do not send it through specialist escalation,
        because that would overwrite the original trigger.
        """

        if state.get(
            "human_escalation_required",
            False,
        ):
            return "human_escalation"

        return "retrieve_long_term_memory"

    # ========================================================
    # START
    # ========================================================

    graph.add_conditional_edges(
        START,
        route_initial_entry,
        {
            "check_user_escalation": (
                "check_user_escalation"
            ),

            "resume_after_human": (
                "resume_after_human"
            ),
        },
    )

    graph.add_conditional_edges(
    "check_user_escalation",
    route_after_user_escalation,
    {
        "human_escalation": "user_request_escalation",
        "retrieve_long_term_memory": (
            "retrieve_long_term_memory"
        ),
    },
)
    # ========================================================
    # Long-term memory → planning
    # ========================================================

    graph.add_edge(
        "retrieve_long_term_memory",
        "planning",
    )

    # ========================================================
    # Planning → dependency-aware dispatch
    # ========================================================

    graph.add_conditional_edges(
        "planning",
        dispatch,
    )

    # ========================================================
    # Specialist → retry / dispatch / review / HITL
    # ========================================================

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

    # ========================================================
    # Specialist retry → specialist
    # ========================================================

    graph.add_edge(
        "retry_specialist",
        "specialist",
    )

    # ========================================================
    # Specialist HITL boundary → END
    # ========================================================
    graph.add_edge(
        "user_request_escalation",
        END,
    )
    graph.add_edge(
        "human_escalation",
        END,
    )

    # ========================================================
    # Reviewer → synthesis / retry / failed / HITL
    # ========================================================

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

    # ========================================================
    # Reviewer HITL boundary → END
    # ========================================================

    graph.add_edge(
        "escalate",
        END,
    )

    # ========================================================
    # Reviewer retry → specialist
    #
    # IMPORTANT:
    # retry_after_review retains current_subtask when one
    # exists, so the specialist node receives its context.
    # ========================================================

    graph.add_edge(
        "retry_after_review",
        "specialist",
    )

    # ========================================================
    # Failed review → END
    # ========================================================

    graph.add_edge(
        "review_failed",
        END,
    )

    # ========================================================
    # Synthesis → END
    # ========================================================

    graph.add_edge(
        "synthesis",
        END,
    )

    # ========================================================
    # HITL resume routing
    #
    # IMPORTANT:
    #
    # route_after_human() may return:
    #
    #   "planning"
    #   "review"
    #   "synthesis"
    #   "rejected"
    #
    # OR a list[Send] from dispatch().
    #
    # The Send objects are returned directly so resumed specialist
    # branches always contain current_subtask.
    # ========================================================

    graph.add_conditional_edges(
        "resume_after_human",
        _route_after_human,
        {
            "planning": "planning",

            "review": "review",

            "synthesis": "synthesis",

            "rejected": END,

            "human_takeover": END,
        },
    )

    return graph.compile()