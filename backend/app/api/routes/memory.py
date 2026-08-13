from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.memory.chroma_client import (
    create_chroma_collection,
)
from app.memory.chroma_store import (
    ChromaLongTermMemoryStore,
)
from app.memory.service import MemoryService


router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
)


async def _get_memory_service() -> MemoryService:
    """
    Create the application memory service backed by ChromaDB.

    This uses the same Chroma configuration and adapter used
    by the AgentRuntime.
    """

    settings = get_settings()

    _, collection = (
        await create_chroma_collection(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=(
                settings.chroma_collection
            ),
        )
    )

    store = ChromaLongTermMemoryStore(
        collection
    )

    return MemoryService(
        store
    )


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory(
    memory_id: str,
) -> None:
    """
    Delete one long-term memory.

    Deletion is intentionally idempotent:
    deleting an unknown memory ID is still a
    successful delete operation.
    """

    if not memory_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="memory_id cannot be empty.",
        )

    service = (
        await _get_memory_service()
    )

    try:
        await service.delete(
            memory_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/user/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_memory(
    user_id: str,
) -> None:
    """
    Delete every long-term memory belonging
    to the specified user.

    Chroma applies the user_id filter at the
    storage layer, preventing memories belonging
    to other users from being deleted.
    """

    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )

    service = (
        await _get_memory_service()
    )

    try:
        await service.delete_user(
            user_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/dashboard/{user_id}",
)
async def memory_dashboard(
    user_id: str,
) -> dict[str, object]:
    """
    Return memory statistics for a user.
    """

    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be empty.",
        )

    service = (
        await _get_memory_service()
    )

    try:
        return await service.get_dashboard(
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc