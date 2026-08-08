from pathlib import Path
from typing import Any

from app.tools.base import BaseTool
from app.tools.sandbox.local import LocalPythonSandbox


class CodeExecutionTool(BaseTool):
    """
    Execute Python code through a sandbox backend.
    """

    name = "code_execution"

    description = (
        "Execute Python code in an isolated execution environment "
        "and return stdout, stderr, exit code, and execution time."
    )

    allowed_specialists = [
        "code_execution",
    ]

    def __init__(
        self,
        workspace_root: Path,
        sandbox: LocalPythonSandbox | None = None,
        default_timeout_seconds: float = 5.0,
    ) -> None:

        self.workspace_root = (
            workspace_root.resolve()
        )

        self.sandbox = (
            sandbox
            if sandbox is not None
            else LocalPythonSandbox()
        )

        self.default_timeout_seconds = (
            default_timeout_seconds
        )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        code = arguments.get("code")

        if not isinstance(code, str):
            raise ValueError(
                "The 'code' argument must be a string."
            )

        if not code.strip():
            raise ValueError(
                "The 'code' argument cannot be empty."
            )

        timeout_seconds = arguments.get(
            "timeout_seconds",
            self.default_timeout_seconds,
        )

        if not isinstance(
            timeout_seconds,
            (int, float),
        ):
            raise ValueError(
                "timeout_seconds must be numeric."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if timeout_seconds > 30:
            raise ValueError(
                "timeout_seconds cannot exceed 30 seconds."
            )

        result = await self.sandbox.execute(
            code,
            timeout_seconds=float(
                timeout_seconds
            ),
            workspace=str(
                self.workspace_root
            ),
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms,
        }