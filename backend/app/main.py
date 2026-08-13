from fastapi import FastAPI

from app.api.routes.hitl import router as hitl_router
from app.api.routes.memory import (
    router as memory_router,
)
from app.config import get_settings
from app.llm.router import LLMRouter
from fastapi.middleware.cors import CORSMiddleware

settings = get_settings()

llm_router = LLMRouter(
    settings
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    hitl_router
)

app.include_router(
    memory_router
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }