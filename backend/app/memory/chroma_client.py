from __future__ import annotations

import chromadb


async def create_chroma_collection(
    *,
    host: str,
    port: int,
    collection_name: str,
):
    """
    Connect to a server-backed ChromaDB instance and return
    the configured collection.
    """

    client = await chromadb.AsyncHttpClient(
        host=host,
        port=port,
    )

    collection = await client.get_or_create_collection(
        name=collection_name,
    )

    return client, collection