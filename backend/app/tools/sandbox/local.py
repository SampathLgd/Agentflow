import asyncio
import sys
import time

from .base import BaseSandbox, SandboxResult


class LocalPythonSandbox(BaseSandbox):
    """
    Development sandbox.

    Executes Python in a separate subprocess with:
    - isolated process
    - timeout
    - captured stdout/stderr
    - controlled working directory

    This is NOT the final production isolation boundary.
    KubernetesSandbox will replace this backend in deployment.
    """

    async def execute(
        self,
        code: str,
        *,
        timeout_seconds: float,
        workspace: str | None = None,
    ) -> SandboxResult:

        started = time.perf_counter()

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace,
        )

        timed_out = False

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )

        except asyncio.TimeoutError:
            timed_out = True

            process.kill()

            await process.wait()

            stdout = b""
            stderr = b"Execution timed out."

        duration_ms = (
            time.perf_counter() - started
        ) * 1000

        return SandboxResult(
            stdout=stdout.decode(
                "utf-8",
                errors="replace",
            ),
            stderr=stderr.decode(
                "utf-8",
                errors="replace",
            ),
            exit_code=(
                process.returncode
                if process.returncode is not None
                else -1
            ),
            timed_out=timed_out,
            duration_ms=duration_ms,
        )