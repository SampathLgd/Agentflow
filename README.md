# AgentFlow --- Multi-Agent Orchestration System

> A production-oriented multi-agent orchestration platform built with
> LangGraph, FastAPI, Redis, PostgreSQL, ChromaDB, Celery, and Docker
> Compose, with tool use, persistent memory, human-in-the-loop control,
> execution tracing, analytics, and selected-span replay.
> 
## 🎥 Project Demo

Watch the complete walkthrough here:

```
[(https://www.loom.com/share/a0ce9ebb3646482cada73dcc8d312b6b)](https://www.loom.com/share/a0ce9ebb3646482cada73dcc8d312b6b)
```
---
## Project Description

AgentFlow is a multi-agent orchestration system for executing complex,
multi-step tasks through a coordinated hierarchy of AI agents rather
than a single LLM call.

A **Supervisor Agent** converts an incoming task into a structured
execution plan, assigns subtasks to domain-specific specialists, and
manages dependency-aware execution. Specialists can use registered tools
such as web search, read-only database querying, and code execution. A
**Reviewer Agent** validates specialist outputs before synthesis.

The system addresses production-oriented agent problems including task
decomposition, dependency management, tool failures, low-confidence
results, human approval, asynchronous execution, persistent memory,
observability, and reproducible debugging.

The implementation follows the Project 15 architecture: a supervisor
coordinating specialists with tools, persistent memory, human
escalation, and full execution observability.

## Architecture

``` mermaid
flowchart TB
    U[User / Client] --> API[FastAPI API]

    API --> TASK[Task / Execution Service]
    API --> HITL[HITL API]
    API --> TRACE[Trace / Replay API]

    TASK --> CELERY[Celery Worker]
    HITL --> CELERY
    CELERY --> GRAPH[LangGraph Orchestration]

    GRAPH --> MEMR[Redis Working Memory]
    GRAPH --> MEML[ChromaDB Long-Term Memory]
    GRAPH --> SUP[Supervisor Agent]

    SUP --> PLAN[Structured Execution Plan]
    PLAN --> DISPATCH[Dependency-Aware Dispatcher]

    DISPATCH --> R[Research Specialist]
    DISPATCH --> A[Data Analysis Specialist]
    DISPATCH --> W[Writing Specialist]
    DISPATCH --> C[Code Execution Specialist]

    R --> TOOLS[Tool Registry / Executor]
    A --> TOOLS
    W --> TOOLS
    C --> TOOLS

    TOOLS --> WEB[Web Search]
    TOOLS --> DBQ[Read-Only Database Query]
    TOOLS --> CODE[Code Execution]
    TOOLS --> APIX[Configured API Tools]

    R --> REVIEW[Reviewer Agent]
    A --> REVIEW
    W --> REVIEW
    C --> REVIEW

    REVIEW -->|Approved| SYN[Synthesis]
    REVIEW -->|Retry / Feedback| DISPATCH
    REVIEW -->|Low Confidence| ESC[Human Escalation]
    GRAPH -->|Low Specialist Confidence| ESC
    GRAPH -->|Explicit User Escalation| ESC

    ESC --> DECISION[Human Decision]
    DECISION -->|Approve| RESUME[Resume Execution]
    DECISION -->|Replan| PLAN
    DECISION -->|Reject| END[Terminal State]

    RESUME --> DISPATCH
    RESUME --> REVIEW
    SYN --> END

    GRAPH --> TRACESTORE[(PostgreSQL Trace Store)]
    TRACE --> TRACESTORE
    TRACE --> REPLAY[Selected-Span Replay]
    REPLAY --> NEWEXEC[New Replay Execution]
    NEWEXEC --> GRAPH

    POSTGRES[(PostgreSQL)] --> TASK
    POSTGRES --> HITL
    POSTGRES --> TRACESTORE

    FRONTEND[React Frontend / Trace Explorer] --> API
    FRONTEND --> TRACE

    CELERY --> REDIS[Redis Queue / Result Backend]
```

### Core workflow

``` text
Task Intake
    ↓
Long-Term Memory Retrieval
    ↓
Supervisor Planning
    ↓
Dependency-Aware Dispatch
    ↓
Specialists + Tools
    ↓
Reviewer
    ├── Retry / feedback → Specialist
    ├── Low confidence → Human Escalation
    └── Approved → Synthesis
                         ↓
                       End
```

