import sqlite3
from pathlib import Path

import pytest

from app.tools.database_query import (
    DatabaseQueryTool,
)


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:

    path = tmp_path / "test.db"

    connection = sqlite3.connect(path)

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT INTO users (name)
        VALUES ('Alice'), ('Bob')
        """
    )

    connection.commit()
    connection.close()

    return path


@pytest.mark.asyncio
async def test_database_query_returns_rows(
    database_path: Path,
):

    tool = DatabaseQueryTool(
        database_path
    )

    result = await tool.execute(
        {
            "query": (
                "SELECT id, name "
                "FROM users "
                "ORDER BY id"
            ),
        }
    )

    assert result["row_count"] == 2

    assert result["rows"][0]["name"] == "Alice"

    assert result["rows"][1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_database_query_rejects_write_query(
    database_path: Path,
):

    tool = DatabaseQueryTool(
        database_path
    )

    with pytest.raises(ValueError):
        await tool.execute(
            {
                "query": (
                    "DELETE FROM users"
                ),
            }
        )


@pytest.mark.asyncio
async def test_database_query_supports_parameters(
    database_path: Path,
):

    tool = DatabaseQueryTool(
        database_path
    )

    result = await tool.execute(
        {
            "query": (
                "SELECT name "
                "FROM users "
                "WHERE id = :user_id"
            ),
            "parameters": {
                "user_id": 1,
            },
        }
    )

    assert result["rows"][0]["name"] == "Alice"