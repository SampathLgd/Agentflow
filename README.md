# AgentFlow

> A production-oriented multi-agent orchestration platform for autonomous task execution with tool use, persistent memory, human-in-the-loop control, resilient LLM routing, and full execution observability.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![MCP](https://img.shields.io/badge/Tools-MCP-purple.svg)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-80%20passing-brightgreen.svg)](#testing)

---

## Project Objective

AgentFlow is being built to solve a fundamental problem with autonomous AI systems:

> **How do we allow multiple AI agents to execute complex real-world tasks autonomously while retaining control, reliability, observability, recoverability, and human oversight?**

The goal is not to build another single-agent chatbot.

The goal is to build an **agent orchestration platform** capable of taking a complex user request, decomposing it into an executable plan, assigning work to specialized agents, allowing those agents to use controlled tools, coordinating dependencies, validating the resulting work, retrying failures, escalating uncertain decisions to humans, learning from previous executions, and providing a complete record of what happened.

The intended end state is:

```text
                         USER TASK
                             │
                             ▼
                    ┌─────────────────┐
                    │    SUPERVISOR   │
                    │     / PLANNER   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ EXECUTION PLAN  │
                    │ + DEPENDENCIES  │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
           ┌─────────┐ ┌──────────┐ ┌──────────┐
           │ Research│ │ Analysis │ │ Writing  │
           │  Agent  │ │  Agent   │ │  Agent   │
           └────┬────┘ └────┬─────┘ └────┬─────┘
                │            │            │
                └────────────┼────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   TOOL LAYER    │
                    │ Custom + MCP    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     REVIEWER    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
          SYNTHESIZE       RETRY         ESCALATE
              │                             │
              ▼                             ▼
          FINAL RESULT                 HUMAN REVIEW
```

The architecture is based on the project's implementation guide, which defines the system as a supervisor-driven multi-agent platform with specialist tool use, persistent memory, human escalation, and observability. 

---

# Why AgentFlow?

Most AI applications stop at:

```text
User → LLM → Response
```

That architecture breaks down when the task requires:

- Multiple independent capabilities
- Long-running execution
- Dependencies between tasks
- External tools
- Failure recovery
- Validation
- Human approval
- Persistent memory
- Auditability
- Cost and latency tracking
- Reproducible execution

AgentFlow is designed around:

```text
User
 ↓
Supervisor
 ↓
Structured execution plan
 ↓
Dependency-aware specialist execution
 ↓
Tool execution
 ↓
Review
 ↓
Retry / Escalation / Synthesis
 ↓
Final result
```

The system treats agents as **components in an execution system**, rather than isolated LLM calls.

---

# Target Architecture

The implementation guide defines three primary agent layers:

### Supervisor

Responsible for:

- Receiving the user's task
- Decomposing the task
- Creating the execution plan
- Assigning specialists
- Managing dependencies
- Coordinating execution

### Specialist Agents

Current specialist domains:

- Research
- Data Analysis
- Writing
- Code Execution

Each specialist owns a domain and can access the tools appropriate for that domain.

### Reviewer

Responsible for:

- Validating specialist outputs
- Evaluating quality
- Providing structured feedback
- Rejecting incomplete work
- Sending rejected work back for retry
- Escalating low-confidence results

This three-layer hierarchy is the foundation specified by the implementation guide. :contentReference[oaicite:1]{index=1}

---

# Core Execution Model

A task flows through the system as follows:

```text
1. Task Intake
       │
       ▼
2. Supervisor Planning
       │
       ▼
3. Execution Plan Validation
       │
       ▼
4. Dependency Resolution
       │
       ▼
5. Specialist Dispatch
       │
       ▼
6. Tool Execution
       │
       ▼
7. Specialist Result
       │
       ├── failure ──► retry
       │
       ├── low confidence ──► escalation
       │
       ▼
8. Reviewer
       │
       ├── rejected ──► retry
       │
       ├── low confidence ──► escalation
       │
       ▼
9. Synthesis
       │
       ▼
10. Final Delivery
```

---

# Execution Plans

The supervisor does not simply produce free-form instructions.

It creates a structured execution plan.

A plan contains:

- Subtask description
- Assigned specialist
- Required inputs
- Expected output
- Estimated complexity
- Dependencies

For example:

```text
Task:
Research a technology and prepare a report.

Execution Plan:

1. Research
   specialist: research
   dependencies: none

2. Analyze findings
   specialist: data_analysis
   dependencies:
      - research

3. Prepare report
   specialist: writing
   dependencies:
      - research
      - analysis
```

This allows AgentFlow to determine which work can run independently and which work must wait.

---

# Dependency-Aware Execution

Dependencies are first-class workflow concepts.

For example:

```text
                ┌─────────────┐
                │  Research   │
                └──────┬──────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      ┌─────────────┐     ┌─────────────┐
      │   Analysis  │     │   Research  │
      │             │     │  Extension  │
      └──────┬──────┘     └──────┬──────┘
             │                   │
             └─────────┬─────────┘
                       ▼
                ┌─────────────┐
                │   Writing   │
                └─────────────┘
```

Independent subtasks can execute without unnecessarily blocking each other.

Dependent subtasks wait until their required outputs are available.

---

# Tool Framework

AgentFlow uses a unified tool framework.

```text
                         ToolExecutor
                              │
              ┌───────────────┴───────────────┐
              │                               │
        Custom Tools                      MCP Tools
              │                               │
      ┌───────┼────────┐              ┌───────┴───────┐
      │       │        │              │               │
     File    Code     API           MCP Adapter     MCP Client
     Tools   Tools    Tools             │               │
      │       │        │                └───────┬───────┘
      └───────┴────────┘                        │
              │                              MCP Server
              └──────────────┬─────────────────┘
                             ▼
                       Tool Result
```

The tool system separates:

- Tool definition
- Tool registration
- Authorization
- Schema validation
- Execution
- Rate limiting
- Invocation logging
- Failure tracking

---

# Built-in Tools

The current implementation includes:

| Tool | Purpose |
|---|---|
| `file_read` | Read files inside the configured workspace |
| `file_write` | Write files inside the configured workspace |
| `code_execution` | Execute Python with timeout controls |
| `web_search` | Perform web searches |
| `database_query` | Execute safe read-only database queries |
| `api_call` | Perform controlled HTTPS API calls |
| MCP tools | Dynamically discovered external tools |

The initial tool set follows the implementation guide's Phase 1 design, which calls for web search, file read/write, sandboxed code execution, database queries, and API calls. :contentReference[oaicite:2]{index=2}

---

# Tool Authorization

Agents do not automatically have access to every tool.

Each tool has an explicit authorization policy.

Example:

```text
file_read
 ├── research       ✓
 ├── writing        ✓
 ├── data_analysis ✗
 └── code_execution ✗
```

Tool definitions contain:

- Name
- Description
- Input schema
- Output schema
- Allowed specialists
- Rate limits

The `ToolRegistry` controls registration and lookup while the `ToolExecutor` enforces execution policy.

---

# Tool Contracts

Tool execution is validated at the boundary.

The framework supports:

- Input schema validation
- Output schema validation
- Authorization checks
- Invocation tracking
- Latency measurement
- Rate limiting
- Success/failure recording

This prevents agents from bypassing the execution layer and calling infrastructure directly.

---

# MCP Integration

AgentFlow supports the **Model Context Protocol (MCP)** as an extensible external tool layer.

MCP tools are adapted into AgentFlow's internal tool abstraction.

This means an agent can use:

```text
Custom Tool
```

or:

```text
MCP Tool
```

through the same:

```text
ToolExecutor
```

interface.

Current MCP capabilities include:

- MCP tool discovery
- MCP tool registration
- MCP tool adapter
- MCP stdio client
- MCP server communication
- MCP tool execution through `ToolExecutor`

This architecture allows external MCP servers to extend AgentFlow without requiring every agent to implement MCP-specific logic.

---

# Security Boundaries

The tool layer contains several security-oriented controls.

### File tools

Workspace restrictions prevent path traversal outside the configured workspace.

### Database tool

The database query tool rejects write operations.

### API tool

The API tool enforces:

- HTTPS
- Host allowlisting

### Code execution

Code execution includes:

- Timeout enforcement
- Empty-code validation
- Maximum timeout limits
- Sandbox abstraction

### Tool access

Specialists can only use tools explicitly authorized for them.

These controls are intended as engineering boundaries, not as a claim of complete production isolation.

Production deployment should additionally use OS/container isolation, network policies, secrets management, authentication, authorization, and resource limits.

---

# Failure Handling

AgentFlow treats failure as part of the workflow.

A specialist failure does not automatically terminate the task.

```text
Specialist
    │
    ▼
  Failure
    │
    ▼
Retry Available?
   / \
 Yes  No
  │    │
  ▼    ▼
Retry Failed
```

The retry system tracks:

- Retry count
- Maximum retries
- Failure reason
- Retry feedback

Once the retry limit is reached, execution enters a failed state.

---

# Reviewer System

The reviewer receives the specialist outputs and evaluates the overall result.

The review is represented by a structured `ReviewResult`.

The reviewer evaluates:

- Approval
- Quality score
- Confidence
- Feedback
- Issues

The routing logic is:

```text
                     Reviewer
                        │
             ┌──────────┼──────────┐
             │          │          │
        approved    rejected    low confidence
             │          │          │
             ▼          ▼          ▼
         synthesis     retry     escalation
```

Rejected reviews can be retried until the configured retry limit is reached.

---

# Confidence-Based Escalation

AgentFlow treats confidence as a workflow signal.

If reviewer confidence falls below the configured threshold:

```text
confidence < threshold
          │
          ▼
      escalation
```

The Phase 1 implementation establishes the escalation boundary and preserves:

- Escalation requirement
- Escalation reason
- Replanning requirement

Persistent human approval, pause/resume, and durable human workflow are part of the planned Human-in-the-Loop phase.

---

# LLM Routing

AgentFlow contains an LLM abstraction layer so agents do not need to directly depend on provider-specific implementations.

The architecture supports provider routing and fallback.

Conceptually:

```text
                 Agent Request
                      │
                      ▼
                 LLM Router
                      │
              ┌───────┴───────┐
              │               │
          Primary          Fallback
          Provider         Provider
              │               │
              └───────┬───────┘
                      ▼
                 LLM Response
```

The current implementation includes provider fallback behavior and tests for routing/failure handling.

The long-term architecture is intended to support multiple LLM providers behind the same agent-facing interface.

---

# Memory Architecture

Persistent memory is a core objective of the complete AgentFlow system.

The planned architecture contains two memory layers.

## Short-Term Working Memory

Short-term memory is scoped to a task execution.

It contains:

- Current execution plan
- Completed specialist outputs
- Intermediate results
- Error logs
- Current execution context

The implementation guide specifies Redis for this working-memory layer. :contentReference[oaicite:3]{index=3}

```text
Task
 │
 ▼
Redis Working Memory
 │
 ├── Plan
 ├── Intermediate Results
 ├── Specialist Outputs
 └── Error Logs
```

---

## Long-Term Semantic Memory

After task completion, the system is intended to extract and store useful information such as:

- What the user asked for
- Which approach worked
- Which tools were used
- Important domain facts
- User preferences
- Lessons from previous executions

The guide specifies ChromaDB for semantic long-term memory. :contentReference[oaicite:4]{index=4}

```text
Completed Task
      │
      ▼
Memory Extraction
      │
      ▼
Embeddings
      │
      ▼
ChromaDB
```

Future tasks can retrieve relevant memories before planning.

---

# Planned Memory Retrieval

The intended planning flow is:

```text
User Task
    │
    ▼
Query Long-Term Memory
    │
    ├── Similar tasks
    ├── Successful approaches
    ├── Failed approaches
    ├── User preferences
    └── Domain knowledge
    │
    ▼
Supervisor Planning
```

Memory is therefore intended to influence planning rather than merely act as a historical log.

---

# Human-in-the-Loop

Human oversight is a fundamental part of the target architecture.

The system is intended to escalate when conditions such as these occur:

- Supervisor confidence is too low
- A specialist repeatedly fails
- A sensitive operation is requested
- Reviewer quality is below threshold
- The user explicitly requests human review

The guide defines multiple approval levels:

```text
Notify
   │
   ▼
Approve Action
   │
   ▼
Approve Plan
   │
   ▼
Take Over
```

The planned approval workflow pauses execution, packages the relevant context, places the request in a review queue, and waits for human action.

---

# Human Review Interface

The planned review interface will expose:

- Original task
- Execution progress
- Current decision point
- Agent's proposed action
- Agent reasoning/context
- Relevant memories
- Similar past decisions
- Approve
- Modify
- Reject
- Take Over
- Human-agent conversation

The guide explicitly defines this as the Human-in-the-Loop interface for the later phase. :contentReference[oaicite:5]{index=5}

---

# Observability

The complete system is designed to provide full execution tracing.

A task trace should capture:

```text
Task
 │
 ├── Supervisor planning
 │
 ├── Specialist execution
 │    ├── Tool calls
 │    ├── LLM calls
 │    └── Results
 │
 ├── Memory retrieval
 │
 ├── Reviewer evaluation
 │
 ├── Retry events
 │
 ├── Escalation events
 │
 └── Human decisions
```

The planned observability layer will track:

- Agent decisions
- Tool calls
- LLM calls
- Latency
- Token usage
- Cost
- Errors
- Confidence
- Escalations
- Human review time

The implementation guide calls for OpenTelemetry-based execution tracing and a visual trace explorer. :contentReference[oaicite:6]{index=6}

---

# Replay and Debugging

A long-term goal is deterministic execution replay.

A historical execution should be inspectable step-by-step:

```text
Original Task
     │
     ▼
Planning
     │
     ▼
Specialist A
     │
     ▼
Tool Call
     │
     ▼
Reviewer
```

An engineer should eventually be able to:

- Inspect every step
- Inspect inputs/outputs
- Modify an input
- Replay from that point
- Compare the new execution with the original
- Diagnose where behavior diverged

This is intended to make agent failures debuggable like conventional distributed systems.

---

# Cost and Performance Tracking

The target system will track execution economics.

Per task:

```text
Total tokens
Total LLM calls
Total tool calls
Total wall-clock time
Human review time
Total cost
```

Aggregated metrics will include:

- Cost per task type
- Most expensive agents
- Tool usage
- Provider usage
- Escalation rate
- Latency
- Failure rate

These metrics are part of the observability phase in the implementation guide. :contentReference[oaicite:7]{index=7}

---

# Technology Stack

The target architecture from the implementation guide uses:

| Component | Technology | Purpose |
|---|---|---|
| Language | Python | Core implementation |
| Orchestration | LangGraph | Agent state machine |
| LLM Providers | Multi-provider | Agent model routing |
| Tool Framework | Custom + MCP | Extensible capabilities |
| Short-Term Memory | Redis | Task working memory |
| Long-Term Memory | ChromaDB | Semantic memory |
| Persistent State | PostgreSQL | Durable application state |
| Queue | Redis + Celery | Async task execution |
| Review UI | React / Streamlit | Human approval |
| API | FastAPI | Service interface |
| Containers | Docker / docker-compose | Deployment |

The guide identifies LangGraph, custom + MCP tools, PostgreSQL + ChromaDB, Redis + Celery, React/Streamlit, and Docker as the target technology stack. :contentReference[oaicite:8]{index=8}

> **Implementation note:** The repository is being built incrementally. Not every target infrastructure component above is implemented yet.

---

# Project Structure

```text
agentflow/
│
├── .gitignore
├── README.md
│
└── backend/
    │
    ├── app/
    │   │
    │   ├── agents/
    │   │   ├── graph/
    │   │   ├── llm/
    │   │   ├── schemas/
    │   │   └── tools/
    │   │       ├── mcp/
    │   │       └── sandbox/
    │   │
    │   ├── config.py
    │   └── main.py
    │
    ├── tests/
    │
    ├── requirements.txt
    └── .env
```

`backend/.env` is local-only and must never be committed.

Use `.env.example` for public configuration documentation.

---

# Current Implementation Status

## Phase 1 — Complete

Current test checkpoint:

```text
80 passed
```

Implemented capabilities include:

### Agent Architecture

- Supervisor agent
- Planner
- Research specialist
- Data analysis specialist
- Writing specialist
- Code execution specialist
- Reviewer agent

### Workflow

- Task intake
- Structured planning
- Execution plans
- Dependency validation
- Dependency-aware dispatch
- Specialist execution
- Retry routing
- Review routing
- Review retry limits
- Synthesis
- Confidence routing
- Escalation boundary
- End-to-end workflow integration

### Tool Framework

- `BaseTool`
- `ToolDefinition`
- `ToolRegistry`
- `ToolExecutor`
- Tool authorization
- Input validation
- Output validation
- Invocation logging
- Latency tracking
- Rate limiting
- Failure tracking

### Built-in Tools

- File read
- File write
- Python code execution
- Web search
- Database query
- API call

### MCP

- MCP adapter
- MCP registry
- MCP tool discovery
- MCP stdio client
- MCP tool invocation
- MCP integration with `ToolExecutor`

### LLM

- LLM abstraction
- Provider routing
- Provider fallback
- Router tests
- Fallback tests

### Testing

The current test suite covers:

- Execution contracts
- Planner integration
- Workflow dependencies
- Specialist behavior
- Specialist retries
- Review schema
- Review routing
- Confidence escalation
- Tool registry
- Tool executor
- Tool contracts
- File tools
- Code execution
- Web search
- Database query
- API calls
- MCP
- LLM routing
- End-to-end workflow execution

---

# Phase Roadmap

The project follows the six-phase structure from the implementation guide.

---

## Phase 1 — Agent Architecture

**Status: COMPLETE**

Goals:

- Agent hierarchy
- Task decomposition
- Execution plan
- Tool registry
- LangGraph state machine
- Specialist execution
- Review
- Retry
- Confidence escalation

Current checkpoint:

```text
80 tests passing
```

---

## Phase 2 — Memory System

**Status: NEXT**

Goals:

### Short-Term Working Memory

Implement Redis-backed task memory containing:

- Execution plan
- Specialist outputs
- Intermediate results
- Error logs

Memory should be scoped to the current task.

### Long-Term Semantic Memory

Implement ChromaDB-backed semantic memory for:

- Previous tasks
- Successful approaches
- Failed approaches
- Domain facts
- User preferences
- Tool usage

### Memory-Aware Planning

The supervisor should retrieve relevant historical memories before creating a new plan.

### Memory Management

Implement:

- Importance scoring
- Consolidation
- Expiration
- User memory management
- Delete endpoint

---

## Phase 3 — Human-in-the-Loop

**Status: PLANNED**

Goals:

- Escalation triggers
- Approval queue
- Workflow pause
- Human approval
- Human rejection
- Human modification
- Human takeover
- Approval levels
- Resume after human decision
- Replanning after feedback
- Human-agent communication

---

## Phase 4 — Observability and Debugging

**Status: PLANNED**

Goals:

- Full execution traces
- OpenTelemetry spans
- Trace explorer
- Agent decision inspection
- Tool call inspection
- LLM call inspection
- Cost tracking
- Latency tracking
- Confidence tracking
- Replay system

---

## Phase 5 — Integration and End-to-End Testing

**Status: PLANNED**

The target demonstration scenario is a complex research task requiring:

```text
Web Search
    ↓
Data Extraction
    ↓
Analysis
    ↓
Written Summary
```

The demo should show:

1. Supervisor decomposition
2. Parallel specialist execution
3. Tool usage
4. Reviewer validation
5. Reviewer-driven retry
6. Memory retrieval
7. Human approval
8. Final synthesis
9. Full execution trace

The guide also calls for Docker-based integration of the orchestration API, Redis, PostgreSQL, ChromaDB, Celery workers, trace explorer, and human review UI. :contentReference[oaicite:9]{index=9}

---

## Phase 6 — Portfolio and Production Polish

**Status: PLANNED**

The final demonstration should show the complete lifecycle:

```text
Complex Request
      ↓
Supervisor Planning
      ↓
Specialist Agents
      ↓
Tool Calls
      ↓
Review
      ↓
Human Approval
      ↓
Memory Update
      ↓
Final Result
      ↓
Trace Explorer
```

The intended portfolio narrative is:

> **I built a multi-agent orchestration system where AI agents decompose complex tasks, use tools to execute them, learn from past interactions through persistent memory, and escalate to humans when confidence is low. It is designed as infrastructure for autonomous AI workflows rather than a single-agent demo.**

This framing follows the project's implementation guide. :contentReference[oaicite:10]{index=10}

---

# Development Philosophy

AgentFlow is being implemented incrementally.

Each architectural capability should have:

```text
Design
  ↓
Contract
  ↓
Implementation
  ↓
Unit Tests
  ↓
Integration Tests
  ↓
System Tests
```

The test suite is treated as an architectural contract.

A feature is not considered complete merely because the code runs.

It should have automated tests covering its expected behavior and failure modes.

---

# Testing

From the backend directory:

```bash
cd backend
python -m pytest -q
```

Current Phase 1 result:

```text
80 passed
```

Run workflow tests:

```bash
python -m pytest tests/test_workflow_integration.py -v
```

Run specialist retry tests:

```bash
python -m pytest tests/test_specialist_retry.py -v
```

Run review tests:

```bash
python -m pytest tests/test_review_routing.py tests/test_confidence_escalation.py -v
```

Run tool tests:

```bash
python -m pytest tests/test_tool_executor.py \
    tests/test_file_read_tool.py \
    tests/test_file_write_tool.py \
    tests/test_code_execution_tool.py -v
```

Run MCP tests:

```bash
python -m pytest tests/test_mcp_tools.py \
    tests/test_mcp_stdio_client.py -v
```

Run the entire suite:

```bash
python -m pytest -q
```

---

# Local Development

## Requirements

Current development environment:

```text
Python 3.12+
pytest
LangGraph
Pydantic
MCP
```

The project targets Python 3.11+ in the architecture guide.

---

## Create Environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

---

## Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

# Environment Variables

Create:

```text
backend/.env
```

Example public template:

```env
GEMINI_API_KEY=
OPENROUTER_API_KEY=
```

Additional provider configuration can be added as the LLM routing layer evolves.

Never commit:

```text
.env
```

to source control.

---

# Design Decisions

## Why LangGraph?

AgentFlow requires explicit state transitions, conditional routing, retries, parallel/sequential execution, and durable workflow semantics.

LangGraph provides the state-machine abstraction required for this style of orchestration.

---

## Why Structured Schemas?

LLM output should not be trusted as arbitrary text at system boundaries.

Structured Pydantic models provide:

- Validation
- Explicit contracts
- Predictable state
- Easier testing
- Safer routing

---

## Why a Custom Tool Framework?

Agents should not directly own infrastructure integrations.

Instead:

```text
Agent
  ↓
ToolExecutor
  ↓
Tool
```

This allows authorization, validation, logging, and rate limiting to be enforced centrally.

---

## Why MCP?

A custom tool framework gives AgentFlow control over its own internal tools.

MCP provides an extensible protocol for connecting external tool servers.

Combining both gives:

```text
AgentFlow-native tools
        +
External MCP ecosystem
```

without forcing agents to understand the implementation details of either.

---

## Why Human-in-the-Loop?

Autonomy should not mean unrestricted autonomy.

Some operations require:

- Higher confidence
- Explicit authorization
- Human judgment
- Business approval
- Sensitive-action confirmation

AgentFlow therefore treats human intervention as a normal workflow state rather than an exceptional error.

---

## Why Persistent Memory?

Without memory, every task begins from zero.

Persistent memory allows future planning to benefit from:

- Previous successful approaches
- Previous failures
- User preferences
- Relevant facts
- Historical tool usage

This is intended to make the system improve over repeated interactions.

---

# Security Model

AgentFlow is designed with defense-in-depth principles.

Current boundaries include:

```text
Agent
  │
  ▼
Authorization
  │
  ▼
Schema Validation
  │
  ▼
Rate Limiting
  │
  ▼
Tool Execution
  │
  ▼
Result Validation
  │
  ▼
Invocation Logging
```

Additional production security will be added as the system moves toward the later phases.

---

# Non-Goals

AgentFlow is not intended to be:

- A simple chatbot
- A single prompt wrapper
- A collection of independent LLM demos
- An unrestricted code execution environment
- A replacement for enterprise authorization systems
- A claim that autonomous agents can safely operate without governance

The purpose is to explore the engineering infrastructure required to make autonomous agent workflows **controlled, observable, recoverable, and extensible**.

---

# Future Architecture

The intended final architecture is:

```text
                           ┌─────────────────────┐
                           │       Client        │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │     FastAPI API     │
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │   Agent Orchestrator│
                           │      LangGraph      │
                           └──────────┬──────────┘
                                      │
              ┌───────────────────────┼────────────────────────┐
              │                       │                        │
              ▼                       ▼                        ▼
        ┌──────────┐            ┌──────────┐            ┌──────────┐
        │Supervisor│            │Specialists│           │ Reviewer │
        └────┬─────┘            └────┬─────┘            └────┬─────┘
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ ToolExecutor │
                              └──────┬───────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
                 Custom             MCP             Sandbox
                  Tools            Tools             Tools
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │    Memory    │
                              ├──────────────┤
                              │ Redis        │
                              │ PostgreSQL   │
                              │ ChromaDB     │
                              └──────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ Observability│
                              ├──────────────┤
                              │ Traces       │
                              │ Metrics      │
                              │ Costs        │
                              │ Replay       │
                              └──────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ Human Review │
                              │     UI       │
                              └──────────────┘
```

---

# Project Milestones

```text
Phase 1  ████████████████████  COMPLETE
Phase 2  ░░░░░░░░░░░░░░░░░░░░  NEXT
Phase 3  ░░░░░░░░░░░░░░░░░░░░  PLANNED
Phase 4  ░░░░░░░░░░░░░░░░░░░░  PLANNED
Phase 5  ░░░░░░░░░░░░░░░░░░░░  PLANNED
Phase 6  ░░░░░░░░░░░░░░░░░░░░  PLANNED
```

Current milestone:

```text
PHASE 1
80 TESTS PASSING
```

---

# Repository Status

AgentFlow is an actively developed engineering project.

The current implementation has completed the initial orchestration foundation and is now moving toward:

1. Persistent memory
2. Human-in-the-loop execution
3. Durable workflow state
4. Full observability
5. End-to-end production-style deployment

The implementation deliberately proceeds incrementally so each architectural layer can be validated before the next one is introduced.

---

# License

License information will be added before the first public release.

---

# Acknowledgements

The architecture and phased implementation plan for this project are based on the **AI Engineering Projects Guide — Project 15: Agent Orchestration System with Tool Use, Memory, and Human-in-the-Loop**.

The implementation is an engineering realization of that architectural blueprint, with implementation decisions and testing added during development.