### HITL resume workflow

``` text
Escalation
    ↓
Persisted Human Decision
    ↓
Celery Resume Task
    ↓
resume_after_human
    ├── approve  → continue execution
    ├── replan   → planning
    └── reject   → terminal state
```

## Key Features

### Supervisor-based task decomposition

The Supervisor produces a typed `ExecutionPlan` containing:

-   subtask ID;
-   description;
-   assigned specialist;
-   required inputs;
-   expected output;
-   estimated complexity;
-   dependency relationships.

Pydantic validation rejects invalid dependency graphs before execution.

### Specialized agents

  Agent            Responsibility
  ---------------- -------------------------------------------
  Supervisor       Task decomposition and orchestration
  Research         Research and web-search workflows
  Data Analysis    Data analysis and database/tool workflows
  Writing          Structured writing and synthesis support
  Code Execution   Programmatic/code-oriented tasks
  Reviewer         Specialist-output validation

### Tool-use layer

Specialists interact with external capabilities through:

``` text
Specialist
    ↓
Tool Runner
    ↓
Tool Executor
    ↓
Tool Registry
    ↓
Concrete Tool
```

Implemented capabilities include:

-   web search;
-   read-only database querying;
-   code execution;
-   configured API access;
-   tool invocation tracing.

### Dependency-aware execution

Subtasks explicitly declare dependencies, allowing independent work to
proceed without waiting for unrelated tasks while dependent tasks wait
for required predecessors.

### Redis working memory

Task-scoped working memory stores:

-   execution plan;
-   completed subtask outputs;
-   intermediate results;
-   error records.

Redis namespaces are isolated by task ID:

``` text
agentflow:memory:{task_id}:plan
agentflow:memory:{task_id}:subtask_outputs
agentflow:memory:{task_id}:intermediate_results
agentflow:memory:{task_id}:errors
```

### ChromaDB long-term memory

Completed executions can contribute reusable semantic memories such as
successful approaches, task context, useful results, and execution
metadata.

Future tasks retrieve relevant memories before planning.

### Human-in-the-loop escalation

Execution can pause when human intervention is required because of low
confidence, approval-sensitive actions, or explicit user escalation.

Persisted HITL information includes:

-   escalation reason;
-   escalation trigger;
-   approval level;
-   proposed action;
-   human decision;
-   human feedback;
-   resume location.

Supported decisions include:

``` text
approve
replan
reject
```

### Durable asynchronous resume

HITL does not depend on an in-memory pause in the API process.

``` text
Escalated
    ↓
Human Decision
    ↓
Mark Resuming
    ↓
Celery
    ↓
LangGraph Resume
    ↓
Specialist / Review / Planning
    ↓
Synthesis
```

### Reviewer and confidence routing

Low-confidence specialist or reviewer results can trigger human
escalation. Reviewer rejection can route work back for retry with
feedback.

``` text
Specialist
    ↓
confidence check
    ├── acceptable → Review
    └── low        → HITL
```

### Full execution tracing

Important workflow, agent, tool, memory, and human-decision operations
are persisted as trace spans.

A representative execution can appear as:

``` text
execution
├── check_user_escalation
├── retrieve_long_term_memory
│   └── memory.retrieve
├── planning
│   └── llm.generate_structured
├── specialist
│   └── tool.web_search
├── human_escalation
├── human_decision
├── execution.resume
├── resume_after_human
├── review
└── synthesis
```

Trace data can include status, duration, inputs, outputs, token usage,
cost information, tool calls, subtask IDs, and workflow metadata.

### Trace Explorer and analytics

The frontend provides:

-   execution selection and inspection;
-   persisted span inspection;
-   execution metadata;
-   latency, token, cost, and tool-call metrics;
-   changed/added/removed span analysis;
-   original-vs-replay comparison.

### Selected-span replay

A persisted specialist span can be replayed as a new execution.

``` text
Original Execution
      ↓
Selected Span
      ↓
Persisted Source Subtask
      ↓
Optional Input / Description Override
      ↓
New Execution
      ↓
Independent Replay
      ↓
Original vs Replay Comparison
```

