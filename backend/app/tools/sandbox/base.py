from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SandboxResult:
    """
    Standard result returned by any sandbox backend.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: float


class BaseSandbox(ABC):
    """
    Abstraction for isolated code execution.

    Implementations may run locally or inside Kubernetes.
    """

    @abstractmethod
    async def execute(
        self,
        code: str,
        *,
        timeout_seconds: float,
        workspace: str | None = None,
    ) -> SandboxResult:
        raise NotImplementedError