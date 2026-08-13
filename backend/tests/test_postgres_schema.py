import pytest
from sqlalchemy import text

from app.db.session import engine


@pytest.mark.asyncio
async def test_postgres_schema_exists():
    expected_tables = {
        "tasks",
        "executions",
        "subtasks",
        "subtask_dependencies",
        "reviews",
    }

    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
        )

        actual_tables = {
            row[0]
            for row in result.fetchall()
        }

    assert expected_tables.issubset(
        actual_tables
    )

    await engine.dispose()