The comparison exposes changes in:

-   execution status;
-   latency;
-   tokens;
-   tool calls;
-   cost;
-   inputs;
-   outputs;
-   spans.

## Technology Stack

  Layer              Technology
  ------------------ --------------------------------------------
  Language           Python 3.12
  API                FastAPI
  Orchestration      LangGraph
  Validation         Pydantic
  LLM Layer          LLM Router / Google GenAI in verified runs
  Agents             Custom Python agents
  Tools              Custom registry and executor
  Working Memory     Redis
  Long-Term Memory   ChromaDB
  Durable Storage    PostgreSQL
  Async Execution    Celery
  Queue / Broker     Redis
  Frontend           React
  Containers         Docker / Docker Compose
  Testing            Pytest

## Service Architecture

``` text
┌──────────────────────────────────────────────┐
│                 Docker Compose               │
│                                              │
│  React Frontend ─────► FastAPI Backend       │
│                              │               │
│             ┌────────────────┼───────────┐   │
│             ▼                ▼           ▼   │
│        PostgreSQL          Redis       Chroma│
│        durable data     queue/memory    memory│
│             ▲                │           ▲   │
│             │                ▼           │   │
│             │          Celery Worker ─────┘   │
│             │                │               │
│             └────────────────┘               │
└──────────────────────────────────────────────┘
```

## Repository Structure

``` text
agentflow/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── analysis/
│   │   │   ├── coding/
│   │   │   ├── research/
│   │   │   ├── reviewer/
│   │   │   ├── supervisor/
│   │   │   ├── writing/
│   │   │   └── tool_runner/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── db/
│   │   │   ├── models/
│   │   │   └── repositories/
│   │   ├── graph/
│   │   │   └── workflow.py
│   │   ├── memory/
│   │   │   ├── redis_store.py
│   │   │   └── chroma_store.py
│   │   ├── tasks/
│   │   │   ├── execution.py
│   │   │   └── resume.py
│   │   ├── tools/
│   │   │   ├── builtin_registry.py
│   │   │   ├── executor.py
│   │   │   └── code_execution.py
│   │   ├── llm/
│   │   │   └── router.py
│   │   └── schemas/
│   │       ├── execution.py
│   │       ├── review.py
│   │       └── human_decision.py
│   └── tests/
├── frontend/
├── docker-compose.yml
└── README.md
```

## Execution Lifecycle

### Normal execution

1.  API receives a task.
2.  Execution is created.
3.  Celery queues background execution.
4.  LangGraph retrieves relevant long-term memory.
5.  Supervisor generates a structured plan.
6.  Subtasks are persisted.
7.  Ready subtasks are dependency-dispatched.
8.  Specialists execute and use authorized tools.
9.  Outputs are accumulated in working memory.
10. Reviewer validates the results.
11. Failed or rejected work can be retried.
12. Low-confidence work can escalate to a human.
13. Approved work is synthesized.
14. Final state and traces are persisted.

### HITL execution

``` text
Specialist / Reviewer
        ↓
Confidence / Policy Check
        ↓
Human Escalation
        ↓
Pending Decision
        ├── approve → resume
        ├── replan  → planning
        └── reject  → terminal state
```

### Selected-span replay

``` text
Persisted Execution
        ↓
Select Span
        ↓
Load Source Subtask
        ↓
Optional Input Override
        ↓
Create New Execution
        ↓
Run Selected Specialist Path
        ↓
Persist Replay Trace
        ↓
Compare Original vs Replay
```

## API Capabilities

The API layer supports:

-   task and execution creation;
-   execution inspection;
-   HITL state inspection;
-   human decision submission;
-   resume/retry of human decisions;
-   execution traces;
-   observability analytics;
-   selected-span replay;
-   original-vs-replay comparison.

The API and worker are separated so long-running agent execution does
not block the request process.

## Testing

Latest full-suite verification:

``` text
347 passed
2 warnings
26.28s
```

The verified end-to-end path includes:

``` text
planning
→ specialist execution
→ low-confidence escalation
→ persisted human decision
→ Celery resume
→ resume_after_human
→ review
→ synthesis
→ completed execution
```

