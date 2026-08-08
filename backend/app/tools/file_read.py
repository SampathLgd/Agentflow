from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


class FileReadTool(BaseTool):
    """
    Read text files from the AgentFlow workspace.

    The tool is deliberately restricted to a configured workspace
    directory so an agent cannot read arbitrary files from the host.
    """

    name = "file_read"

    description = (
        "Read the contents of a text file from the AgentFlow "
        "workspace."
    )

    allowed_specialists = [
        "research",
        "writing",
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

        if not isinstance(
            relative_path,
            str,
        ) or not relative_path.strip():
            raise ValueError(
                "The 'path' argument is required."
            )

        path = self._resolve_safe_path(
            relative_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"File does not exist: {relative_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {relative_path}"
            )

        content = path.read_text(
            encoding="utf-8"
        )

        return {
            "path": relative_path,
            "content": content,
        }