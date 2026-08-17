export type TraceStatus =
  | "running"
  | "success"
  | "completed"
  | "failure"
  | "failed"
  | "escalated"
  | "warning"
  | "pending"
  | string;

export interface TraceSpan {
  span_id: string;
  parent_span_id: string | null;
  execution_id: string;
  name: string;
  kind: string;
  status: TraceStatus;
  agent: string | null;
  specialist: string | null;
  subtask_id: string | null;
  tool_name: string | null;
  provider: string | null;
  model: string | null;
  confidence: number | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  input: string | null;
  output: string | null;
  prompt: string | null;
  raw_response: string | null;
  error: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cost: number | null;
  attributes: Record<string, unknown>;
}

export interface ExecutionTrace {
  trace_id: string;
  execution_id: string;
  task_id: string | null;
  user_id: string | null;
  status: TraceStatus;
  started_at: string;
  completed_at: string | null;
  wall_clock_ms: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_tool_calls: number;
  total_cost: number;
  attributes: Record<string, unknown>;
  spans: TraceSpan[];
}

export interface ExecutionTraceSpansResponse {
  trace_id: string;
  execution_id: string;
  spans: TraceSpan[];
}

export interface TraceHistoryItem {
  trace_id: string;
  execution_id: string;
  task_id: string | null;
  user_id: string | null;
  status: TraceStatus;
  started_at: string;
  completed_at: string | null;
  wall_clock_ms: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_tool_calls: number;
  total_cost: number;
}

export interface ReplayExecutionRequest {
  source_execution_id: string;
  source_span_id?: string | null;
  input_override?: unknown;
  description_override?: string | null;
}

export interface ReplayExecutionResponse {
  source_execution_id: string;
  source_trace_id: string;
  replay_task_id: string;
  replay_execution_id: string;
  source_span_id: string | null;
  applied_subtask_id: string | null;
  status: string;
  celery_task_id: string | null;
}

export interface AnalyticsOverview {
  execution_count: number;
  completed_count: number;
  escalated_count: number;
  failed_count: number;
  running_count: number;
  escalation_rate: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_tool_calls: number;
  total_cost: number;
  average_cost: number;
  average_wall_clock_ms: number;
  total_human_review_ms: number;
  average_human_review_ms: number;
}

export interface CostByTaskType {
  task_type: string;
  executions: number;
  total_tokens: number;
  total_tool_calls: number;
  total_cost: number;
  average_cost: number;
  total_wall_clock_ms: number;
  average_wall_clock_ms: number;
  total_human_review_ms: number;
  average_human_review_ms: number;
  escalations: number;
  escalation_rate: number;
}

export interface AgentAnalytics {
  agent: string;
  span_count: number;
  total_tokens: number;
  total_cost: number;
  total_duration_ms: number;
  tool_calls: number;
  warnings: number;
  failures: number;
}

export interface ModelAnalytics {
  provider: string;
  model: string;
  agent: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number;
  total_duration_ms: number;
}

export interface ToolAnalytics {
  tool_name: string;
  calls: number;
  total_duration_ms: number;
  average_duration_ms: number;
  total_cost: number;
  failures: number;
  failure_rate: number;
}

export interface EscalationTrendItem {
  execution_id: string;
  started_at: string;
  status: TraceStatus;
  escalated: boolean;
  total_cost: number;
  total_tokens: number;
  wall_clock_ms: number;
}

export interface ObservabilityAnalytics {
  overview: AnalyticsOverview;
  cost_by_task_type: CostByTaskType[];
  agents: AgentAnalytics[];
  models: ModelAnalytics[];
  tools: ToolAnalytics[];
  escalation_trends: EscalationTrendItem[];
}

export interface ReplayComparisonExecution {
  status: TraceStatus;
  wall_clock_ms: number | null;
  total_tokens: number;
  total_tool_calls: number;
  total_cost: number;
}

export interface ReplayComparisonChanges {
  status_changed: boolean;
  latency_delta_ms: number;
  token_delta: number;
  tool_call_delta: number;
  cost_delta: number;
  span_count_delta: number;
}

export type ReplaySpanChange =
  | "added"
  | "removed"
  | "changed"
  | "unchanged"
  | "not_reached";

export interface ReplaySpanFieldDiff {
  original: unknown;
  replay: unknown;
}

export interface ReplaySpanDifference {
  key: string;
  change: ReplaySpanChange;
  original: Record<string, unknown> | null;
  replay: Record<string, unknown> | null;
  fields: string[];
  field_diffs?: Record<string, ReplaySpanFieldDiff>;
}

export interface ReplayComparison {
  original_execution_id: string;
  replay_execution_id: string;
  original: ReplayComparisonExecution;
  replay: ReplayComparisonExecution;
  changes: ReplayComparisonChanges;
  span_differences: ReplaySpanDifference[];
}