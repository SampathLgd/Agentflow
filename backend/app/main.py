from fastapi import FastAPI

from app.config import get_settings
from app.llm.router import LLMRouter


settings = get_settings()

llm_router = LLMRouter(settings)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }