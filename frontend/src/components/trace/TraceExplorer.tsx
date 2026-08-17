import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getExecutionTrace,
  getExecutionTraces,
  getObservabilityAnalytics,
  getReplayComparison,
  replayExecution,
} from "../../api/trace";

import type {
  ExecutionTrace,
  ObservabilityAnalytics,
  ReplayComparison,
  ReplayExecutionResponse,
  TraceHistoryItem,
  TraceSpan,
} from "../../types/trace";

interface TraceExplorerProps {
  initialExecutionId?: string | null;
}

interface TraceNodeProps {
  span: TraceSpan;
  childrenMap: Map<string | null, TraceSpan[]>;
  depth: number;
  selectedSpanId: string | null;
  onSelect: (span: TraceSpan) => void;
}

function formatDuration(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "—";
  }

  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }

  return `${(value / 1000).toFixed(2)} s`;
}

function formatCost(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "—";
  }

  return `$${value.toFixed(4)}`;
}

function formatTokens(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "—";
  }

  return value.toLocaleString();
}

function formatDate(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function shortId(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function pretty(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function attributeValue(
  attributes:
    | Record<string, unknown>
    | null
    | undefined,
  key: string,
): string | null {
  if (!attributes) {
    return null;
  }

  const value = attributes[key];

  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === "string") {
    return value;
  }

  return String(value);
}

function statusClass(
  status: string,
): string {
  const normalized = status.toLowerCase();

  if (
    normalized === "success" ||
    normalized === "completed"
  ) {
    return "trace-status-success";
  }

  if (
    normalized === "failure" ||
    normalized === "failed"
  ) {
    return "trace-status-failure";
  }

  if (
    normalized === "escalated" ||
    normalized === "human_review"
  ) {
    return "trace-status-escalated";
  }

  if (
    normalized === "warning" ||
    normalized === "pending"
  ) {
    return "trace-status-warning";
  }

  return "trace-status-running";
}

function statusLabel(
  status: string,
): string {
  return status.replace(/_/g, " ");
}

function buildChildrenMap(
  spans: TraceSpan[],
): Map<string | null, TraceSpan[]> {
  const map = new Map<
    string | null,
    TraceSpan[]
  >();

  for (const span of spans) {
    const parentId =
      span.parent_span_id;

    const children =
      map.get(parentId) ?? [];

    children.push(span);

    map.set(
      parentId,
      children,
    );
  }

  return map;
}

function isReplayableSpan(
  span: TraceSpan,
): boolean {
  const kind = (span.kind ?? "").toLowerCase();
  const name = (span.name ?? "").toLowerCase();

  return Boolean(
    span.subtask_id &&
      (kind === "specialist" ||
        name === "specialist" ||
        name.startsWith("specialist")),
  );
}

function spanIcon(
  span: TraceSpan,
): string {
  const value =
    `${span.kind} ${span.name}`.toLowerCase();

  if (value.includes("human")) {
    return "H";
  }

  if (value.includes("tool")) {
    return "T";
  }

  if (value.includes("memory")) {
    return "M";
  }

  if (
    value.includes("llm") ||
    value.includes("model")
  ) {
    return "AI";
  }

  if (
    value.includes("specialist") ||
    value.includes("agent")
  ) {
    return "A";
  }

  return "W";
}

function TraceNode({
  span,
  childrenMap,
  depth,
  selectedSpanId,
  onSelect,
}: TraceNodeProps) {
  const children =
    childrenMap.get(span.span_id) ?? [];

  return (
    <div className="trace-tree-branch">
      <button
        type="button"
        className={`trace-node ${
          selectedSpanId === span.span_id
            ? "selected"
            : ""
        }`}
        style={{
          marginLeft: `${depth * 22}px`,
        }}
        onClick={() => onSelect(span)}
      >
        <span
          className={`trace-node-rail ${statusClass(
            span.status,
          )}`}
        />

        <span className="trace-node-icon">
          {spanIcon(span)}
        </span>

        <span className="trace-node-main">
          <strong>
            {span.name}
          </strong>

          <span className="trace-node-meta">
            {span.agent ??
              span.specialist ??
              span.kind}

            {span.tool_name
              ? ` · ${span.tool_name}`
              : ""}

            {span.model
              ? ` · ${span.model}`
              : ""}
          </span>
        </span>

        <span className="trace-node-status-text">
          {statusLabel(span.status)}
        </span>

        <span className="trace-node-metrics">
          {formatDuration(
            span.duration_ms,
          )}

          {span.total_tokens !== null &&
            span.total_tokens !==
              undefined && (
              <span>
                {formatTokens(
                  span.total_tokens,
                )}{" "}
                tok
              </span>
            )}

          {span.cost !== null &&
            span.cost !== undefined && (
              <span>
                {formatCost(span.cost)}
              </span>
            )}
        </span>
      </button>

      {children.length > 0 && (
        <div className="trace-tree-children">
          {children.map((child) => (
            <TraceNode
              key={child.span_id}
              span={child}
              childrenMap={childrenMap}
              depth={depth + 1}
              selectedSpanId={
                selectedSpanId
              }
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TraceExplorer({
  initialExecutionId = null,
}: TraceExplorerProps) {
  const [
    executionId,
    setExecutionId,
  ] = useState(
    initialExecutionId ?? "",
  );

  const [
    history,
    setHistory,
  ] = useState<TraceHistoryItem[]>([]);

  const [
    trace,
    setTrace,
  ] = useState<ExecutionTrace | null>(
    null,
  );

  const [
    selectedSpan,
    setSelectedSpan,
  ] = useState<TraceSpan | null>(
    null,
  );

  const [
    loadingHistory,
    setLoadingHistory,
  ] = useState(true);

  const [
    loadingTrace,
    setLoadingTrace,
  ] = useState(false);

  const [
    loadingAnalytics,
    setLoadingAnalytics,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    analytics,
    setAnalytics,
  ] = useState<
    ObservabilityAnalytics | null
  >(null);

  const [
    originalExecutionId,
    setOriginalExecutionId,
  ] = useState(
    initialExecutionId ?? "",
  );

  const [
    replayExecutionId,
    setReplayExecutionId,
  ] = useState("");

  const [
    comparison,
    setComparison,
  ] = useState<
    ReplayComparison | null
  >(null);

  const [
    loadingComparison,
    setLoadingComparison,
  ] = useState(false);

  const [
    loadingReplay,
    setLoadingReplay,
  ] = useState(false);

  const [
    replaySourceSpan,
    setReplaySourceSpan,
  ] = useState<TraceSpan | null>(null);

  const [
    replayDescription,
    setReplayDescription,
  ] = useState("");

  const [
    replayInputOverride,
    setReplayInputOverride,
  ] = useState("");

  const [
    replayResult,
    setReplayResult,
  ] = useState<ReplayExecutionResponse | null>(null);

  async function runReplay() {
    const originalId = originalExecutionId.trim();

    if (!originalId) {
      setError("Select an original execution first.");
      return;
    }

    if (!replaySourceSpan) {
      setError("Select a specialist span to replay first.");
      return;
    }

    if (!isReplayableSpan(replaySourceSpan)) {
      setError(
        "Only persisted specialist spans with a subtask can be replayed.",
      );
      return;
    }

    let inputOverride: unknown = undefined;
    const rawOverride = replayInputOverride.trim();

    if (rawOverride) {
      try {
        inputOverride = JSON.parse(rawOverride);
      } catch {
        inputOverride = rawOverride;
      }
    }

    try {
      setLoadingReplay(true);
      setError(null);
      setReplayResult(null);
      setComparison(null);

      const result = await replayExecution({
        source_execution_id: originalId,
        source_span_id: replaySourceSpan.span_id,
        input_override: inputOverride,
        description_override:
          replayDescription.trim() || undefined,
      });

      setReplayResult(result);
      setReplayExecutionId(result.replay_execution_id);

      /*
       * The replay execution is created immediately, but its trace
       * may not be persisted until the Celery execution finishes.
       * Keep the replay ID available for comparison even when the
       * trace is not ready yet.
       */
    } catch (err) {
      console.error("Failed to replay execution:", err);
      setReplayResult(null);
      setError(
        "Replay could not be started. Check the selected execution/span and backend replay endpoint.",
      );
    } finally {
      setLoadingReplay(false);
    }
  }

  async function waitForReplayTrace(
    replayId: string,
    attempts = 12,
  ): Promise<boolean> {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        await getExecutionTrace(replayId);
        return true;
      } catch {
        await new Promise((resolve) =>
          window.setTimeout(resolve, 1000),
        );
      }
    }

    return false;
  }


  async function loadComparison() {
    const originalId =
      originalExecutionId.trim();

    const replayId =
      replayExecutionId.trim();

    if (!originalId) {
      setError(
        "Select an original execution first.",
      );
      return;
    }

    if (!replayId) {
      setError(
        "Enter or select a replay execution ID.",
      );
      return;
    }

    if (originalId === replayId) {
      setError(
        "Original and replay executions must be different.",
      );
      return;
    }

    try {
      setLoadingComparison(true);
      setError(null);

      const ready =
        await waitForReplayTrace(replayId);

      if (!ready) {
        setError(
          "Replay was created, but its persisted trace is not ready yet. Try Compare again after the worker finishes.",
        );
        setComparison(null);
        return;
      }

      const data =
        await getReplayComparison(
          originalId,
          replayId,
        );

      setComparison(data);
    } catch (err) {
      console.error(
        "Failed to compare replay:",
        err,
      );

      setComparison(null);

      setError(
        "Replay comparison could not be loaded. Make sure both executions have persisted traces.",
      );
    } finally {
      setLoadingComparison(false);
    }
  }

  async function loadAnalytics() {
    try {
      setLoadingAnalytics(true);

      const data =
        await getObservabilityAnalytics();

      setAnalytics(data);
    } catch (err) {
      console.error(
        "Failed to load observability analytics:",
        err,
      );
    } finally {
      setLoadingAnalytics(false);
    }
  }

  async function loadHistory() {
    try {
      setLoadingHistory(true);

      const items =
        await getExecutionTraces(25);

      setHistory(items);

      if (
        !executionId &&
        initialExecutionId
      ) {
        setExecutionId(
          initialExecutionId,
        );
      }
    } catch (err) {
      console.error(
        "Failed to load execution history:",
        err,
      );

      setError(
        "Execution history could not be loaded.",
      );
    } finally {
      setLoadingHistory(false);
    }
  }

  async function loadTrace(
    requestedId?: string,
  ) {
    const id = (
      requestedId ??
      executionId
    ).trim();

    if (!id) {
      setError(
        "Select or enter an execution ID.",
      );
      return;
    }

    try {
      setLoadingTrace(true);
      setError(null);
      setSelectedSpan(null);
      setExecutionId(id);
      setOriginalExecutionId(id);

      const data =
        await getExecutionTrace(id);

      setTrace(data);

      /*
       * The selected execution changed.
       * Replay/comparison state belongs to the old original.
       */
      setComparison(null);
      setReplayResult(null);
      setReplayExecutionId("");
      setReplaySourceSpan(null);
      setReplayDescription("");
      setReplayInputOverride("");
    } catch (err) {
      console.error(
        "Failed to load trace:",
        err,
      );

      setTrace(null);
      setComparison(null);

      setError(
        "Trace could not be loaded. Check the execution ID and make sure a persisted trace exists.",
      );
    } finally {
      setLoadingTrace(false);
    }
  }

  async function refreshAll() {
    await Promise.all([
      loadHistory(),
      loadAnalytics(),
    ]);

    if (executionId.trim()) {
      await loadTrace(
        executionId,
      );
    }
  }

  useEffect(() => {
    void loadHistory();
    void loadAnalytics();
  }, []);

  useEffect(() => {
    if (
      initialExecutionId &&
      initialExecutionId !==
        executionId
    ) {
      setExecutionId(
        initialExecutionId,
      );

      void loadTrace(
        initialExecutionId,
      );
    }
  }, [initialExecutionId]);

  const childrenMap = useMemo(
    () =>
      trace
        ? buildChildrenMap(
            trace.spans,
          )
        : new Map<
            string | null,
            TraceSpan[]
          >(),
    [trace],
  );

  const roots =
    childrenMap.get(null) ?? [];

  const replayableSpans = useMemo(
    () =>
      trace
        ? trace.spans.filter(isReplayableSpan)
        : [],
    [trace],
  );

  return (
    <div className="trace-explorer">
      <header className="trace-page-header">
        <div className="trace-page-heading">
          <div className="trace-page-icon">
            ◈
          </div>

          <div>
            <div className="eyebrow">
              Observability
            </div>

            <h1>
              Execution observability
            </h1>

            <p>
              Monitor workflow performance,
              agent behavior, tool usage,
              cost, and human escalation.
            </p>
          </div>
        </div>

        <div className="trace-toolbar-actions">
          <button
            type="button"
            className="refresh-button"
            disabled={
              loadingHistory ||
              loadingAnalytics ||
              loadingTrace
            }
            onClick={() =>
              void refreshAll()
            }
          >
            {loadingHistory ||
            loadingAnalytics ||
            loadingTrace
              ? "Refreshing..."
              : "Refresh data"}
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner trace-error">
          <strong>
            Unable to load trace
          </strong>

          <span>{error}</span>
        </div>
      )}

      {analytics && (
        <ObservabilityAnalyticsPanel
          analytics={analytics}
        />
      )}

      <section className="trace-selector-card">
        <div>
          <div className="trace-section-kicker">
            Trace explorer
          </div>

          <h2>
            Inspect an execution
          </h2>

          <p>
            Select a recent execution or
            paste an execution UUID.
          </p>
        </div>

        <div className="trace-load-control">
          <select
            value={executionId}
            onChange={(event) => {
              const id =
                event.target.value;

              setExecutionId(id);

              if (id) {
                void loadTrace(id);
              }
            }}
            disabled={loadingHistory}
          >
            <option value="">
              {loadingHistory
                ? "Loading executions..."
                : "Select execution"}
            </option>

            {history.map((item) => (
              <option
                key={
                  item.execution_id
                }
                value={
                  item.execution_id
                }
              >
                {item.status} ·{" "}
                {formatDate(
                  item.started_at,
                )}{" "}
                ·{" "}
                {shortId(
                  item.execution_id,
                )}
              </option>
            ))}
          </select>

          <input
            value={executionId}
            onChange={(event) =>
              setExecutionId(
                event.target.value,
              )
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void loadTrace();
              }
            }}
            placeholder="Execution UUID"
          />

          <button
            type="button"
            className="trace-load-button"
            disabled={
              loadingTrace ||
              !executionId.trim()
            }
            onClick={() =>
              void loadTrace()
            }
          >
            {loadingTrace
              ? "Loading..."
              : "Inspect"}
          </button>
        </div>
      </section>

      {/* =====================================================
          Replay
          ===================================================== */}

      {trace && (
        <section className="replay-compare-card">
          <div>
            <div className="trace-section-kicker">
              Replay
            </div>

            <h2>
              Replay a selected span
            </h2>

            <p>
              Select a persisted span, optionally override its
              input or description, then create a new execution.
            </p>
          </div>

          <div className="replay-compare-control">
            <select
              value={replaySourceSpan?.span_id ?? ""}
              onChange={(event) => {
                const span =
                  replayableSpans.find(
                    (item) =>
                      item.span_id === event.target.value,
                  ) ?? null;

                setReplaySourceSpan(span);
                setError(null);

                if (span) {
                  setReplayDescription(
                    span.attributes?.description
                      ? String(span.attributes.description)
                      : "",
                  );

                  setReplayInputOverride(
                    span.input ?? "",
                  );
                }
              }}
              disabled={loadingReplay}
            >
              <option value="">
                Select specialist span to replay
              </option>

              {replayableSpans.map((span) => (
                <option
                  key={span.span_id}
                  value={span.span_id}
                >
                  {span.name} · {span.kind} · {shortId(span.span_id)}
                </option>
              ))}
            </select>

            <textarea
              value={replayDescription}
              onChange={(event) =>
                setReplayDescription(event.target.value)
              }
              placeholder="Optional replay description override"
              rows={2}
              disabled={loadingReplay}
            />

            <textarea
              value={replayInputOverride}
              onChange={(event) =>
                setReplayInputOverride(event.target.value)
              }
              placeholder='Optional input override. JSON is parsed when valid; otherwise it is sent as text.'
              rows={4}
              disabled={loadingReplay}
            />

            <button
              type="button"
              className="trace-load-button"
              disabled={
                loadingReplay ||
                !originalExecutionId.trim() ||
                !replaySourceSpan
              }
              onClick={() => void runReplay()}
            >
              {loadingReplay
                ? "Starting replay..."
                : "Run replay"}
            </button>
          </div>

          {replayResult && (
            <div className="replay-result">
              <div>
                <div className="trace-section-kicker">
                  Replay created
                </div>

                <strong>
                  {shortId(replayResult.replay_execution_id)}
                </strong>

                <code>
                  {replayResult.replay_execution_id}
                </code>
              </div>

              <div className="replay-result-actions">
                <span
                  className={`trace-status-pill ${statusClass(
                    replayResult.status,
                  )}`}
                >
                  {statusLabel(replayResult.status)}
                </span>

                <button
                  type="button"
                  className="trace-load-button"
                  disabled={
                    loadingComparison ||
                    !replayExecutionId.trim()
                  }
                  onClick={() => void loadComparison()}
                >
                  {loadingComparison
                    ? "Waiting / comparing..."
                    : "Compare original vs replay"}
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* =====================================================
          Replay comparison
          ===================================================== */}

      {comparison && (
        <ReplayComparisonPanel
          comparison={comparison}
        />
      )}

      {/* =====================================================
          Trace inspection
          ===================================================== */}

      {!trace ? (
        <div className="trace-empty">
          <div className="trace-empty-icon">
            ◌
          </div>

          <h3>
            No trace selected
          </h3>

          <p>
            Choose an execution above to
            inspect its complete persisted
            workflow trace.
          </p>
        </div>
      ) : (
        <>
          <section className="trace-selected-banner">
            <div>
              <span>
                Selected execution
              </span>

              <strong>
                {shortId(
                  trace.execution_id,
                )}
              </strong>

              <code>
                {trace.execution_id}
              </code>
            </div>

            <span
              className={`trace-status-pill ${statusClass(
                trace.status,
              )}`}
            >
              {statusLabel(
                trace.status,
              )}
            </span>
          </section>

          <section className="trace-summary">
            <TraceMetric
              label="Status"
              value={statusLabel(
                trace.status,
              )}
              accent={statusClass(
                trace.status,
              )}
            />

            <TraceMetric
              label="Duration"
              value={formatDuration(
                trace.wall_clock_ms,
              )}
            />

            <TraceMetric
              label="Total tokens"
              value={formatTokens(
                trace.total_tokens,
              )}
            />

            <TraceMetric
              label="Tool calls"
              value={String(
                trace.total_tool_calls,
              )}
            />

            <TraceMetric
              label="Total cost"
              value={formatCost(
                trace.total_cost,
              )}
            />

            <TraceMetric
              label="Spans"
              value={String(
                trace.spans.length,
              )}
            />
          </section>

          <div className="trace-workspace">
            <section className="trace-tree-panel">
              <div className="trace-panel-header">
                <div>
                  <div className="trace-section-kicker">
                    Workflow
                  </div>

                  <h3>
                    Execution timeline
                  </h3>

                  <span>
                    {trace.spans.length}{" "}
                    spans
                  </span>
                </div>

                <span className="trace-tree-summary">
                  {formatDuration(
                    trace.wall_clock_ms,
                  )}
                </span>
              </div>

              <div className="trace-tree">
                {roots.length === 0 ? (
                  <div className="empty-state">
                    No spans recorded.
                  </div>
                ) : (
                  roots.map((span) => (
                    <TraceNode
                      key={
                        span.span_id
                      }
                      span={span}
                      childrenMap={
                        childrenMap
                      }
                      depth={0}
                      selectedSpanId={
                        selectedSpan?.span_id ??
                        null
                      }
                      onSelect={(span) => {
                        setSelectedSpan(span);

                        if (isReplayableSpan(span)) {
                          setReplaySourceSpan(span);
                          setError(null);
                        } else {
                          setReplaySourceSpan(null);
                          setError(
                            "Replay is available only for specialist spans that reference a persisted subtask.",
                          );
                        }
                      }}
                    />
                  ))
                )}
              </div>
            </section>

            <section className="trace-detail-panel">
              {!selectedSpan ? (
                <div className="trace-detail-empty">
                  <div className="trace-detail-empty-icon">
                    ◇
                  </div>

                  <h3>
                    Select a span
                  </h3>

                  <p>
                    Click any workflow,
                    agent, LLM, tool, memory,
                    or human-decision span
                    to inspect its details.
                  </p>
                </div>
              ) : (
                <SpanDetails
                  span={selectedSpan}
                />
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

/* =========================================================
   Replay comparison
   ========================================================= */

function ReplayComparisonPanel({
  comparison,
}: {
  comparison: ReplayComparison;
}) {
  const original = comparison.original ?? {
    status: "unknown",
    wall_clock_ms: null,
    total_tokens: 0,
    total_tool_calls: 0,
    total_cost: 0,
  };

  const replay = comparison.replay ?? {
    status: "unknown",
    wall_clock_ms: null,
    total_tokens: 0,
    total_tool_calls: 0,
    total_cost: 0,
  };

  const changes = comparison.changes ?? {
    status_changed: false,
    latency_delta_ms: 0,
    token_delta: 0,
    tool_call_delta: 0,
    cost_delta: 0,
    span_count_delta: 0,
  };

  const spanDifferences = Array.isArray(comparison.span_differences)
    ? comparison.span_differences
    : [];

  const changed = spanDifferences.filter(
    (item) => item.change === "changed",
  );
  const added = spanDifferences.filter(
    (item) => item.change === "added",
  );
  const removed = spanDifferences.filter(
    (item) => item.change === "removed",
  );
  const notReached = spanDifferences.filter(
    (item) => item.change === "not_reached",
  );
  const unchanged = spanDifferences.filter(
    (item) => item.change === "unchanged",
  );

  const hasSpanChanges =
    changed.length > 0 ||
    added.length > 0 ||
    removed.length > 0 ||
    notReached.length > 0;

  const hasMetricChanges =
    Number(changes.latency_delta_ms ?? 0) !== 0 ||
    Number(changes.token_delta ?? 0) !== 0 ||
    Number(changes.tool_call_delta ?? 0) !== 0 ||
    Number(changes.cost_delta ?? 0) !== 0;

  const comparisonChanged =
    Boolean(changes.status_changed) ||
    hasSpanChanges ||
    hasMetricChanges;

  return (
    <section className="replay-comparison">
      <div className="replay-comparison-header">
        <div>
          <div className="trace-section-kicker">Comparison result</div>
          <h2>Original vs replay</h2>
          <p>See what changed, what improved, and what stayed the same.</p>
        </div>
        <div className="replay-comparison-counts">
          <span><strong>{changed.length}</strong> changed</span>
          <span><strong>{added.length}</strong> added</span>
          <span><strong>{removed.length}</strong> removed</span>
          <span><strong>{notReached.length}</strong> not reached</span>
          <span><strong>{unchanged.length}</strong> unchanged</span>
        </div>
      </div>

      <div className="replay-execution-grid">
        <ReplayExecutionCard
          title="Original"
          executionId={comparison.original_execution_id ?? "unknown"}
          execution={original}
        />
        <ReplayExecutionCard
          title="Replay"
          executionId={comparison.replay_execution_id ?? "unknown"}
          execution={replay}
        />
      </div>

      <div className="replay-delta-grid">
        <ReplayDelta
          label="Status"
          value={
            changes.status_changed
              ? `${original.status} → ${replay.status}`
              : comparisonChanged
                ? "Execution status unchanged"
                : "No change"
          }
          changed={comparisonChanged}
        />
        <ReplayDelta
          label="Latency"
          value={formatSignedDuration(Number(changes.latency_delta_ms ?? 0))}
          changed={Number(changes.latency_delta_ms ?? 0) !== 0}
          tone={Number(changes.latency_delta_ms ?? 0) < 0 ? "good" : Number(changes.latency_delta_ms ?? 0) > 0 ? "bad" : "neutral"}
        />
        <ReplayDelta
          label="Tokens"
          value={formatSignedNumber(Number(changes.token_delta ?? 0))}
          changed={Number(changes.token_delta ?? 0) !== 0}
          tone={Number(changes.token_delta ?? 0) < 0 ? "good" : Number(changes.token_delta ?? 0) > 0 ? "bad" : "neutral"}
        />
        <ReplayDelta
          label="Tool calls"
          value={formatSignedNumber(Number(changes.tool_call_delta ?? 0))}
          changed={Number(changes.tool_call_delta ?? 0) !== 0}
          tone={Number(changes.tool_call_delta ?? 0) < 0 ? "good" : Number(changes.tool_call_delta ?? 0) > 0 ? "bad" : "neutral"}
        />
        <ReplayDelta
          label="Cost"
          value={formatSignedCost(Number(changes.cost_delta ?? 0))}
          changed={Number(changes.cost_delta ?? 0) !== 0}
          tone={Number(changes.cost_delta ?? 0) < 0 ? "good" : Number(changes.cost_delta ?? 0) > 0 ? "bad" : "neutral"}
        />
        <ReplayDelta
          label="Span count"
          value={formatSignedNumber(Number(changes.span_count_delta ?? 0))}
          changed={Number(changes.span_count_delta ?? 0) !== 0}
          tone="neutral"
        />
      </div>

      <div className="replay-span-differences">
        <div className="replay-section-heading">
          <div>
            <h3>Changed spans</h3>
            <span>Only spans with meaningful differences are expanded.</span>
          </div>
        </div>

        {changed.length + added.length + removed.length + notReached.length === 0 ? (
          <div className="analytics-empty">No changed spans detected.</div>
        ) : (
          <div className="replay-span-list">
            {[...changed, ...added, ...removed, ...notReached].map((difference, index) => (
              <ReplaySpanDifferenceRow
                key={`${difference.key}-${difference.change}-${index}`}
                difference={difference}
              />
            ))}
          </div>
        )}

        {unchanged.length > 0 && (
          <details className="replay-unchanged">
            <summary>
              <span>Unchanged spans</span>
              <strong>{unchanged.length}</strong>
            </summary>
            <div className="replay-unchanged-list">
              {unchanged.map((difference, index) => (
                <div
                  key={`${difference.key}-unchanged-${index}`}
                  className="replay-unchanged-row"
                >
                  <span>{formatReplaySpanKey(difference.key)}</span>
                  <span>unchanged</span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </section>
  );
}

function ReplaySpanDifferenceRow({
  difference,
}: {
  difference: ReplayComparison["span_differences"][number];
}) {
  const fields = Array.isArray(difference.fields)
    ? difference.fields
    : [];

  const fieldDiffs = difference.field_diffs ?? {};

  const isChanged =
    difference.change === "changed";

  const isNotReached =
    difference.change === "not_reached";

  return (
    <details
      className={`replay-span-diff replay-change-${difference.change}`}
      open={isChanged}
    >
      <summary>
        <div>
          <strong>
            {formatReplaySpanKey(
              difference.key,
            )}
          </strong>

          <span>
            {difference.change === "not_reached"
              ? "not reached"
              : difference.change}
          </span>
        </div>

        <div className="replay-changed-fields">
          {isNotReached ? (
            <span>
              replay stopped before this span
            </span>
          ) : fields.length === 0 ? (
            <span>
              {difference.change}
            </span>
          ) : (
            fields.map((field) => (
              <span key={field}>
                {field}
              </span>
            ))
          )}
        </div>
      </summary>

      {isNotReached && (
        <div className="replay-not-reached-message">
          <strong>
            This span was not reached by the replay.
          </strong>

          <span>
            It existed in the original execution, but
            the replay terminated before this logical
            step could execute. It was not removed from
            the workflow.
          </span>
        </div>
      )}

      {isChanged && fields.length > 0 && (
        <div className="replay-field-diff-grid">
          {fields.map((field) => {
            const diff = fieldDiffs[field];

            const originalValue =
              diff?.original ??
              difference.original?.[field];

            const replayValue =
              diff?.replay ??
              difference.replay?.[field];

            return (
              <div
                className="replay-field-diff"
                key={field}
              >
                <div className="replay-field-diff-title">
                  {field}
                </div>

                <div>
                  <span>Original</span>

                  <pre>
                    {pretty(originalValue)}
                  </pre>
                </div>

                <div>
                  <span>Replay</span>

                  <pre>
                    {pretty(replayValue)}
                  </pre>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {difference.change === "added" && (
        <div className="replay-not-reached-message">
          <strong>
            New span in replay.
          </strong>

          <span>
            This logical step did not exist in the
            original execution.
          </span>
        </div>
      )}

      {difference.change === "removed" && (
        <div className="replay-not-reached-message">
          <strong>
            Span removed from replay.
          </strong>

          <span>
            The replay completed without executing this
            logical step, so it is classified as removed
            rather than not reached.
          </span>
        </div>
      )}
    </details>
  );
}

function formatReplaySpanKey(
  key: string,
): string {
  const parts = key.split("|");

  const kind = parts[0] ?? "";
  const name = parts[1] ?? "";
  const agent = parts[2] ?? "";
  const specialist = parts[3] ?? "";
  const tool = parts[4] ?? "";
  const occurrence = parts[5] ?? "";

  const base =
    name || kind || "span";

  const owner =
    specialist || agent
      ? ` · ${specialist || agent}`
      : "";

  const toolSuffix =
    tool
      ? ` · ${tool}`
      : "";

  const occurrenceSuffix =
    occurrence
      ? ` ${occurrence}`
      : "";

  return `${base}${owner}${toolSuffix}${occurrenceSuffix}`;
}

function ReplayExecutionCard({
  title,
  executionId,
  execution,
}: {
  title: string;
  executionId: string;
  execution: ReplayComparison["original"];
}) {
  return (
    <div className="replay-execution-card">
      <div className="replay-card-heading">
        <div>
          <div className="trace-section-kicker">
            {title}
          </div>

          <code>
            {shortId(executionId)}
          </code>
        </div>

        <span
          className={`trace-status-pill ${statusClass(
            execution.status,
          )}`}
        >
          {statusLabel(
            execution.status,
          )}
        </span>
      </div>

      <div className="replay-metrics">
        <TraceMetric
          label="Latency"
          value={formatDuration(
            execution.wall_clock_ms,
          )}
        />

        <TraceMetric
          label="Tokens"
          value={formatTokens(
            execution.total_tokens,
          )}
        />

        <TraceMetric
          label="Tool calls"
          value={String(
            execution.total_tool_calls,
          )}
        />

        <TraceMetric
          label="Cost"
          value={formatCost(
            execution.total_cost,
          )}
        />
      </div>
    </div>
  );
}

function ReplayDelta({
  label,
  value,
  changed,
  tone = "neutral",
}: {
  label: string;
  value: string;
  changed: boolean;
  tone?: "good" | "bad" | "neutral";
}) {
  return (
    <div
      className={`replay-delta ${
        changed ? "replay-delta-changed" : ""
      } replay-delta-${tone}`}
    >
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

function formatSignedNumber(
  value: number,
): string {
  if (value === 0) {
    return "0";
  }

  return value > 0
    ? `+${value.toLocaleString()}`
    : value.toLocaleString();
}

function formatSignedCost(
  value: number,
): string {
  if (value === 0) {
    return "$0.0000";
  }

  return value > 0
    ? `+$${value.toFixed(4)}`
    : `-$${Math.abs(value).toFixed(4)}`;
}

function formatSignedDuration(
  value: number,
): string {
  if (value === 0) {
    return "0 ms";
  }

  const prefix =
    value > 0 ? "+" : "-";

  return `${prefix}${formatDuration(
    Math.abs(value),
  )}`;
}

/* =========================================================
   Trace metrics
   ========================================================= */

function TraceMetric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div
      className={`trace-metric ${
        accent
          ? `metric-${accent}`
          : ""
      }`}
    >
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

/* =========================================================
   Span details
   ========================================================= */

function SpanDetails({
  span,
}: {
  span: TraceSpan;
}) {
  return (
    <div className="span-details">
      <div className="span-details-header">
        <div className="span-title-row">
          <div className="span-icon-large">
            {spanIcon(span)}
          </div>

          <div>
            <div className="eyebrow">
              {span.kind}
            </div>

            <h3>
              {span.name}
            </h3>

            <p>
              {span.span_id}
            </p>
          </div>
        </div>

        <span
          className={`trace-status-pill ${statusClass(
            span.status,
          )}`}
        >
          {statusLabel(
            span.status,
          )}
        </span>
      </div>

      <div className="span-metadata-grid">
        <TraceMetric
          label="Kind"
          value={span.kind}
        />

        <TraceMetric
          label="Agent"
          value={
            span.agent ??
            span.specialist ??
            "—"
          }
        />

        <TraceMetric
          label="Latency"
          value={formatDuration(
            span.duration_ms,
          )}
        />

        <TraceMetric
          label="Confidence"
          value={
            span.confidence === null ||
            span.confidence ===
              undefined
              ? "—"
              : `${(
                  span.confidence * 100
                ).toFixed(0)}%`
          }
        />

        <TraceMetric
          label="Tokens"
          value={formatTokens(
            span.total_tokens,
          )}
        />

        <TraceMetric
          label="Cost"
          value={formatCost(
            span.cost,
          )}
        />

        <TraceMetric
          label="Provider"
          value={
            span.provider ?? "—"
          }
        />

        <TraceMetric
          label="Model"
          value={
            span.model ?? "—"
          }
        />
      </div>

      <HITLDetails span={span} />

      {span.tool_name && (
        <DetailSection
          title="Tool"
          value={span.tool_name}
        />
      )}

      <DetailSection
        title="Input"
        value={span.input}
      />

      <DetailSection
        title="Prompt"
        value={span.prompt}
      />

      <DetailSection
        title="Output"
        value={span.output}
      />

      <DetailSection
        title="Raw Response"
        value={span.raw_response}
      />

      {span.error && (
        <DetailSection
          title="Error"
          value={span.error}
          error
        />
      )}

      <DetailSection
        title="Metadata"
        value={pretty(
          span.attributes,
        )}
      />

      <div className="span-timestamps">
        <div>
          <span>Started</span>

          <strong>
            {formatDate(
              span.started_at,
            )}
          </strong>
        </div>

        <div>
          <span>Ended</span>

          <strong>
            {formatDate(
              span.ended_at,
            )}
          </strong>
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   HITL details
   ========================================================= */

function HITLDetails({
  span,
}: {
  span: TraceSpan;
}) {
  const decision =
    attributeValue(
      span.attributes,
      "decision",
    );

  const decisionId =
    attributeValue(
      span.attributes,
      "decision_id",
    );

  const approvalLevel =
    attributeValue(
      span.attributes,
      "approval_level",
    );

  const escalationTrigger =
    attributeValue(
      span.attributes,
      "escalation_trigger",
    );

  const feedback =
    attributeValue(
      span.attributes,
      "feedback",
    );

  const resumeNode =
    attributeValue(
      span.attributes,
      "resume_node",
    );

  const resumeSubtaskId =
    attributeValue(
      span.attributes,
      "resume_subtask_id",
    );

  const humanDecision =
    attributeValue(
      span.attributes,
      "human_decision",
    );

  const isHumanDecision =
    span.kind ===
      "human_decision" ||
    span.name ===
      "human_decision";

  const isResume =
    span.name ===
    "execution.resume";

  if (
    !isHumanDecision &&
    !isResume
  ) {
    return null;
  }

  return (
    <section className="trace-hitl-details">
      <div className="trace-hitl-header">
        <div className="trace-hitl-icon">
          H
        </div>

        <div>
          <div className="eyebrow">
            {isHumanDecision
              ? "Human decision"
              : "Workflow resume"}
          </div>

          <strong>
            {isHumanDecision
              ? "HITL decision recorded"
              : "Execution resumed"}
          </strong>
        </div>
      </div>

      <div className="trace-hitl-grid">
        {decision && (
          <HITLField
            label="Decision"
            value={decision}
          />
        )}

        {humanDecision && (
          <HITLField
            label="Human decision"
            value={
              humanDecision
            }
          />
        )}

        {approvalLevel && (
          <HITLField
            label="Approval level"
            value={
              approvalLevel
            }
          />
        )}

        {escalationTrigger && (
          <HITLField
            label="Escalation trigger"
            value={
              escalationTrigger
            }
          />
        )}

        {resumeNode && (
          <HITLField
            label="Resume node"
            value={resumeNode}
          />
        )}

        {resumeSubtaskId && (
          <HITLField
            label="Resume subtask"
            value={
              resumeSubtaskId
            }
          />
        )}

        {decisionId && (
          <HITLField
            label="Decision ID"
            value={decisionId}
          />
        )}
      </div>

      {feedback && (
        <div className="trace-hitl-feedback">
          <span>
            Reviewer feedback
          </span>

          <pre>{feedback}</pre>
        </div>
      )}
    </section>
  );
}

function HITLField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <span>{label}</span>

      <strong>
        {value}
      </strong>
    </div>
  );
}

function DetailSection({
  title,
  value,
  error = false,
}: {
  title: string;
  value: string | null;
  error?: boolean;
}) {
  return (
    <section
      className={`span-detail-section ${
        error
          ? "span-detail-error"
          : ""
      }`}
    >
      <div className="detail-section-heading">
        <h4>{title}</h4>
      </div>

      <pre>
        {value ?? "—"}
      </pre>
    </section>
  );
}

/* =========================================================
   Observability analytics
   ========================================================= */

function ObservabilityAnalyticsPanel({
  analytics,
}: {
  analytics: ObservabilityAnalytics;
}) {
  const overview =
    analytics.overview;

  return (
    <section className="analytics-section">
      <div className="analytics-header">
        <div>
          <div className="trace-section-kicker">
            Analytics
          </div>

          <h2 className="analytics-title">
            Cost & performance
          </h2>

          <span className="analytics-subtitle">
            Cross-execution observability
          </span>
        </div>

        <div className="analytics-execution-count">
          <strong>
            {overview.execution_count}
          </strong>

          <span>
            executions
          </span>
        </div>
      </div>

      <div className="analytics-summary">
        <TraceMetric
          label="Executions"
          value={String(
            overview.execution_count,
          )}
        />

        <TraceMetric
          label="Completed"
          value={String(
            overview.completed_count,
          )}
        />

        <TraceMetric
          label="Escalated"
          value={String(
            overview.escalated_count,
          )}
          accent="trace-status-escalated"
        />

        <TraceMetric
          label="Failed"
          value={String(
            overview.failed_count,
          )}
        />

        <TraceMetric
          label="Total cost"
          value={formatCost(
            overview.total_cost,
          )}
        />

        <TraceMetric
          label="Avg latency"
          value={formatDuration(
            overview.average_wall_clock_ms,
          )}
        />
      </div>

      <div className="analytics-secondary">
        <AnalyticsMiniMetric
          label="Total tokens"
          value={formatTokens(
            overview.total_tokens,
          )}
        />

        <AnalyticsMiniMetric
          label="Tool calls"
          value={String(
            overview.total_tool_calls,
          )}
        />

        <AnalyticsMiniMetric
          label="Average cost"
          value={formatCost(
            overview.average_cost,
          )}
        />

        <AnalyticsMiniMetric
          label="Escalation rate"
          value={`${(
            overview.escalation_rate *
            100
          ).toFixed(1)}%`}
        />

        <AnalyticsMiniMetric
          label="Human review"
          value={formatDuration(
            overview.total_human_review_ms,
          )}
        />

        <AnalyticsMiniMetric
          label="Avg human review"
          value={formatDuration(
            overview.average_human_review_ms,
          )}
        />
      </div>

      <div className="analytics-grid">
        <AnalyticsCard title="Cost by task type">
          {analytics
            .cost_by_task_type.length ===
          0 ? (
            <AnalyticsEmpty />
          ) : (
            analytics.cost_by_task_type
              .slice(0, 8)
              .map((item) => (
                <AnalyticsRow
                  key={
                    item.task_type
                  }
                  label={
                    item.task_type
                  }
                  value={formatCost(
                    item.total_cost,
                  )}
                  secondary={`${item.executions} executions · ${(
                    item.escalation_rate *
                    100
                  ).toFixed(
                    0,
                  )}% escalated`}
                />
              ))
          )}
        </AnalyticsCard>

        <AnalyticsCard title="Most expensive agents">
          {analytics.agents.length ===
          0 ? (
            <AnalyticsEmpty />
          ) : (
            analytics.agents
              .slice(0, 8)
              .map((item) => (
                <AnalyticsRow
                  key={item.agent}
                  label={
                    item.agent
                  }
                  value={formatCost(
                    item.total_cost,
                  )}
                  secondary={`${formatTokens(
                    item.total_tokens,
                  )} tokens · ${formatDuration(
                    item.total_duration_ms,
                  )}`}
                />
              ))
          )}
        </AnalyticsCard>

        <AnalyticsCard title="Model usage">
          {analytics.models.length ===
          0 ? (
            <AnalyticsEmpty />
          ) : (
            analytics.models
              .slice(0, 8)
              .map((item) => (
                <AnalyticsRow
                  key={`${item.provider}-${item.model}-${item.agent}`}
                  label={item.model}
                  value={formatCost(
                    item.total_cost,
                  )}
                  secondary={`${item.provider} · ${item.calls} calls · ${formatTokens(
                    item.total_tokens,
                  )} tokens`}
                />
              ))
          )}
        </AnalyticsCard>

        <AnalyticsCard title="Tool usage">
          {analytics.tools.length ===
          0 ? (
            <AnalyticsEmpty />
          ) : (
            analytics.tools
              .slice(0, 8)
              .map((item) => (
                <AnalyticsRow
                  key={
                    item.tool_name
                  }
                  label={
                    item.tool_name
                  }
                  value={`${item.calls} calls`}
                  secondary={`${formatDuration(
                    item.average_duration_ms,
                  )} avg · ${(
                    item.failure_rate *
                    100
                  ).toFixed(
                    1,
                  )}% failed`}
                />
              ))
          )}
        </AnalyticsCard>
      </div>
    </section>
  );
}

function AnalyticsMiniMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="analytics-mini-metric">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

function AnalyticsCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="analytics-card">
      <div className="analytics-card-header">
        <h3>{title}</h3>
      </div>

      <div className="analytics-card-body">
        {children}
      </div>
    </div>
  );
}

function AnalyticsRow({
  label,
  value,
  secondary,
}: {
  label: string;
  value: string;
  secondary?: string;
}) {
  return (
    <div className="analytics-row">
      <div className="analytics-row-label">
        <strong>{label}</strong>

        {secondary && (
          <span>
            {secondary}
          </span>
        )}
      </div>

      <strong className="analytics-row-value">
        {value}
      </strong>
    </div>
  );
}

function AnalyticsEmpty() {
  return (
    <div className="analytics-empty">
      No data available yet.
    </div>
  );
}