import axios from "axios";

import type {
  ExecutionTrace,
  ExecutionTraceSpansResponse,
  ObservabilityAnalytics,
  ReplayComparison,
  ReplayExecutionRequest,
  ReplayExecutionResponse,
  TraceHistoryItem,
} from "../types/trace";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function replayExecution(
  request: ReplayExecutionRequest,
): Promise<ReplayExecutionResponse> {
  const response = await api.post(
    "/api/executions/replay",
    request,
  );

  return response.data;
}

export async function getReplayComparison(
  originalExecutionId: string,
  replayExecutionId: string,
): Promise<ReplayComparison> {
  const response = await api.get(
    "/api/executions/replay/compare",
    {
      params: {
        original_execution_id: originalExecutionId,
        replay_execution_id: replayExecutionId,
      },
    },
  );

  return response.data;
}

export async function getExecutionTraces(
  limit = 25,
): Promise<TraceHistoryItem[]> {
  const response = await api.get(
    "/api/executions/traces",
    {
      params: { limit },
    },
  );

  return response.data;
}

export async function getExecutionTrace(
  executionId: string,
): Promise<ExecutionTrace> {
  const response = await api.get(
    `/api/executions/${executionId}/trace`,
  );

  return response.data;
}

export async function getExecutionTraceSpans(
  executionId: string,
): Promise<ExecutionTraceSpansResponse> {
  const response = await api.get(
    `/api/executions/${executionId}/trace/spans`,
  );

  return response.data;
}

export async function getObservabilityAnalytics(): Promise<ObservabilityAnalytics> {
  const response = await api.get(
    "/api/executions/analytics",
  );

  return response.data;
}