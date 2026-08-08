from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


class FileWriteTool(BaseTool):
    """
    Write text files inside the AgentFlow workspace.

    The tool cannot write outside the configured workspace.
    """

    name = "file_write"

    description = (
        "Write text content to a file inside the "
        "AgentFlow workspace."
    )

    allowed_specialists = [
        "research",
        "writing",
        "code_execution",
    ]

    def __init__(
        self,
        workspace_root: Path,
    ) -> None:
        self.workspace_root = (
            workspace_root.resolve()
        )

    def _resolve_safe_path(
        self,
        relative_path: str,
    ) -> Path:
        """
        Resolve a path while preventing traversal outside
        the configured workspace.
        """

        candidate = (
            self.workspace_root / relative_path
        ).resolve()

        try:
            candidate.relative_to(
                self.workspace_root
            )
        except ValueError as exc:
            raise ValueError(
                "File path must remain inside the "
                "configured workspace."
            ) from exc

        return candidate

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        relative_path = arguments.get(
            "path"
        )

        content = arguments.get(
            "content"
        )

        if not isinstance(
            relative_path,
            str,
        ) or not relative_path.strip():
            raise ValueError(
                "The 'path' argument is required."
            )

        if not isinstance(
            content,
            str,
        ):
            raise ValueError(
                "The 'content' argument must be a string."
            )

        path = self._resolve_safe_path(
            relative_path
        )

        # Prevent writing to a directory.
        if path.exists() and not path.is_file():
            raise ValueError(
                f"Path is not a file: {relative_path}"
            )

        # Create parent directories only inside
        # the already validated workspace.
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        return {
            "path": relative_path,
            "bytes_written": len(
                content.encode("utf-8")
            ),
        }