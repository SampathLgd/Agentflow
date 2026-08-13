from dataclasses import dataclass
from pathlib import Path
from redis.asyncio import Redis
from app.agents.analysis.agent import DataAnalysisAgent
from app.agents.coding.agent import CodeExecutionAgent
from app.agents.research.agent import ResearchAgent
from app.agents.reviewer.agent import ReviewerAgent
from app.agents.supervisor.agent import SupervisorAgent
from app.agents.writing.agent import WritingAgent
from app.memory.service import MemoryService
from app.agents.supervisor.planner import TaskPlanner
from app.config import Settings
from app.llm.router import LLMRouter

from app.memory.chroma_store import ChromaLongTermMemoryStore
from app.memory.redis_store import RedisWorkingMemoryStore

from app.memory.chroma_client import (
    create_chroma_collection,
)
from app.memory.chroma_store import (
    ChromaLongTermMemoryStore,
)
from app.memory.redis_store import (
    RedisWorkingMemoryStore,
)


from app.tools.builtin_registry import create_builtin_registry
from app.tools.code_execution import CodeExecutionTool
from app.tools.executor import ToolExecutor
from app.agents.tool_runner import SpecialistToolRunner


@dataclass(frozen=True)
class AgentRuntime:
    supervisor: SupervisorAgent
    research_agent: ResearchAgent
    analysis_agent: DataAnalysisAgent
    writing_agent: WritingAgent
    coding_agent: CodeExecutionAgent
    reviewer_agent: ReviewerAgent

    working_memory: RedisWorkingMemoryStore
    long_term_memory: ChromaLongTermMemoryStore
    memory_service: MemoryService


async def build_agent_runtime(
    settings: Settings,
) -> AgentRuntime:
    workspace_root = Path(
        settings.workspace_root
    ).resolve()

    workspace_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_path = Path(
        settings.database_path
    )

    if not database_path.is_absolute():
        database_path = (
            workspace_root / database_path
        )

    database_path = database_path.resolve()

    # ---------------------------------------------------------
    # LLM layer
    # ---------------------------------------------------------

    llm_router = LLMRouter(settings)

    planner = TaskPlanner(
        llm_router
    )

    # ---------------------------------------------------------
    # Tool layer
    # ---------------------------------------------------------

    code_execution_tool = CodeExecutionTool(
        workspace_root=workspace_root,
        default_timeout_seconds=(
            settings.code_execution_timeout_seconds
        ),
    )

    registry = create_builtin_registry(
        workspace_root=workspace_root,
        database_path=database_path,
        allowed_api_hosts=(
            settings.allowed_api_host_set
        ),
        code_execution_tool=(
            code_execution_tool
        ),
    )

    tool_executor = ToolExecutor(
        registry
    )

    tool_runner = SpecialistToolRunner(
        tool_executor
    )

    # ---------------------------------------------------------
    # Memory
    # ---------------------------------------------------------

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    working_memory = RedisWorkingMemoryStore(redis_client)

    _, chroma_collection = await create_chroma_collection(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection,
    )

    long_term_memory = ChromaLongTermMemoryStore(
        chroma_collection
    )
    memory_service = MemoryService(
        long_term_memory,
    )

    # ---------------------------------------------------------
    # Agents
    # ---------------------------------------------------------

    supervisor = SupervisorAgent(
        planner
    )

    research_agent = ResearchAgent(
        tool_runner
    )

    analysis_agent = DataAnalysisAgent(
        tool_runner
    )

    writing_agent = WritingAgent(
        llm_router,
        tool_runner,
    )

    coding_agent = CodeExecutionAgent(
        tool_runner
    )

    reviewer_agent = ReviewerAgent()

    return AgentRuntime(
        supervisor=supervisor,
        research_agent=research_agent,
        analysis_agent=analysis_agent,
        writing_agent=writing_agent,
        coding_agent=coding_agent,
        reviewer_agent=reviewer_agent,
        working_memory=working_memory,
        long_term_memory=long_term_memory,
        memory_service=memory_service,
    )