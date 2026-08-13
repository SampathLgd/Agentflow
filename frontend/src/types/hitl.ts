export type HumanDecision =
  | "approve"
  | "replan"
  | "reject"
  | "notify"
  | "approve_action"
  | "approve_plan"
  | "take_over";

export type ApprovalLevel =
  | "approve_plan"
  | "approve_action"
  | "take_over"
  | string;

export interface HITLReviewContext {
  original_task: string;
  plan: Record<string, unknown> | null;
  completed_steps: Record<string, unknown>[];
  current_step: Record<string, unknown> | null;
  proposed_action: string;
  reasoning: string | null;
  relevant_memories: unknown[];
  past_decisions: Record<string, unknown>[];
}

export interface HITLReview {
  decision_id: string;
  execution_id: string;
  status: string;
  approval_level: string | null;
  escalation_trigger: string | null;
  escalation_reason: string | null;
  context: HITLReviewContext;
  created_at: string;
}

export interface HumanDecisionResponse {
  id: string;
  execution_id: string;
  status: string;
  decision: HumanDecision | null;
  feedback: string | null;
  decided_by: string | null;
  decided_at: string | null;
  approval_level: string | null;
  escalation_trigger: string | null;
  proposed_action: string | null;
  review_context: HITLReviewContext | null;
  created_at: string;
  resume_task_id?: string | null;
}

export interface HumanDecisionCreate {
  decision: HumanDecision;
  feedback?: string | null;
  decided_by?: string | null;
}

export interface ReviewQueueItem {
  decision_id?: string;
  execution_id: string;
  status?: string;
  approval_level?: string | null;
  escalation_trigger?: string | null;
  escalation_reason?: string | null;
  proposed_action?: string | null;
  created_at?: string;
}

export interface EscalationState {
  execution_id: string;
  status: string;
  escalation_required: boolean;
  human_escalation_required: boolean;
  escalation_reason: string | null;
  specialist_confidence: number | null;
  confidence_threshold: number | null;
  human_decision_status: string;
  human_decision: HumanDecision | null;
  human_feedback: string | null;
  human_decided_at: string | null;
  resume_node: string | null;
  resume_subtask_id: string | null;
}
