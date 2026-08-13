from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery(
    "agentflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.imports = (
    "app.tasks.execution",
    "app.tasks.resume",
)