import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


class DatabaseQueryTool(BaseTool):
    """
    Execute read-only SQL queries against a configured SQLite database.

    Only SELECT/WITH queries are permitted.

    The database path is configured by the application rather than
    supplied by the agent, preventing arbitrary database access.
    """

    name = "database_query"

    description = (
        "Execute a read-only SQL query against the configured "
        "AgentFlow database."
    )

    allowed_specialists = [
        "research",
        "data_analysis",
    ]

    def __init__(
        self,
        database_path: Path,
    ) -> None:
        self.database_path = (
            database_path.resolve()
        )

    @staticmethod
    def _validate_query(
        query: str,
    ) -> None:

        normalized = query.strip().lower()

        if not normalized:
            raise ValueError(
                "The 'query' argument is required."
            )

        if not (
            normalized.startswith("select ")
            or normalized.startswith("select\n")
            or normalized.startswith("with ")
        ):
            raise ValueError(
                "Only read-only SELECT or WITH queries "
                "are allowed."
            )

        forbidden = (
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "replace ",
            "truncate ",
            "attach ",
            "detach ",
        )

        for keyword in forbidden:
            if keyword in normalized:
                raise ValueError(
                    "Query contains a forbidden SQL operation."
                )

    def _execute_sync(
        self,
        query: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:

        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = (
            sqlite3.Row
        )

        try:
            cursor = connection.execute(
                query,
                parameters,
            )

            rows = [
                dict(row)
                for row in cursor.fetchall()
            ]

            columns = [
                description[0]
                for description in cursor.description
            ]

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }

        finally:
            connection.close()

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        query = arguments.get(
            "query"
        )

        if not isinstance(
            query,
            str,
        ):
            raise ValueError(
                "The 'query' argument must be a string."
            )

        self._validate_query(query)

        parameters = arguments.get(
            "parameters",
            {},
        )

        if not isinstance(
            parameters,
            dict,
        ):
            raise ValueError(
                "parameters must be an object."
            )

        return await asyncio.to_thread(
            self._execute_sync,
            query,
            parameters,
        )