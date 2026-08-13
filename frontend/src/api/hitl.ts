import axios from "axios";

import type {
  HITLReview,
  HumanDecision,
  HumanDecisionResponse,
  ReviewQueueItem,
  EscalationState,
} from "../types/hitl";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function getReviewQueue(): Promise<ReviewQueueItem[]> {
  const response = await api.get(
    "/api/executions/reviews/queue",
  );

  const data = response.data;

  if (Array.isArray(data)) {
    return data;
  }

  if (Array.isArray(data?.items)) {
    return data.items;
  }

  if (Array.isArray(data?.reviews)) {
    return data.reviews;
  }

  return [];
}

export async function getEscalation(
  executionId: string,
): Promise<EscalationState> {
  const response = await api.get(
    `/api/executions/${executionId}/escalation`,
  );

  return response.data;
}

export async function getReview(
  executionId: string,
): Promise<HITLReview> {
  const response = await api.get(
    `/api/executions/${executionId}/review`,
  );

  return response.data;
}

export async function submitHumanDecision(
  executionId: string,
  decision: HumanDecision,
  feedback?: string,
  decidedBy?: string,
): Promise<HumanDecisionResponse> {
  const response = await api.post(
    `/api/executions/${executionId}/human-decision`,
    {
      decision,
      feedback: feedback || null,
      decided_by: decidedBy || null,
    },
  );

  return response.data;
}

export async function resumeHumanDecision(
  executionId: string,
  decisionId: string,
): Promise<unknown> {
  const response = await api.post(
    `/api/executions/${executionId}/human-decision/${decisionId}/resume`,
  );

  return response.data;
}
