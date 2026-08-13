from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import memory


class FakeMemoryService:
    def __init__(self) -> None:
        self.deleted_memory_ids: list[str] = []
        self.deleted_user_ids: list[str] = []

    async def delete(
        self,
        memory_id: str,
    ) -> None:
        self.deleted_memory_ids.append(
            memory_id
        )

    async def delete_user(
        self,
        user_id: str,
    ) -> None:
        self.deleted_user_ids.append(
            user_id
        )


def build_app(
    monkeypatch,
    service: FakeMemoryService,
) -> FastAPI:
    async def fake_get_memory_service():
        return service

    monkeypatch.setattr(
        memory,
        "_get_memory_service",
        fake_get_memory_service,
    )

    app = FastAPI()

    app.include_router(
        memory.router
    )

    return app


def test_delete_memory(
    monkeypatch,
):
    service = FakeMemoryService()

    app = build_app(
        monkeypatch,
        service,
    )

    client = TestClient(app)

    response = client.delete(
        "/api/memory/memory-123"
    )

    assert response.status_code == 204

    assert (
        service.deleted_memory_ids
        == ["memory-123"]
    )


def test_delete_user_memory(
    monkeypatch,
):
    service = FakeMemoryService()

    app = build_app(
        monkeypatch,
        service,
    )

    client = TestClient(app)

    response = client.delete(
        "/api/memory/user/user-123"
    )

    assert response.status_code == 204

    assert (
        service.deleted_user_ids
        == ["user-123"]
    )


def test_delete_memory_rejects_empty_id(
    monkeypatch,
):
    service = FakeMemoryService()

    app = build_app(
        monkeypatch,
        service,
    )

    client = TestClient(app)

    response = client.delete(
        "/api/memory/%20"
    )

    assert response.status_code == 400


def test_delete_user_rejects_empty_id(
    monkeypatch,
):
    service = FakeMemoryService()

    app = build_app(
        monkeypatch,
        service,
    )

    client = TestClient(app)

    response = client.delete(
        "/api/memory/user/%20"
    )

    assert response.status_code == 400