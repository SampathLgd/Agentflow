import { useEffect, useState } from "react";

import {
  getEscalation,
  getReview,
  getReviewQueue,
  resumeHumanDecision,
  submitHumanDecision,
} from "./api/hitl";

import type {
  HITLReview,
  HumanDecision,
  ReviewQueueItem,
} from "./types/hitl";

import "./App.css";

const DECISIONS: {
  value: HumanDecision;
  label: string;
}[] = [
  {
    value: "approve",
    label: "Approve",
  },
  {
    value: "notify",
    label: "Notify",
  },
  {
    value: "approve_action",
    label: "Approve Action",
  },
  {
    value: "approve_plan",
    label: "Approve Plan",
  },
  {
    value: "replan",
    label: "Replan",
  },
  {
    value: "reject",
    label: "Reject",
  },
  {
    value: "take_over",
    label: "Take Over",
  },
];

function formatDate(value?: string | null) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function pretty(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function isReviewContextUnavailable(
  error: unknown,
): boolean {
  if (
    typeof error !== "object" ||
    error === null
  ) {
    return false;
  }

  const candidate = error as {
    response?: {
      status?: number;
    };
  };

  return candidate.response?.status === 409;
}

function App() {
  const [queue, setQueue] = useState<
    ReviewQueueItem[]
  >([]);

  const [
    selectedExecutionId,
    setSelectedExecutionId,
  ] = useState<string | null>(null);

  const [review, setReview] =
    useState<HITLReview | null>(null);

  const [
    loadingQueue,
    setLoadingQueue,
  ] = useState(true);

  const [
    loadingReview,
    setLoadingReview,
  ] = useState(false);

  const [reviewUnavailable, setReviewUnavailable] =
    useState(false);

  const [
    reviewUnavailableMessage,
    setReviewUnavailableMessage,
  ] = useState<string | null>(null);

  const [submitting, setSubmitting] =
    useState(false);

  const [resuming, setResuming] =
    useState(false);

  const [decisionState, setDecisionState] =
    useState<{
      executionId: string;
      decisionId: string;
      decision: HumanDecision;
      resumeTaskId: string | null;
    } | null>(null);

  const [executionStatus, setExecutionStatus] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const [feedback, setFeedback] =
    useState("");

  const [decidedBy, setDecidedBy] =
    useState("");

  async function loadQueue() {
    try {
      setError(null);
      setLoadingQueue(true);

      const items = await getReviewQueue();

      setQueue(items);

      if (items.length === 0) {
        setSelectedExecutionId(null);
        setReview(null);
        setReviewUnavailable(false);
        setReviewUnavailableMessage(null);
        return;
      }

      if (
        !selectedExecutionId ||
        !items.some(
          (item) =>
            item.execution_id ===
            selectedExecutionId,
        )
      ) {
        setSelectedExecutionId(
          items[0].execution_id,
        );
      }
    } catch (err) {
      console.error(err);
      setError(
        "Failed to load the review queue.",
      );
    } finally {
      setLoadingQueue(false);
    }
  }

  async function loadReview(
    executionId: string,
  ) {
    try {
      setError(null);
      setLoadingReview(true);

      setReview(null);
      setReviewUnavailable(false);
      setReviewUnavailableMessage(null);

      const data = await getReview(
        executionId,
      );

      setReview(data);
    } catch (err) {
      console.error(
        "Failed to load review:",
        err,
      );

      setReview(null);

      if (
        isReviewContextUnavailable(err)
      ) {
        setReviewUnavailable(true);

        setReviewUnavailableMessage(
          "This pending review does not contain a review packet. It may be a legacy or incomplete escalation.",
        );

        return;
      }

      setError(
        "Failed to load the review packet.",
      );
    } finally {
      setLoadingReview(false);
    }
  }

  useEffect(() => {
    void loadQueue();
  }, []);

  useEffect(() => {
    if (selectedExecutionId) {
      void loadReview(
        selectedExecutionId,
      );
    } else {
      setReview(null);
      setReviewUnavailable(false);
      setReviewUnavailableMessage(null);
    }
  }, [selectedExecutionId]);

  useEffect(() => {
    if (!decisionState) {
      return;
    }
  
    const executionId = decisionState.executionId;
  
    if (!executionId) {
      return;
    }
  
    let cancelled = false;
  
    async function pollExecution() {
      try {
        const state = await getEscalation(executionId);
  
        if (cancelled) {
          return;
        }
  
        setExecutionStatus(state.status);
  
        if (
          state.status === "completed" ||
          state.status === "rejected" ||
          state.status === "human_takeover" ||
          state.status === "failed"
        ) {
          return;
        }
      } catch (err) {
        console.error(
          "Failed to refresh execution status:",
          err,
        );
      }
    }
  
    void pollExecution();
  
    const interval = window.setInterval(
      () => {
        void pollExecution();
      },
      2000,
    );
  
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [decisionState]);

  async function handleDecision(
    decision: HumanDecision,
  ) {
    if (!review) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const response = await submitHumanDecision(
        review.execution_id,
        decision,
        feedback,
        decidedBy,
      );

      setDecisionState({
        executionId: response.execution_id,
        decisionId: response.id,
        decision,
        resumeTaskId: response.resume_task_id ?? null,
      });

      setExecutionStatus("resuming");
      setFeedback("");
      setReview(null);
      setReviewUnavailable(false);
      setReviewUnavailableMessage(null);
      setSelectedExecutionId(null);

      await loadQueue();
    } catch (err) {
      console.error(err);

      setError(
        `Failed to submit "${decision}" decision.`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResume() {
    if (!decisionState) {
      return;
    }

    try {
      setResuming(true);
      setError(null);

      await resumeHumanDecision(
        decisionState.executionId,
        decisionState.decisionId,
      );

      setExecutionStatus("resuming");
      setDecisionState({
        ...decisionState,
      });
    } catch (err) {
      console.error(err);

      setError(
        "Failed to retry the execution resume.",
      );
    } finally {
      setResuming(false);
    }
  }

  function handleSelectExecution(
    executionId: string,
  ) {
    if (
      executionId ===
      selectedExecutionId
    ) {
      return;
    }

    setReview(null);
    setReviewUnavailable(false);
    setReviewUnavailableMessage(null);
    setError(null);

    setSelectedExecutionId(
      executionId,
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>AgentFlow Reviewer</h1>

          <p>
            Human-in-the-loop approval queue
          </p>
        </div>

        <button
          className="refresh-button"
          onClick={() =>
            void loadQueue()
          }
          disabled={loadingQueue}
        >
          {loadingQueue
            ? "Refreshing..."
            : "Refresh Queue"}
        </button>
      </header>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {decisionState && (
        <DecisionSubmittedPanel
          decisionState={decisionState}
          executionStatus={executionStatus}
          resuming={resuming}
          onRetryResume={handleResume}
          onDismiss={() => {
            setDecisionState(null);
            setExecutionStatus(null);
          }}
        />
      )}

      <main className="workspace">
        <aside className="queue-panel">
          <div className="panel-header">
            <h2>Review Queue</h2>

            <span className="queue-count">
              {queue.length}
            </span>
          </div>

          {loadingQueue ? (
            <div className="empty-state">
              Loading queue...
            </div>
          ) : queue.length === 0 ? (
            <div className="empty-state">
              No pending human reviews.
            </div>
          ) : (
            <div className="queue-list">
              {queue.map((item) => (
                <button
                  key={
                    item.execution_id
                  }
                  className={`queue-item ${
                    selectedExecutionId ===
                    item.execution_id
                      ? "selected"
                      : ""
                  }`}
                  onClick={() =>
                    handleSelectExecution(
                      item.execution_id,
                    )
                  }
                >
                  <div className="queue-item-top">
                    <strong>
                      {item.approval_level ??
                        "Human review"}
                    </strong>

                    <span>
                      {item.status ??
                        "pending"}
                    </span>
                  </div>

                  <div className="queue-execution">
                    {item.execution_id}
                  </div>

                  {item.escalation_trigger && (
                    <div className="queue-trigger">
                      {
                        item.escalation_trigger
                      }
                    </div>
                  )}

                  {item.proposed_action && (
                    <p>
                      {
                        item.proposed_action
                      }
                    </p>
                  )}

                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="review-panel">
          {!selectedExecutionId ? (
            <div className="review-placeholder">
              <h2>
                Select a review
              </h2>

              <p>
                Choose a pending execution
                from the queue.
              </p>
            </div>
          ) : loadingReview ? (
            <div className="review-placeholder">
              <h2>
                Loading review...
              </h2>
            </div>
          ) : reviewUnavailable ? (
            <ReviewUnavailable
              executionId={
                selectedExecutionId
              }
              message={
                reviewUnavailableMessage
              }
              onRefresh={() =>
                void loadReview(
                  selectedExecutionId,
                )
              }
            />
          ) : !review ? (
            <div className="review-placeholder">
              <h2>
                Review unavailable
              </h2>

              <p>
                The review packet could not
                be loaded.
              </p>
            </div>
          ) : (
            <ReviewPanel
              review={review}
              feedback={feedback}
              setFeedback={setFeedback}
              decidedBy={decidedBy}
              setDecidedBy={setDecidedBy}
              submitting={submitting}
              onDecision={
                handleDecision
              }
            />
          )}
        </section>
      </main>
    </div>
  );
}

interface DecisionSubmittedPanelProps {
  decisionState: {
    executionId: string;
    decisionId: string;
    decision: HumanDecision;
    resumeTaskId: string | null;
  };
  executionStatus: string | null;
  resuming: boolean;
  onRetryResume: () => Promise<void>;
  onDismiss: () => void;
}

function DecisionSubmittedPanel({
  decisionState,
  executionStatus,
  resuming,
  onRetryResume,
  onDismiss,
}: DecisionSubmittedPanelProps) {
  const terminal = [
    "completed",
    "rejected",
    "human_takeover",
  ].includes(executionStatus ?? "");

  const retryable = executionStatus === "failed";

  return (
    <section className="decision-submitted-panel">
      <div>
        <div className="eyebrow">Decision submitted</div>
        <h2>Human decision: {decisionState.decision}</h2>
        <p>
          The decision was saved successfully and the resume task was queued.
        </p>
        <div className="metadata-grid">
          <Metadata label="Execution" value={decisionState.executionId} />
          <Metadata label="Status" value={executionStatus ?? "resuming"} />
          <Metadata label="Resume task" value={decisionState.resumeTaskId ?? "—"} />
        </div>
      </div>

      {retryable && (
        <button
          className="resume-button"
          disabled={resuming}
          onClick={() => void onRetryResume()}
        >
          {resuming ? "Retrying..." : "Retry Resume"}
        </button>
      )}

      {terminal && (
        <button
          className="refresh-button"
          onClick={onDismiss}
        >
          Close
        </button>
      )}
    </section>
  );
}

interface ReviewUnavailableProps {
  executionId: string;
  message: string | null;
  onRefresh: () => void;
}

function ReviewUnavailable({
  executionId,
  message,
  onRefresh,
}: ReviewUnavailableProps) {
  return (
    <div className="review-placeholder">
      <div className="review-unavailable-icon">
        !
      </div>

      <h2>
        Review context unavailable
      </h2>

      <p>
        {message ??
          "This pending review does not contain the review context required by the reviewer UI."}
      </p>

      <p className="muted">
        Execution
      </p>

      <code>
        {executionId}
      </code>

      <button
        className="refresh-button"
        onClick={onRefresh}
      >
        Retry Review
      </button>
    </div>
  );
}

interface ReviewPanelProps {
  review: HITLReview;
  feedback: string;
  setFeedback: (
    value: string,
  ) => void;
  decidedBy: string;
  setDecidedBy: (
    value: string,
  ) => void;
  submitting: boolean;
  onDecision: (
    decision: HumanDecision,
  ) => Promise<void>;
}

function ReviewPanel({
  review,
  feedback,
  setFeedback,
  decidedBy,
  setDecidedBy,
  submitting,
  onDecision,
}: ReviewPanelProps) {
  const context = review.context;

  return (
    <div className="review-content">
      <div className="review-header">
        <div>
          <div className="eyebrow">
            Human Review
          </div>

          <h2>
            {context.original_task}
          </h2>
        </div>

        <div className="status-badge">
          {review.status}
        </div>
      </div>

      <div className="metadata-grid">
        <Metadata
          label="Approval level"
          value={
            review.approval_level ??
            "—"
          }
        />

        <Metadata
          label="Escalation trigger"
          value={
            review.escalation_trigger ??
            "—"
          }
        />

        <Metadata
          label="Created"
          value={formatDate(
            review.created_at,
          )}
        />

        <Metadata
          label="Execution"
          value={
            review.execution_id
          }
        />
      </div>

      {review.escalation_reason && (
        <section className="review-section warning">
          <h3>
            Why this was escalated
          </h3>

          <p>
            {review.escalation_reason}
          </p>
        </section>
      )}

      <section className="review-section proposed">
        <h3>
          Proposed action
        </h3>

        <p>
          {context.proposed_action}
        </p>
      </section>

      {context.reasoning && (
        <section className="review-section">
          <h3>
            Agent reasoning
          </h3>

          <p>
            {context.reasoning}
          </p>
        </section>
      )}

      <section className="review-section">
        <h3>Plan</h3>

        <pre>
          {pretty(context.plan)}
        </pre>
      </section>

      <section className="review-section">
        <h3>
          Completed steps
        </h3>

        {context.completed_steps
          .length === 0 ? (
          <p className="muted">
            No completed steps.
          </p>
        ) : (
          <div className="json-list">
            {context.completed_steps.map(
              (step, index) => (
                <pre key={index}>
                  {pretty(step)}
                </pre>
              ),
            )}
          </div>
        )}
      </section>

      <section className="review-section">
        <h3>
          Current step
        </h3>

        <pre>
          {pretty(
            context.current_step,
          )}
        </pre>
      </section>

      <section className="review-section">
        <h3>
          Relevant memories
        </h3>

        {context.relevant_memories
          .length === 0 ? (
          <p className="muted">
            No relevant memories.
          </p>
        ) : (
          <pre>
            {pretty(
              context.relevant_memories,
            )}
          </pre>
        )}
      </section>

      <section className="review-section">
        <h3>
          Past decisions
        </h3>

        {context.past_decisions
          .length === 0 ? (
          <p className="muted">
            No previous decisions.
          </p>
        ) : (
          <pre>
            {pretty(
              context.past_decisions,
            )}
          </pre>
        )}
      </section>

      <section className="decision-section">
        <h3>
          Human decision
        </h3>

        <label>
          Reviewer

          <input
            value={decidedBy}
            onChange={(event) =>
              setDecidedBy(
                event.target.value,
              )
            }
            placeholder="Reviewer name or ID"
          />
        </label>

        <label>
          Feedback

          <textarea
            value={feedback}
            onChange={(event) =>
              setFeedback(
                event.target.value,
              )
            }
            placeholder="Optional instructions or feedback..."
            rows={4}
          />
        </label>

        <div className="decision-grid">
          {DECISIONS.map((item) => (
            <button
              key={item.value}
              className={`decision-button decision-${item.value}`}
              disabled={submitting}
              onClick={() =>
                void onDecision(
                  item.value,
                )
              }
            >
              {submitting
                ? "Submitting..."
                : item.label}
            </button>
          ))}
        </div>

      </section>
    </div>
  );
}

function Metadata({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="metadata">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default App;