Replay verification includes:

``` text
original execution
→ selected specialist span
→ new replay execution
→ replay completion
→ original-vs-replay comparison
```

## Running Locally

### Prerequisites

-   Docker
-   Docker Compose
-   configured LLM credentials in `backend/.env`

### Start the stack

``` bash
docker compose up --build
```

### Services

``` text
Frontend       http://localhost:5173
Backend API    http://localhost:8000
PostgreSQL     localhost:5432
Redis          localhost:6379
ChromaDB       localhost:8001
```

### Run tests

``` bash
docker compose exec backend python -m pytest -q
```

### Follow worker logs

``` bash
docker compose logs -f celery-worker
```

### Follow backend logs

``` bash
docker compose logs -f backend
```

## Example Execution

A representative task:

``` json
{
  "description": "Research a topic, analyze the findings, and produce a concise report."
}
```

can become:

``` text
Supervisor
   │
   ├── Research
   │      └── web_search
   │
   ├── Analysis
   │      └── analysis/database tools
   │
   └── Writing
          └── specialist outputs
                │
                ▼
             Reviewer
                │
                ▼
             Synthesis
```

If confidence is below the configured threshold:

``` text
Specialist
   ↓
confidence = 0.30
threshold = 0.50
   ↓
Human Escalation
   ↓
Human Approval
   ↓
Celery Resume
   ↓
Review
   ↓
Synthesis
   ↓
Completed
```

## Engineering Highlights

### Stateful orchestration

LangGraph provides explicit workflow state and conditional routing
instead of hiding the entire workflow inside a monolithic agent prompt.

### Separation of concerns

``` text
API
 ↓
Task Queue
 ↓
Workflow
 ↓
Agents
 ↓
Tools
 ↓
Memory / Persistence
 ↓
Observability
```

### Durable execution boundaries

Execution state is persisted across API, Celery, PostgreSQL, and Redis
boundaries so HITL workflows can resume independently of the original
API process.

### Controlled tool access

Specialists interact with external capabilities through a registry and
executor boundary rather than directly invoking arbitrary
infrastructure.

### Typed agent contracts

Pydantic schemas enforce structured plans, subtasks, review results, and
human decisions.

### Debuggable agent behavior

Trace persistence and selected-span replay make agent execution
inspectable, reproducible, and comparable instead of treating it as an
opaque LLM call.

## Project Scope

Current implementation covers:

-   multi-agent hierarchy;
-   structured task planning;
-   dependency-aware specialist execution;
-   tool registry and execution;
-   Redis working memory;
-   ChromaDB long-term memory;
-   reviewer-based validation;
-   confidence-based escalation;
-   persistent HITL decisions;
-   Celery-based resume;
-   PostgreSQL persistence;
-   execution tracing;
-   observability analytics;
-   Trace Explorer;
-   selected-span replay;
-   original-vs-replay comparison;
-   Docker Compose deployment;
-   automated testing.

**Kubernetes deployment is intentionally outside the current
implementation scope.**

## Portfolio Summary

**AgentFlow is a production-oriented multi-agent orchestration platform
that coordinates a Supervisor, domain-specialist agents, tools, memory,
reviewer validation, and human-in-the-loop escalation through a stateful
LangGraph workflow. It persists execution state in PostgreSQL and Redis,
stores semantic long-term memory in ChromaDB, executes workloads
asynchronously with Celery, and provides end-to-end observability with
trace exploration, analytics, and selected-span replay for debugging
agent behavior.**

## What This Project Demonstrates

-   Multi-agent system architecture
-   LangGraph workflow orchestration
-   Structured LLM outputs
-   Agent specialization and routing
-   Dependency-aware execution
-   Tool-use architecture
-   Short-term and long-term memory
-   Semantic retrieval
-   Human-in-the-loop workflows
-   Durable asynchronous execution
-   Celery task processing
-   PostgreSQL persistence
-   Redis state and queue infrastructure
-   ChromaDB vector memory
-   Execution tracing
-   Observability analytics
-   Agent replay and debugging
-   Docker-based service orchestration
-   End-to-end testing

## License

Add the license appropriate for the repository before publishing.
